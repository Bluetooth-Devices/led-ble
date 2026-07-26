from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import cast
from unittest.mock import AsyncMock, Mock

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTServiceCollection
import pytest

from led_ble.govee import (
    GOVEE_H6196_MODEL_NUM,
    UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC,
    GoveeH6196Command,
    build_h6196_brightness_packet,
    build_h6196_packet,
    build_h6196_power_packet,
    build_h6196_rgb_packet,
    is_h6196_light_name,
)
from led_ble.led_ble import LEDBLE
from led_ble.models import LEDBLEState
from led_ble.native_protocol import H6196_MODEL_DATA, NativeCommand

from .conftest import FakeAdvertisement, FakeBLEDevice, FakeServices


def test_identifies_h6196_light_names() -> None:
    assert is_h6196_light_name("ihoment_H6196_F23C")
    assert is_h6196_light_name("ihoment_H6196")
    assert not is_h6196_light_name("Govee_H5075_2762")
    assert not is_h6196_light_name(None)


def test_builds_known_h6196_packets() -> None:
    assert build_h6196_power_packet(True).hex() == (
        "3301010000000000000000000000000000000033"
    )
    assert build_h6196_power_packet(False).hex() == (
        "3301000000000000000000000000000000000032"
    )
    assert build_h6196_brightness_packet(0xA0).hex() == (
        "3304a00000000000000000000000000000000097"
    )
    assert build_h6196_rgb_packet((0, 0, 255)).hex() == (
        "3305020000ff00000000000000000000000000cb"
    )


def test_validates_h6196_packet_values() -> None:
    with pytest.raises(ValueError, match="Byte value"):
        build_h6196_brightness_packet(256)

    with pytest.raises(ValueError, match="Byte value"):
        build_h6196_rgb_packet((-1, 0, 0))

    with pytest.raises(ValueError, match="Payload too long"):
        build_h6196_packet(GoveeH6196Command.POWER, [0] * 18)


def test_h6196_characteristics_are_known(make_led: Callable[..., LEDBLE]) -> None:
    led = make_led(name="ihoment_H6196_F23C")

    assert led._native_protocol is not None
    assert (
        UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC
        in led._native_protocol.write_characteristics
    )
    assert led._native_protocol.read_characteristics == ()


def test_h6196_can_be_detected_from_advertisement_name(
    make_led: Callable[..., LEDBLE],
) -> None:
    led = make_led(
        name=None,
        advertisement=FakeAdvertisement(local_name="ihoment_H6196_F23C"),
    )

    assert led._native_protocol is not None


def test_resolves_h6196_characteristics(make_led: Callable[..., LEDBLE]) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    write_char = object()
    services = FakeServices(
        {
            UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC: write_char,
        }
    )

    assert led._resolve_characteristics(cast(BleakGATTServiceCollection, services))
    assert led._write_char is write_char
    assert led._read_char is None


def test_h6196_turn_on_uses_govee_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()

    loop.run_until_complete(led.turn_on())

    led._send_command.assert_awaited_once_with([build_h6196_power_packet(True)])
    assert led.on is True
    assert led.model_num == GOVEE_H6196_MODEL_NUM


def test_h6196_turn_off_uses_govee_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()
    led._state = led._state.__class__(power=True)

    loop.run_until_complete(led.turn_off())

    led._send_command.assert_awaited_once_with([build_h6196_power_packet(False)])
    assert led.on is False


def test_h6196_set_rgb_uses_govee_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()

    loop.run_until_complete(led.set_rgb((255, 245, 220)))

    led._send_command.assert_awaited_once_with(
        [build_h6196_rgb_packet((255, 245, 220))]
    )
    assert led.rgb == (255, 245, 220)
    assert led.model_num == GOVEE_H6196_MODEL_NUM
    assert led.w == 0


def test_h6196_set_brightness_uses_govee_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()

    loop.run_until_complete(led.set_brightness(180))

    led._send_command.assert_awaited_once_with([build_h6196_brightness_packet(180)])
    assert led.brightness == 180


