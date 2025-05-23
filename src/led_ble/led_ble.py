from __future__ import annotations

import asyncio
import colorsys
import logging
from collections.abc import Callable
from dataclasses import replace
from typing import Any, TypeVar

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from bleak.backends.service import BleakGATTCharacteristic, BleakGATTServiceCollection
from bleak.exc import BleakDBusError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakError,
    BleakNotFoundError,
    establish_connection,
    retry_bluetooth_connection_error,
)
from flux_led.base_device import PROTOCOL_NAME_TO_CLS, PROTOCOL_TYPES
from flux_led.const import LevelWriteMode
from flux_led.pattern import EFFECT_ID_NAME, EFFECT_LIST, PresetPattern
from flux_led.utils import rgbw_brightness

from led_ble.model_db import LEDBLEModel

from .const import (
    POSSIBLE_READ_CHARACTERISTIC_UUIDS,
    POSSIBLE_WRITE_CHARACTERISTIC_UUIDS,
    STATE_COMMAND,
)
from .exceptions import CharacteristicMissingError
from .model_db import get_model
from .models import LEDBLEState
from .util import asyncio_timeout

BLEAK_BACKOFF_TIME = 0.25

__version__ = "0.5.0"


WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

DISCONNECT_DELAY = 120

RETRY_BACKOFF_EXCEPTIONS = (BleakDBusError,)

_LOGGER = logging.getLogger(__name__)

DEFAULT_ATTEMPTS = 3

DREAM_EFFECTS = {f"Effect {i + 1}": i for i in range(0, 255)}
DREAM_EFFECT_LIST = list(DREAM_EFFECTS)


