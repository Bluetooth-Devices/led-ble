from __future__ import annotations

import asyncio
import colorsys
import logging
from collections.abc import Callable
from typing import Any, TypeVar, cast

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic, BleakGATTServiceCollection
from bleak.exc import BleakDBusError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakError,
    BleakNotFoundError,
    ble_device_has_changed,
    establish_connection,
)

from led_ble.const import (
    POSSIBLE_READ_CHARACTERISTIC_UUIDS,
    POSSIBLE_WRITE_CHARACTERISTIC_UUIDS,
    POWER_OFF_COMAMND,
    POWER_ON_COMMAND,
    STATE_COMMAND,
)

from .exceptions import CharacteristicMissingError
from .models import LEDBLEState

__version__ = "0.4.0"


WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

DISCONNECT_DELAY = 120

RETRY_BACKOFF_EXCEPTIONS = (BleakDBusError,)
BLEAK_EXCEPTIONS = (AttributeError, BleakError, asyncio.exceptions.TimeoutError)

RETRY_EXCEPTIONS = (
    asyncio.TimeoutError,
    BleakError,
    EOFError,
)
_LOGGER = logging.getLogger(__name__)

DEFAULT_ATTEMPTS = 3


def retry_bluetooth_connection_error(func: WrapFuncType) -> WrapFuncType:
    """Define a wrapper to retry on bleak error.

    The accessory is allowed to disconnect us any time so
    we need to retry the operation.
    """

    async def _async_wrap_retry_bluetooth_connection_error(
        self: "LEDBLE", *args: Any, **kwargs: Any
    ) -> Any:
        _LOGGER.debug("%s: Starting retry loop", self.name)
        attempts = DEFAULT_ATTEMPTS
        max_attempts = attempts - 1

        for attempt in range(attempts):
            try:
                return await func(self, *args, **kwargs)
            except BleakNotFoundError:
                # The lock cannot be found so there is no
                # point in retrying.
                raise
            except RETRY_BACKOFF_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    _LOGGER.debug(
                        "%s: %s error calling %s, reach max attempts (%s/%s)",
                        self.name,
                        type(err),
                        func,
                        attempt,
                        max_attempts,
                        exc_info=True,
                    )
                    raise
                _LOGGER.debug(
                    "%s: %s error calling %s, backing off %ss, retrying (%s/%s)...",
                    self.name,
                    type(err),
                    func,
                    0.25,
                    attempt,
                    max_attempts,
                    exc_info=True,
                )
                await asyncio.sleep(0.25)
            except RETRY_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    _LOGGER.debug(
                        "%s: %s error calling %s, reach max attempts (%s/%s)",
                        self.name,
                        type(err),
                        func,
                        attempt,
                        max_attempts,
                        exc_info=True,
                    )
                    raise
                _LOGGER.debug(
                    "%s: %s error calling %s, retrying  (%s/%s)...",
                    self.name,
                    type(err),
                    func,
                    attempt,
                    max_attempts,
                    exc_info=True,
                )

    return cast(WrapFuncType, _async_wrap_retry_bluetooth_connection_error)


