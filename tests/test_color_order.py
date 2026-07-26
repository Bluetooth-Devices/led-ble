"""Tests for color order / device type configuration (issue #18).

These cover the pure, mockable surface: command-byte construction for the
``set``/``get`` commands, parsing of the notification response, the derived
properties, and the enum value mapping. No bleak backend is required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from led_ble import ColorOrder, DeviceType, LEDBLEState
from led_ble.const import (
    COLOR_ORDER_QUERY,
    COLOR_ORDER_RESPONSE_PREFIX,
)


def test_enum_values_match_protocol():
    """Enum values must match the documented wire bytes (issue #18)."""
    assert (ColorOrder.RGB, ColorOrder.GRB, ColorOrder.BRG) == (1, 2, 3)
    assert (DeviceType.RGB, DeviceType.RGBW, DeviceType.RGB_AND_W) == (1, 2, 3)


def test_state_defaults_are_none():
    state = LEDBLEState()
    assert state.color_order is None
    assert state.device_type is None


def test_set_color_order_builds_command(loop, led):
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_color_order(ColorOrder.GRB, DeviceType.RGB_AND_W))
    led._send_command.assert_awaited_once_with([bytes([0x22, 0x02, 0x03, 0x33])])


def test_set_color_order_updates_state(loop, led):
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_color_order(ColorOrder.BRG, DeviceType.RGBW))
    assert led.color_order == ColorOrder.BRG
    assert led.device_type == DeviceType.RGBW


def test_set_color_order_fires_callbacks(loop, led):
    led._send_command = AsyncMock()
    seen: list[LEDBLEState] = []
    led.register_callback(seen.append)
    loop.run_until_complete(led.set_color_order(ColorOrder.RGB, DeviceType.RGB))
    assert len(seen) == 1
    assert seen[0].color_order == ColorOrder.RGB


def test_set_color_order_accepts_plain_ints(loop, led):
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_color_order(1, 2))
    led._send_command.assert_awaited_once_with([bytes([0x22, 0x01, 0x02, 0x33])])


def test_get_color_order_sends_query(loop, led):
    led._send_command = AsyncMock()
    loop.run_until_complete(led.get_color_order())
    led._send_command.assert_awaited_once_with([COLOR_ORDER_QUERY])


def test_notification_parses_color_order_response(led):
    # 0xE2 <color_order=01> <device_type=03> 0x33
    led._notification_handler(
        0, bytearray([COLOR_ORDER_RESPONSE_PREFIX, 0x01, 0x03, 0x33])
    )
    assert led.color_order == ColorOrder.RGB
    assert led.device_type == DeviceType.RGB_AND_W


def test_notification_color_order_response_fires_callbacks(led):
    seen: list[LEDBLEState] = []
    led.register_callback(seen.append)
    led._notification_handler(
        0, bytearray([COLOR_ORDER_RESPONSE_PREFIX, 0x02, 0x01, 0x33])
    )
    assert len(seen) == 1
    assert seen[0].color_order == ColorOrder.GRB
    assert seen[0].device_type == DeviceType.RGB


def test_notification_color_order_does_not_clobber_other_state(led):
    led._notification_handler(
        0, bytearray([COLOR_ORDER_RESPONSE_PREFIX, 0x03, 0x02, 0x33])
    )
    # The short color-order reply must not reset RGB/power to defaults.
    assert led.color_order == ColorOrder.BRG
    assert led.rgb == (0, 0, 0)
    assert led.on is False