class LEDBLE:
    def __init__(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData | None = None
    ) -> None:
        """Init the LEDBLE."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data
        self._operation_lock = asyncio.Lock()
        self._state = LEDBLEState()
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._read_char: BleakGATTCharacteristic | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._client: BleakClientWithServiceCache | None = None
        self._expected_disconnect = False
        self.loop = asyncio.get_running_loop()
        self._callbacks: list[Callable[[LEDBLEState], None]] = []
        self._model_data: LEDBLEModel | None = None
        self._protocol: PROTOCOL_TYPES | None = None
        self._resolve_protocol_event = asyncio.Event()

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        """Set the ble device."""
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data

    @property
    def address(self) -> str:
        """Return the address."""
        return self._ble_device.address

    @property
    def _address(self) -> str:
        """Return the address."""
        return self._ble_device.address

    @property
    def model_data(self) -> LEDBLEModel:
        """Return the model data."""
        assert self._model_data is not None  # nosec
        return self._model_data

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._ble_device.name or self._ble_device.address

    @property
    def rssi(self) -> int | None:
        """Get the rssi of the device."""
        if self._advertisement_data:
            return self._advertisement_data.rssi
        return None

    @property
    def state(self) -> LEDBLEState:
        """Return the state."""
        return self._state

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self._state.rgb

    @property
    def w(self) -> int:
        return self._state.w

    @property
    def rgb_unscaled(self) -> tuple[int, int, int]:
        """Return the unscaled RGB."""
        r, g, b = self.rgb
        hsv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        r_p, g_p, b_p = colorsys.hsv_to_rgb(hsv[0], hsv[1], 1)
        return round(r_p * 255), round(g_p * 255), round(b_p * 255)

    @property
    def on(self) -> bool:
        return self._state.power

    @property
    def brightness(self) -> int:
        """Return current brightness 0-255."""
        if self.w:
            return self.w
        r, g, b = self.rgb
        _, _, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        return int(v * 255)

    async def update(self) -> None:
        """Update the LEDBLE."""
        await self._ensure_connected()
        await self._resolve_protocol()
        _LOGGER.debug("%s: Updating", self.name)
        assert self._protocol is not None  # nosec
        command = self._protocol.construct_state_query()
        await self._send_command([command])

    async def turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("%s: Turn on", self.name)
        assert self._protocol is not None  # nosec
        await self._send_command(self._protocol.construct_state_change(True))
        self._state = replace(self._state, power=True)
        self._fire_callbacks()

    async def turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("%s: Turn off", self.name)
        assert self._protocol is not None  # nosec
        await self._send_command(self._protocol.construct_state_change(False))
        self._state = replace(self._state, power=False)
        self._fire_callbacks()

    async def set_brightness(self, brightness: int) -> None:
        """Set the brightness."""
        _LOGGER.debug("%s: Set brightness: %s", self.name, brightness)
        effect = self.effect
        if effect:
            effect_brightness = round(brightness / 255 * 100)
            await self.async_set_effect(effect, self.speed, effect_brightness)
            return
        if self.w:
            await self.set_white(brightness)
            return
        await self.set_rgb(self.rgb_unscaled, brightness)

    async def set_rgb(
        self, rgb: tuple[int, int, int], brightness: int | None = None
    ) -> None:
        """Set rgb."""
        _LOGGER.debug("%s: Set rgb: %s brightness: %s", self.name, rgb, brightness)
        for value in rgb:
            if not 0 <= value <= 255:
                raise ValueError("Value {} is outside the valid range of 0-255")
        if brightness is not None:
            rgb = self._calculate_brightness(rgb, brightness)
        _LOGGER.debug("%s: Set rgb after brightness: %s", self.name, rgb)
        assert self._protocol is not None  # nosec
        r, g, b = rgb
        command = self._protocol.construct_levels_change(
            persist=True,
            red=r,
            green=g,
            blue=b,
            warm_white=None,
            cool_white=None,
            write_mode=LevelWriteMode.COLORS,
        )
        await self._send_command(command)
        self._state = replace(
            self._state,
            rgb=rgb,
            w=0,
            preset_pattern=1 if self.dream else self.preset_pattern_num,
        )
        self._fire_callbacks()

    async def set_rgbw(
        self, rgbw: tuple[int, int, int, int], brightness: int | None = None
    ) -> None:
        """Set rgbw."""
        _LOGGER.debug("%s: Set rgbw: %s brightness: %s", self.name, rgbw, brightness)
        for value in rgbw:
            if not 0 <= value <= 255:
                raise ValueError("Value {} is outside the valid range of 0-255")
        r, g, b, w = rgbw_brightness(rgbw, brightness)
        _LOGGER.debug("%s: Set rgbw after brightness: %s", self.name, rgbw)
        assert self._protocol is not None  # nosec

        command = self._protocol.construct_levels_change(
            persist=True,
            red=r,
            green=g,
            blue=b,
            warm_white=w,
            cool_white=None,
            write_mode=LevelWriteMode.ALL,
        )
        await self._send_command(command)

        self._state = replace(
            self._state,
            rgb=(rgbw[0], rgbw[1], rgbw[2]),
            w=rgbw[3],
            preset_pattern=1 if self.dream else self.preset_pattern_num,
        )
        self._fire_callbacks()

    async def set_white(self, brightness: int) -> None:
        """Set rgb."""
        _LOGGER.debug("%s: Set white: %s", self.name, brightness)
        if not 0 <= brightness <= 255:
            raise ValueError("Value {} is outside the valid range of 0-255")
        assert self._protocol is not None  # nosec

        command = self._protocol.construct_levels_change(
            persist=True,
            red=0,
            green=0,
            blue=0,
            warm_white=brightness,
            cool_white=None,
            write_mode=LevelWriteMode.WHITES,
        )
        await self._send_command(command)
        self._state = replace(
            self._state,
            rgb=(0, 0, 0),
            w=brightness,
            preset_pattern=1 if self.dream else self.preset_pattern_num,
        )
        self._fire_callbacks()

    def _generate_preset_pattern(
        self, pattern: int, speed: int, brightness: int
    ) -> bytearray:
        """Generate the preset pattern protocol bytes."""
        if self.dream:
            # TODO: move this to the protocol
            brightness = int(brightness * 255 / 100)
            speed = int(speed * 255 / 100)
            return bytearray([0x9E, 0x00, pattern, speed, brightness, 0x00, 0xE9])
        PresetPattern.valid_or_raise(pattern)
        if not (1 <= brightness <= 100):
            raise ValueError("Brightness must be between 1 and 100")
        assert self._protocol is not None  # nosec
        return self._protocol.construct_preset_pattern(pattern, speed, brightness)

    async def async_set_preset_pattern(
        self, effect: int, speed: int, brightness: int = 100
    ) -> None:
        """Set a preset pattern on the device."""
        command = self._generate_preset_pattern(effect, speed, brightness)
        await self._send_command(command)
        if self.dream:
            self._state = replace(self._state, preset_pattern=0, mode=effect)
        else:
            self._state = replace(self._state, preset_pattern=effect)
        self._fire_callbacks()

    async def async_set_effect(
        self, effect: str, speed: int, brightness: int = 100
    ) -> None:
        """Set an effect."""
        await self.async_set_preset_pattern(
            self._effect_to_pattern(effect), speed, brightness
        )

    async def stop(self) -> None:
        """Stop the LEDBLE."""
        _LOGGER.debug("%s: Stop", self.name)
        await self._execute_disconnect()

    def _calculate_brightness(
        self, rgb: tuple[int, int, int], level: int
    ) -> tuple[int, int, int]:
        hsv = colorsys.rgb_to_hsv(*rgb)
        r, g, b = colorsys.hsv_to_rgb(hsv[0], hsv[1], level)
        return int(r), int(g), int(b)

    def _fire_callbacks(self) -> None:
        """Fire the callbacks."""
        for callback in self._callbacks:
            callback(self._state)

    def register_callback(
        self, callback: Callable[[LEDBLEState], None]
    ) -> Callable[[], None]:
        """Register a callback to be called when the state changes."""

        def unregister_callback() -> None:
            self._callbacks.remove(callback)

        self._callbacks.append(callback)
        return unregister_callback

    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        if self._connect_lock.locked():
            _LOGGER.debug(
                "%s: Connection already in progress, waiting for it to complete; RSSI: %s",
                self.name,
                self.rssi,
            )
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return
        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return
            _LOGGER.debug("%s: Connecting; RSSI: %s", self.name, self.rssi)
            for attempt in range(2):
                client = await establish_connection(
                    BleakClientWithServiceCache,
                    self._ble_device,
                    self.name,
                    self._disconnected,
                    use_services_cache=True,
                    ble_device_callback=lambda: self._ble_device,
                )
                _LOGGER.debug("%s: Connected; RSSI: %s", self.name, self.rssi)
                if self._resolve_characteristics(client.services):
                    # Supported characteristics found
                    break
                else:
                    if attempt == 0:
                        # Try to handle services failing to load
                        await client.clear_cache()
                        await client.disconnect()
                        continue
                    await client.disconnect()
                    raise CharacteristicMissingError(
                        "Failed to find supported characteristics, device may not be supported"
                    )

            self._client = client
            self._reset_disconnect_timer()

            _LOGGER.debug(
                "%s: Subscribe to notifications; RSSI: %s", self.name, self.rssi
            )
            await client.start_notify(self._read_char, self._notification_handler)
            if not self._protocol:
                await self._resolve_protocol()

    @property
    def model_num(self) -> int:
        """Return the model num."""
        return self._state.model_num

    @property
    def version_num(self) -> int:
        """Return the version num."""
        return self._state.version_num

    @property
    def preset_pattern_num(self) -> int:
        """Return the preset_pattern."""
        return self._state.preset_pattern

    @property
    def mode(self) -> int:
        """Return the mode."""
        return self._state.mode

    @property
    def speed(self) -> int:
        """Return the speed."""
        return self._state.speed

    def _effect_to_pattern(self, effect: str) -> int:
        """Convert an effect to a pattern code."""
        if self.dream:
            if effect not in DREAM_EFFECTS:
                raise ValueError(f"Effect {effect} is not valid")
            return DREAM_EFFECTS[effect]
        return PresetPattern.str_to_val(effect)

    @property
    def effect_list(self) -> list[str]:
        """Return the list of available effects."""
        if self.dream:
            return DREAM_EFFECT_LIST
        return EFFECT_LIST

    @property
    def dream(self) -> bool:
        """Return if the device is a dream."""
        return self.model_num in (0x10,) or (
            self._advertisement_data is not None
            and self._advertisement_data.local_name is not None
            and self._advertisement_data.local_name.startswith("Dream")
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self.dream and self.preset_pattern_num == 0:
            return f"Effect {self.mode + 1}"
        return self._named_effect

    @property
    def _named_effect(self) -> str | None:
        """Returns the named effect."""
        return EFFECT_ID_NAME.get(self.preset_pattern_num)

    def _notification_handler(self, _sender: int, data: bytearray) -> None:
        """Handle notification responses."""
        _LOGGER.debug("%s: Notification received: %s", self.name, data.hex())

        if len(data) == 4 and data[0] == 0xCC:
            on = data[1] == 0x23
            self._state = replace(self._state, power=on)
            return
        if len(data) < 11:
            return
        model_num = data[1]
        on = data[2] == 0x23
        preset_pattern = data[3]
        mode = data[4]
        speed = data[5]
        r = data[6]
        g = data[7]
        b = data[8]
        w = data[9]
        version = data[10]
        self._state = LEDBLEState(
            on, (r, g, b), w, model_num, preset_pattern, mode, speed, version
        )

        _LOGGER.debug(
            "%s: Notification received; RSSI: %s: %s %s",
            self.name,
            self.rssi,
            data.hex(),
            self._state,
        )

        if not self._resolve_protocol_event.is_set():
            self._resolve_protocol_event.set()
            self._model_data = get_model(model_num)
            self._set_protocol(self._model_data.protocol_for_version_num(version))

        self._fire_callbacks()

    def _reset_disconnect_timer(self) -> None:
        """Reset disconnect timer."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
        self._expected_disconnect = False
        self._disconnect_timer = self.loop.call_later(
            DISCONNECT_DELAY, self._disconnect
        )

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            _LOGGER.debug(
                "%s: Disconnected from device; RSSI: %s", self.name, self.rssi
            )
            return
        _LOGGER.warning(
            "%s: Device unexpectedly disconnected; RSSI: %s",
            self.name,
            self.rssi,
        )

    def _disconnect(self) -> None:
        """Disconnect from device."""
        self._disconnect_timer = None
        asyncio.create_task(self._execute_timed_disconnect())

    async def _execute_timed_disconnect(self) -> None:
        """Execute timed disconnection."""
        _LOGGER.debug(
            "%s: Disconnecting after timeout of %s",
            self.name,
            DISCONNECT_DELAY,
        )
        await self._execute_disconnect()

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            read_char = self._read_char
            client = self._client
            self._expected_disconnect = True
            self._client = None
            self._read_char = None
            self._write_char = None
            if client and client.is_connected:
                if read_char:
                    try:
                        await client.stop_notify(read_char)
                    except BleakError:
                        _LOGGER.debug(
                            "%s: Failed to stop notifications", self.name, exc_info=True
                        )
                await client.disconnect()

    @retry_bluetooth_connection_error(DEFAULT_ATTEMPTS)
    async def _send_command_locked(self, commands: list[bytes]) -> None:
        """Send command to device and read response."""
        try:
            await self._execute_command_locked(commands)
        except BleakDBusError as ex:
            # Disconnect so we can reset state and try again
            await asyncio.sleep(BLEAK_BACKOFF_TIME)
            _LOGGER.debug(
                "%s: RSSI: %s; Backing off %ss; Disconnecting due to error: %s",
                self.name,
                self.rssi,
                BLEAK_BACKOFF_TIME,
                ex,
            )
            await self._execute_disconnect()
            raise
        except BleakError as ex:
            # Disconnect so we can reset state and try again
            _LOGGER.debug(
                "%s: RSSI: %s; Disconnecting due to error: %s", self.name, self.rssi, ex
            )
            await self._execute_disconnect()
            raise

    async def _send_command(
        self, commands: list[bytes] | bytes, retry: int | None = None
    ) -> None:
        """Send command to device and read response."""
        await self._ensure_connected()
        await self._resolve_protocol()
        if not isinstance(commands, list):
            commands = [commands]
        await self._send_command_while_connected(commands, retry)

    async def _send_command_while_connected(
        self, commands: list[bytes], retry: int | None = None
    ) -> None:
        """Send command to device and read response."""
        _LOGGER.debug(
            "%s: Sending commands %s",
            self.name,
            [command.hex() for command in commands],
        )
        if self._operation_lock.locked():
            _LOGGER.debug(
                "%s: Operation already in progress, waiting for it to complete; RSSI: %s",
                self.name,
                self.rssi,
            )
        async with self._operation_lock:
            try:
                await self._send_command_locked(commands)
                return
            except BleakNotFoundError:
                _LOGGER.error(
                    "%s: device not found, no longer in range, or poor RSSI: %s",
                    self.name,
                    self.rssi,
                    exc_info=True,
                )
                raise
            except CharacteristicMissingError as ex:
                _LOGGER.debug(
                    "%s: characteristic missing: %s; RSSI: %s",
                    self.name,
                    ex,
                    self.rssi,
                    exc_info=True,
                )
                raise
            except BLEAK_EXCEPTIONS:
                _LOGGER.debug("%s: communication failed", self.name, exc_info=True)
                raise

        raise RuntimeError("Unreachable")

    async def _execute_command_locked(self, commands: list[bytes]) -> None:
        """Execute command and read response."""
        assert self._client is not None  # nosec
        if not self._read_char:
            raise CharacteristicMissingError("Read characteristic missing")
        if not self._write_char:
            raise CharacteristicMissingError("Write characteristic missing")
        for command in commands:
            await self._client.write_gatt_char(self._write_char, command, False)

    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve characteristics."""
        for characteristic in POSSIBLE_READ_CHARACTERISTIC_UUIDS:
            if char := services.get_characteristic(characteristic):
                self._read_char = char
                break
        for characteristic in POSSIBLE_WRITE_CHARACTERISTIC_UUIDS:
            if char := services.get_characteristic(characteristic):
                self._write_char = char
                break
        return bool(self._read_char and self._write_char)

    async def _resolve_protocol(self) -> None:
        """Resolve protocol."""
        if self._resolve_protocol_event.is_set():
            return
        await self._send_command_while_connected([STATE_COMMAND])
        async with asyncio_timeout(10):
            await self._resolve_protocol_event.wait()

    def _set_protocol(self, protocol: str) -> None:
        cls = PROTOCOL_NAME_TO_CLS.get(protocol)
        if cls is None:
            raise ValueError(f"Invalid protocol: {protocol}")
        self._protocol = cls()
