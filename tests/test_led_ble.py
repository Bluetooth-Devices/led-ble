"""Tests for the LEDBLE device class.

These cover the pure / mockable logic: properties, the notification parser,
effect handling, command construction dispatch, validation, and the small
amount of connection bookkeeping that does not require a real bleak backend.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest
from flux_led.const import LevelWriteMode
from flux_led.pattern import EFFECT_ID_NAME, EFFECT_LIST, PresetPattern

from led_ble import LEDBLEState
from led_ble.const import (
    POSSIBLE_READ_CHARACTERISTIC_UUIDS,
    POSSIBLE_WRITE_CHARACTERISTIC_UUIDS,
)
from led_ble.exceptions import CharacteristicMissingError
from led_ble.led_ble import DREAM_EFFECT_LIST, DREAM_EFFECTS

from .conftest import FakeAdvertisement, FakeBLEDevice, FakeServices

# A model_num / version that resolves to a real flux_led protocol class.
KNOWN_MODEL = 0xE3


def _protocol_mock() -> Mock:
    """A protocol whose construct_* methods return sentinel command lists."""
    protocol = Mock()
    protocol.construct_state_change.return_value = [b"\x01"]
    protocol.construct_levels_change.return_value = [b"\x02"]
    protocol.construct_state_query.return_value = b"\x03"
    protocol.construct_preset_pattern.return_value = bytearray(b"\x04")
    return protocol


# ---------------------------------------------------------------------------
# Identity / addressing properties
# ---------------------------------------------------------------------------


def test_address_property(led):
    assert led.address == "AA:BB:CC:DD:EE:FF"


def test_name_uses_device_name(led):
    assert led.name == "LEDnet"


def test_name_falls_back_to_address(make_led):
    led = make_led(name=None)
    assert led.name == "AA:BB:CC:DD:EE:FF"


def test_rssi_none_without_advertisement(led):
    assert led.rssi is None


def test_rssi_from_advertisement(make_led):
    led = make_led(advertisement=FakeAdvertisement(rssi=-42))
    assert led.rssi == -42


def test_set_ble_device_and_advertisement_data(led):
    new_device = FakeBLEDevice(address="11:22:33:44:55:66", name="New")
    adv = FakeAdvertisement(rssi=-10)
    led.set_ble_device_and_advertisement_data(new_device, adv)
    assert led.address == "11:22:33:44:55:66"
    assert led.name == "New"
    assert led.rssi == -10


# ---------------------------------------------------------------------------
# State-derived properties
# ---------------------------------------------------------------------------


def test_state_property_defaults(led):
    assert led.state == LEDBLEState()
    assert led.on is False
    assert led.rgb == (0, 0, 0)
    assert led.w == 0


def test_color_and_meta_properties_reflect_state(led):
    led._state = LEDBLEState(
        power=True,
        rgb=(10, 20, 30),
        w=40,
        model_num=0x54,
        preset_pattern=37,
        mode=2,
        speed=3,
        version_num=8,
    )
    assert led.on is True
    assert led.rgb == (10, 20, 30)
    assert led.w == 40
    assert led.model_num == 0x54
    assert led.preset_pattern_num == 37
    assert led.mode == 2
    assert led.speed == 3
    assert led.version_num == 8


def test_brightness_uses_white_when_present(led):
    led._state = replace(led._state, w=123, rgb=(255, 0, 0))
    assert led.brightness == 123


def test_brightness_uses_rgb_value_when_no_white(led):
    led._state = replace(led._state, w=0, rgb=(255, 0, 0))
    # value channel of pure red at full saturation is 255.
    assert led.brightness == 255


def test_brightness_zero_when_off_and_dark(led):
    assert led.brightness == 0


def test_rgb_unscaled_normalizes_to_full_value(led):
    led._state = replace(led._state, rgb=(128, 0, 0))
    # Scaling a dim red back up to full brightness yields pure red.
    assert led.rgb_unscaled == (255, 0, 0)


# ---------------------------------------------------------------------------
# Dream detection / effects
# ---------------------------------------------------------------------------


def test_dream_true_for_dream_model(led):
    led._state = replace(led._state, model_num=0x10)
    assert led.dream is True


def test_dream_true_from_advertisement_local_name(make_led):
    led = make_led(advertisement=FakeAdvertisement(local_name="Dream-1234"))
    assert led.dream is True


def test_dream_false_otherwise(led):
    assert led.dream is False


def test_effect_list_normal(led):
    assert led.effect_list == EFFECT_LIST


def test_effect_list_dream(led):
    led._state = replace(led._state, model_num=0x10)
    assert led.effect_list == DREAM_EFFECT_LIST
    assert len(DREAM_EFFECT_LIST) == 255


def test_effect_named_for_known_preset(led):
    preset_id, name = next(iter(EFFECT_ID_NAME.items()))
    led._state = replace(led._state, preset_pattern=preset_id)
    assert led.effect == name


def test_effect_none_for_unknown_preset(led):
    led._state = replace(led._state, preset_pattern=0)
    assert led.effect is None


def test_effect_dream_reports_mode_based_name(led):
    led._state = replace(led._state, model_num=0x10, preset_pattern=0, mode=4)
    assert led.effect == "Effect 5"


def test_effect_to_pattern_normal(led):
    name = EFFECT_LIST[0]
    assert led._effect_to_pattern(name) == PresetPattern.str_to_val(name)


def test_effect_to_pattern_dream_valid(led):
    led._state = replace(led._state, model_num=0x10)
    assert led._effect_to_pattern("Effect 1") == DREAM_EFFECTS["Effect 1"]


def test_effect_to_pattern_dream_invalid_raises(led):
    led._state = replace(led._state, model_num=0x10)
    with pytest.raises(ValueError, match="not valid"):
        led._effect_to_pattern("Nope")


# ---------------------------------------------------------------------------
# Notification handler (pure packet parsing)
# ---------------------------------------------------------------------------


def test_notification_power_on_short_packet(led):
    led._notification_handler(0, bytearray([0xCC, 0x23, 0x00, 0x00]))
    assert led.on is True


def test_notification_power_off_short_packet(led):
    led._state = replace(led._state, power=True)
    led._notification_handler(0, bytearray([0xCC, 0x24, 0x00, 0x00]))
    assert led.on is False


def test_notification_ignores_too_short_packet(led):
    before = led.state
    led._notification_handler(0, bytearray([0x81, 0x00, 0x23, 0x01, 0x02]))
    assert led.state == before


def test_notification_full_packet_parses_all_fields(led):
    packet = bytearray([0x81, KNOWN_MODEL, 0x23, 0x01, 0x02, 0x03, 10, 20, 30, 40, 5])
    led._notification_handler(0, packet)
    state = led.state
    assert state.power is True
    assert state.model_num == KNOWN_MODEL
    assert state.preset_pattern == 0x01
    assert state.mode == 0x02
    assert state.speed == 0x03
    assert state.rgb == (10, 20, 30)
    assert state.w == 40
    assert state.version_num == 5


def test_notification_resolves_protocol_once(led):
    packet = bytearray([0x81, KNOWN_MODEL, 0x23, 0x01, 0x02, 0x03, 10, 20, 30, 40, 5])
    led._notification_handler(0, packet)
    assert led._resolve_protocol_event.is_set()
    assert led._protocol is not None
    assert led.model_data.model_num == KNOWN_MODEL


def test_notification_fires_callbacks(led):
    received: list[LEDBLEState] = []
    led.register_callback(received.append)
    packet = bytearray([0x81, KNOWN_MODEL, 0x23, 0x01, 0x02, 0x03, 10, 20, 30, 40, 5])
    led._notification_handler(0, packet)
    assert len(received) == 1
    assert received[0].rgb == (10, 20, 30)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------


def test_register_and_unregister_callback(led):
    calls: list[LEDBLEState] = []
    unregister = led.register_callback(calls.append)
    led._fire_callbacks()
    assert len(calls) == 1
    unregister()
    led._fire_callbacks()
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Protocol resolution helpers
# ---------------------------------------------------------------------------


def test_set_protocol_valid(led):
    led._set_protocol("LEDENET_ORIGINAL_RGBW")
    assert led._protocol is not None


def test_set_protocol_invalid_raises(led):
    with pytest.raises(ValueError, match="Invalid protocol"):
        led._set_protocol("NOT_A_PROTOCOL")


# ---------------------------------------------------------------------------
# Characteristic resolution
# ---------------------------------------------------------------------------


def test_resolve_characteristics_found(led):
    read_uuid = POSSIBLE_READ_CHARACTERISTIC_UUIDS[0]
    write_uuid = POSSIBLE_WRITE_CHARACTERISTIC_UUIDS[0]
    read_char, write_char = object(), object()
    services = FakeServices({read_uuid: read_char, write_uuid: write_char})
    assert led._resolve_characteristics(services) is True
    assert led._read_char is read_char
    assert led._write_char is write_char


def test_resolve_characteristics_missing(led):
    assert led._resolve_characteristics(FakeServices({})) is False
    assert led._read_char is None
    assert led._write_char is None


def test_resolve_characteristics_resets_stale_chars(led):
    """A partial resolve must not leak a stale char into the next attempt.

    Simulates the reconnect path: attempt 0 resolves only the read char,
    attempt 1 sees services that only resolve the write char. Without a
    reset, the stale read char from the dead client would satisfy the
    read-and-write check and return True against mismatched clients.
    """
    read_uuid = POSSIBLE_READ_CHARACTERISTIC_UUIDS[0]
    write_uuid = POSSIBLE_WRITE_CHARACTERISTIC_UUIDS[0]
    stale_read = object()

    # Attempt 0: only the read char resolves -> partial, returns False.
    assert led._resolve_characteristics(FakeServices({read_uuid: stale_read})) is False
    assert led._read_char is stale_read

    # Attempt 1: fresh services expose only the write char.
    fresh_write = object()
    assert (
        led._resolve_characteristics(FakeServices({write_uuid: fresh_write})) is False
    )
    # The stale read char must have been cleared, not retained.
    assert led._read_char is None
    assert led._write_char is fresh_write


# ---------------------------------------------------------------------------
# Brightness math / preset generation
# ---------------------------------------------------------------------------


def test_calculate_brightness_returns_ints(led):
    result = led._calculate_brightness((255, 0, 0), 128)
    assert len(result) == 3
    assert all(isinstance(v, int) for v in result)


def test_generate_preset_pattern_rejects_out_of_range_brightness(led):
    led._set_protocol("LEDENET_ORIGINAL_RGBW")
    valid_pattern = PresetPattern.str_to_val(EFFECT_LIST[0])
    with pytest.raises(ValueError, match="between 1 and 100"):
        led._generate_preset_pattern(valid_pattern, 50, 0)
    with pytest.raises(ValueError, match="between 1 and 100"):
        led._generate_preset_pattern(valid_pattern, 50, 101)


def test_generate_preset_pattern_normal(led):
    led._set_protocol("LEDENET_ORIGINAL_RGBW")
    valid_pattern = PresetPattern.str_to_val(EFFECT_LIST[0])
    result = led._generate_preset_pattern(valid_pattern, 50, 100)
    assert isinstance(result, (bytes, bytearray))


def test_generate_preset_pattern_dream(led):
    led._state = replace(led._state, model_num=0x10)
    result = led._generate_preset_pattern(5, 50, 100)
    assert result[0] == 0x9E
    assert result[2] == 5
    assert result[-1] == 0xE9


# ---------------------------------------------------------------------------
# Async command methods (mock the transport)
# ---------------------------------------------------------------------------


def test_turn_on(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.turn_on())
    assert led.on is True
    led._send_command.assert_awaited_once_with([b"\x01"])


def test_turn_off(loop, led):
    led._state = replace(led._state, power=True)
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.turn_off())
    assert led.on is False


def test_set_rgb_updates_state(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_rgb((10, 20, 30)))
    assert led.rgb == (10, 20, 30)
    assert led.w == 0
    led._protocol.construct_levels_change.assert_called_once()
    _, kwargs = led._protocol.construct_levels_change.call_args
    assert kwargs["write_mode"] == LevelWriteMode.COLORS


def test_set_rgb_rejects_out_of_range(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    with pytest.raises(ValueError, match="300 is outside"):
        loop.run_until_complete(led.set_rgb((10, 20, 300)))
    led._send_command.assert_not_awaited()


def test_set_rgbw_updates_state(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_rgbw((10, 20, 30, 40)))
    assert led.rgb == (10, 20, 30)
    assert led.w == 40


def test_set_rgbw_rejects_out_of_range(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    with pytest.raises(ValueError, match="999 is outside"):
        loop.run_until_complete(led.set_rgbw((10, 20, 30, 999)))
    led._send_command.assert_not_awaited()


def test_set_white_updates_state(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_white(200))
    assert led.w == 200
    assert led.rgb == (0, 0, 0)


def test_set_white_rejects_out_of_range(loop, led):
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    with pytest.raises(ValueError, match="256 is outside"):
        loop.run_until_complete(led.set_white(256))
    led._send_command.assert_not_awaited()


def test_set_brightness_uses_white_path(loop, led):
    led._state = replace(led._state, w=100)
    led.set_white = AsyncMock()
    loop.run_until_complete(led.set_brightness(150))
    led.set_white.assert_awaited_once_with(150)


def test_set_brightness_uses_rgb_path(loop, led):
    led._state = replace(led._state, w=0, rgb=(255, 0, 0))
    led.set_rgb = AsyncMock()
    loop.run_until_complete(led.set_brightness(150))
    led.set_rgb.assert_awaited_once()


def test_set_brightness_uses_effect_path(loop, led):
    led._state = replace(led._state, w=0, preset_pattern=next(iter(EFFECT_ID_NAME)))
    led.async_set_effect = AsyncMock()
    loop.run_until_complete(led.set_brightness(255))
    led.async_set_effect.assert_awaited_once()


def test_async_set_preset_pattern_normal_state(loop, led):
    led._send_command = AsyncMock()
    led._generate_preset_pattern = Mock(return_value=bytearray(b"\x04"))
    loop.run_until_complete(led.async_set_preset_pattern(37, 50, 100))
    assert led.preset_pattern_num == 37


def test_async_set_preset_pattern_dream_state(loop, led):
    led._state = replace(led._state, model_num=0x10)
    led._send_command = AsyncMock()
    led._generate_preset_pattern = Mock(return_value=bytearray(b"\x04"))
    loop.run_until_complete(led.async_set_preset_pattern(7, 50, 100))
    assert led.preset_pattern_num == 0
    assert led.mode == 7


def test_async_set_effect_dispatches_pattern(loop, led):
    led.async_set_preset_pattern = AsyncMock()
    name = EFFECT_LIST[0]
    loop.run_until_complete(led.async_set_effect(name, 50, 100))
    led.async_set_preset_pattern.assert_awaited_once_with(
        PresetPattern.str_to_val(name), 50, 100
    )


def test_update_sends_state_query(loop, led):
    led._ensure_connected = AsyncMock()
    led._resolve_protocol = AsyncMock()
    led._protocol = _protocol_mock()
    led._send_command = AsyncMock()
    loop.run_until_complete(led.update())
    led._send_command.assert_awaited_once_with([b"\x03"])


def test_stop_executes_disconnect(loop, led):
    led._execute_disconnect = AsyncMock()
    loop.run_until_complete(led.stop())
    led._execute_disconnect.assert_awaited_once()


# ---------------------------------------------------------------------------
# Low-level command execution
# ---------------------------------------------------------------------------


def test_execute_command_locked_requires_read_char(loop, led):
    led._client = Mock()
    led._read_char = None
    led._write_char = Mock()
    with pytest.raises(CharacteristicMissingError, match="Read"):
        loop.run_until_complete(led._execute_command_locked([b"\x01"]))


def test_execute_command_locked_requires_write_char(loop, led):
    led._client = Mock()
    led._read_char = Mock()
    led._write_char = None
    with pytest.raises(CharacteristicMissingError, match="Write"):
        loop.run_until_complete(led._execute_command_locked([b"\x01"]))


def test_execute_command_locked_writes_each_command(loop, led):
    client = Mock()
    client.write_gatt_char = AsyncMock()
    led._client = client
    led._read_char = Mock()
    led._write_char = Mock()
    loop.run_until_complete(led._execute_command_locked([b"\x01", b"\x02"]))
    assert client.write_gatt_char.await_count == 2