def test_h6196_protocol_is_retained_after_nameless_advertisement(
    make_led: Callable[..., LEDBLE],
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    native_protocol = led._native_protocol
    nameless_device = cast(BLEDevice, FakeBLEDevice(name=None))

    led.set_ble_device_and_advertisement_data(nameless_device, None)

    assert led._native_protocol is native_protocol


def test_h6196_model_has_no_flux_led_protocol() -> None:
    assert H6196_MODEL_DATA.protocols == []
    with pytest.raises(ValueError, match="Native models"):
        H6196_MODEL_DATA.protocol_for_version_num(0)


def test_h6196_write_only_protocol_does_not_require_read_characteristic(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    client = Mock()
    client.write_gatt_char = AsyncMock()
    led._client = client
    led._write_char = Mock()

    loop.run_until_complete(led._execute_command_locked([b"\x01"]))

    client.write_gatt_char.assert_awaited_once_with(led._write_char, b"\x01", False)


def test_h6196_connects_without_notification_subscription(
    loop: asyncio.AbstractEventLoop,
    make_led: Callable[..., LEDBLE],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    client = Mock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.services = FakeServices({UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC: Mock()})
    monkeypatch.setattr(
        "led_ble.led_ble.establish_connection", AsyncMock(return_value=client)
    )

    loop.run_until_complete(led._ensure_connected())

    try:
        assert led._client is client
        client.start_notify.assert_not_awaited()
    finally:
        assert led._disconnect_timer is not None
        led._disconnect_timer.cancel()


def test_h6196_set_brightness_rejects_out_of_range(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")

    with pytest.raises(ValueError, match="outside the valid range"):
        loop.run_until_complete(led.set_brightness(256))


def test_h6196_set_brightness_scales_existing_color(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()
    led._state = LEDBLEState(rgb=(128, 0, 0))

    loop.run_until_complete(led.set_brightness(64))

    led._send_command.assert_awaited_once_with([build_h6196_brightness_packet(64)])
    assert led.rgb == (64, 0, 0)
    assert led.model_num == GOVEE_H6196_MODEL_NUM


def test_h6196_set_white_uses_rgb_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()

    loop.run_until_complete(led.set_white(128))

    led._send_command.assert_awaited_once_with(
        [build_h6196_rgb_packet((128, 128, 128))]
    )
    assert led.rgb == (128, 128, 128)


def test_h6196_set_rgbw_uses_rgb_packet(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()

    loop.run_until_complete(led.set_rgbw((0, 0, 0, 200)))

    led._send_command.assert_awaited_once_with(
        [build_h6196_rgb_packet((200, 200, 200))]
    )
    assert led.rgb == (200, 200, 200)


def test_h6196_effects_are_not_supported(make_led: Callable[..., LEDBLE]) -> None:
    led = make_led(name="ihoment_H6196_F23C")

    assert led.effect is None
    assert led.effect_list == []


def test_h6196_ignores_unparsed_notifications(make_led: Callable[..., LEDBLE]) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    received: list[LEDBLEState] = []
    led.register_callback(received.append)
    before = led.state

    led._notification_handler(0, bytearray([0x01, 0x02, 0x03]))

    assert led.state == before
    assert received == []


def test_h6196_applies_parsed_native_notifications(
    make_led: Callable[..., LEDBLE],
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    parsed = LEDBLEState(power=True, rgb=(10, 20, 30))
    assert led._native_protocol is not None
    led._native_protocol.parse_notification = Mock(return_value=parsed)
    received: list[LEDBLEState] = []
    led.register_callback(received.append)

    led._notification_handler(0, bytearray([0x01, 0x02, 0x03]))

    assert led.state == parsed
    assert received == [parsed]


def test_h6196_native_command_without_state_only_sends_command(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command = AsyncMock()
    received: list[LEDBLEState] = []
    led.register_callback(received.append)

    loop.run_until_complete(led._execute_native_command(NativeCommand((b"\x01",))))

    led._send_command.assert_awaited_once_with([b"\x01"])
    assert received == []


def test_h6196_resolve_protocol_does_not_query_state(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._send_command_while_connected = AsyncMock()

    loop.run_until_complete(led._resolve_protocol())

    led._send_command_while_connected.assert_not_awaited()
    assert led._resolve_protocol_event.is_set()


def test_h6196_update_populates_model_data_without_state_query(
    loop: asyncio.AbstractEventLoop, make_led: Callable[..., LEDBLE]
) -> None:
    led = make_led(name="ihoment_H6196_F23C")
    led._ensure_connected = AsyncMock()
    led._send_command_while_connected = AsyncMock()

    loop.run_until_complete(led.update())

    led._ensure_connected.assert_awaited_once()
    led._send_command_while_connected.assert_not_awaited()
    assert led.model_num == GOVEE_H6196_MODEL_NUM
    assert led.model_data.description == "Govee H6196 RGB Controller"