class LEDBLE:
    def __init__(
        self, ble_device: BLEDevice, retry_count: int = DEFAULT_ATTEMPTS
    ) -> None:
        """Init the LEDBLE."""
        self._ble_device = ble_device
        self._operation_lock = asyncio.Lock()
        self._state = LEDBLEState()
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._cached_services: BleakGATTServiceCollection | None = None
        self._read_char: BleakGATTCharacteristic | None = None
        self._write_char: BleakGATTCharacteristic | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._retry_count = retry_count
        self._client: BleakClientWithServiceCache | None = None
        self._expected_disconnect = False
        self.loop = asyncio.get_running_loop()
        self._callbacks: list[Callable[[LEDBLEState], None]] = []

    def set_ble_device(self, ble_device: BLEDevice) -> None:
        """Set the ble device."""
        if self._ble_device and ble_device_has_changed(self._ble_device, ble_device):
            _LOGGER.debug(
                "%s: New ble device details, clearing cached services", self.name
            )
            self._cached_services = None
        self._ble_device = ble_device
        self._address = ble_device.address

    @property
    def name(self) -> str:
        """Get the name of the device."""
        return self._ble_device.name or self._ble_device.address

    @property
    def rssi(self) -> str:
        """Get the name of the device."""
        return self._ble_device.rssi

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

    @retry_bluetooth_connection_error
    async def update(self) -> None:
        """Update the LEDBLE."""
        _LOGGER.debug("%s: Updating", self.name)
        await self._send_command(STATE_COMMAND)

    @retry_bluetooth_connection_error
    async def turn_on(self) -> None:
        """Turn on."""
        _LOGGER.debug("%s: Turn on", self.name)
        await self._send_command(POWER_ON_COMMAND)
        self._state = LEDBLEState(
            rgb=self.rgb,
            w=self.w,
            power=True,
            mode=self.mode,
            speed=self.speed,
            model_num=self.model_num,
            preset_pattern=self.preset_pattern,
        )
        self._fire_callbacks()

    @retry_bluetooth_connection_error
    async def turn_off(self) -> None:
        """Turn off."""
        _LOGGER.debug("%s: Turn off", self.name)
        await self._send_command(POWER_OFF_COMAMND)
        self._state = LEDBLEState(
            rgb=self.rgb,
            w=self.w,
            power=False,
            mode=self.mode,
            speed=self.speed,
            model_num=self.model_num,
            preset_pattern=self.preset_pattern,
        )
        self._fire_callbacks()

    async def set_brightness(self, brightness: int) -> None:
        """Set the brightness."""
        _LOGGER.debug("%s: Set brightness: %s", self.name, brightness)
        await self.set_rgb(self.rgb_unscaled, brightness)

    @retry_bluetooth_connection_error
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

        await self._send_command(b"\x56" + bytes(rgb) + b"\x00\xF0\xAA")
        self._state = LEDBLEState(
            rgb=rgb,
            power=True,
            mode=self.mode,
            speed=self.speed,
            model_num=self.model_num,
            preset_pattern=self.preset_pattern,
        )
        self._fire_callbacks()

    @retry_bluetooth_connection_error
    async def set_white(self, brightness: int) -> None:
        """Set rgb."""
        _LOGGER.debug("%s: Set white: %s", self.name, brightness)
        if not 0 <= brightness <= 255:
            raise ValueError("Value {} is outside the valid range of 0-255")
        await self._send_command(
            b"\x56\x00\x00\x00" + bytes([brightness]) + b"\x0F\xAA"
        )
        self._state = LEDBLEState(
            rgb=(0, 0, 0),
            w=brightness,
            power=True,
            mode=self.mode,
            speed=self.speed,
            model_num=self.model_num,
            preset_pattern=self.preset_pattern,
        )
        self._fire_callbacks()

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
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                self._disconnected,
                cached_services=self._cached_services,
                ble_device_callback=lambda: self._ble_device,
            )
            _LOGGER.debug("%s: Connected; RSSI: %s", self.name, self.rssi)
            resolved = self._resolve_characteristics(client.services)
            if not resolved:
                # Try to handle services failing to load
                resolved = self._resolve_characteristics(await client.get_services())
            self._cached_services = client.services if resolved else None
            self._client = client
            self._reset_disconnect_timer()

            _LOGGER.debug(
                "%s: Subscribe to notifications; RSSI: %s", self.name, self.rssi
            )
            await client.start_notify(self._read_char, self._notification_handler)

    @property
    def model_num(self) -> int:
        """Return the model num."""
        return self._state.model_num

    @property
    def preset_pattern(self) -> int:
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

    def _notification_handler(self, _sender: int, data: bytearray) -> None:
        """Handle notification responses."""
        _LOGGER.debug(
            "%s: Notification received; RSSI: %s: %s", self.name, self.rssi, data.hex()
        )
        model_num = data[1]
        on = data[2] == 0x23
        preset_pattern = data[3]
        mode = data[4]
        speed = data[5]
        r = data[6]
        g = data[7]
        b = data[8]
        w = data[9]
        self._state = LEDBLEState(
            on, (r, g, b), w, model_num, preset_pattern, mode, speed
        )
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
                await client.stop_notify(read_char)
                await client.disconnect()

    async def _send_command_locked(self, command: bytes) -> None:
        """Send command to device and read response."""
        try:
            await self._execute_command_locked(command)
        except BleakDBusError as ex:
            # Disconnect so we can reset state and try again
            await asyncio.sleep(0.25)
            _LOGGER.debug(
                "%s: RSSI: %s; Backing off %ss; Disconnecting due to error: %s",
                self.name,
                self.rssi,
                0.25,
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

    async def _send_command(self, command: bytes, retry: int | None = None) -> None:
        """Send command to device and read response."""
        await self._ensure_connected()
        if retry is None:
            retry = self._retry_count
        _LOGGER.debug("%s: Sending command %s", self.name, command)
        max_attempts = retry + 1
        if self._operation_lock.locked():
            _LOGGER.debug(
                "%s: Operation already in progress, waiting for it to complete; RSSI: %s",
                self.name,
                self.rssi,
            )
        async with self._operation_lock:
            for attempt in range(max_attempts):
                try:
                    await self._send_command_locked(command)
                    return
                except BleakNotFoundError:
                    _LOGGER.error(
                        "%s: device not found, no longer in range, or poor RSSI: %s",
                        self.name,
                        self.rssi,
                        exc_info=True,
                    )
                    return None
                except CharacteristicMissingError as ex:
                    if attempt == retry:
                        _LOGGER.error(
                            "%s: characteristic missing: %s; Stopping trying; RSSI: %s",
                            self.name,
                            ex,
                            self.rssi,
                            exc_info=True,
                        )
                        return None

                    _LOGGER.debug(
                        "%s: characteristic missing: %s; RSSI: %s",
                        self.name,
                        ex,
                        self.rssi,
                        exc_info=True,
                    )
                except BLEAK_EXCEPTIONS:
                    if attempt == retry:
                        _LOGGER.error(
                            "%s: communication failed; Stopping trying; RSSI: %s",
                            self.name,
                            self.rssi,
                            exc_info=True,
                        )
                        return None

                    _LOGGER.debug(
                        "%s: communication failed with:", self.name, exc_info=True
                    )

        raise RuntimeError("Unreachable")

    async def _execute_command_locked(self, command: bytes) -> None:
        """Execute command and read response."""
        assert self._client is not None  # nosec
        if not self._read_char:
            raise CharacteristicMissingError("Read characteristic missing")
        if not self._write_char:
            raise CharacteristicMissingError("Write characteristic missing")
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
