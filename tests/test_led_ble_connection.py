"""Tests for the connection / command-dispatch lifecycle.

These exercise the disconnect bookkeeping and the send pipeline by mocking the
bleak client and the lower-level locked sender, without a real BLE backend.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from bleak.exc import BleakDBusError, BleakError
from bleak_retry_connector import BleakNotFoundError

from led_ble.const import STATE_COMMAND
from led_ble.exceptions import CharacteristicMissingError

# A model_num / version that resolves to a real flux_led protocol class.
KNOWN_MODEL = 0xE3


def test_internal_address_property(led):
    assert led._address == led.address == "AA:BB:CC:DD:EE:FF"


def test_set_rgb_applies_brightness(loop, led):
    led._protocol = Mock()
    led._protocol.construct_levels_change.return_value = [b"\x02"]
    led._send_command = AsyncMock()
    loop.run_until_complete(led.set_rgb((255, 0, 0), brightness=64))
    # Brightness scaling dims the stored color away from full red.
    assert led.rgb != (255, 0, 0)
    assert led.rgb[0] <= 64


# ---------------------------------------------------------------------------
# Disconnect timer / lifecycle
# ---------------------------------------------------------------------------


def test_reset_disconnect_timer_schedules_and_clears_expected_flag(loop, led):
    led._expected_disconnect = True
    led._reset_disconnect_timer()
    try:
        assert led._disconnect_timer is not None
        assert led._expected_disconnect is False
    finally:
        led._disconnect_timer.cancel()


def test_reset_disconnect_timer_cancels_previous(loop, led):
    led._reset_disconnect_timer()
    first = led._disconnect_timer
    led._reset_disconnect_timer()
    try:
        assert first.cancelled()
        assert led._disconnect_timer is not first
    finally:
        led._disconnect_timer.cancel()


def test_disconnected_callback_expected(led):
    led._expected_disconnect = True
    # Should not raise; expected disconnects are logged at debug only.
    led._disconnected(Mock())


def test_disconnected_callback_unexpected(led):
    led._expected_disconnect = False
    led._disconnected(Mock())


def test_disconnect_schedules_execution(loop, led):
    led._execute_timed_disconnect = AsyncMock()
    led._disconnect_timer = Mock()

    async def run():
        led._disconnect()
        await asyncio.sleep(0)

    loop.run_until_complete(run())
    assert led._disconnect_timer is None
    led._execute_timed_disconnect.assert_awaited_once()


def test_execute_timed_disconnect_delegates(loop, led):
    led._execute_disconnect = AsyncMock()
    loop.run_until_complete(led._execute_timed_disconnect())
    led._execute_disconnect.assert_awaited_once()


def test_execute_disconnect_with_connected_client(loop, led):
    client = Mock()
    client.is_connected = True
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    read_char = Mock()
    led._client = client
    led._read_char = read_char
    led._write_char = Mock()

    loop.run_until_complete(led._execute_disconnect())

    assert led._expected_disconnect is True
    assert led._client is None
    assert led._read_char is None
    assert led._write_char is None
    client.stop_notify.assert_awaited_once_with(read_char)
    client.disconnect.assert_awaited_once()


def test_execute_disconnect_with_no_client(loop, led):
    led._client = None
    # Should be a no-op beyond resetting flags.
    loop.run_until_complete(led._execute_disconnect())
    assert led._expected_disconnect is True
    assert led._client is None


# ---------------------------------------------------------------------------
# Send pipeline
# ---------------------------------------------------------------------------


def test_send_command_wraps_single_command_in_list(loop, led):
    led._ensure_connected = AsyncMock()
    led._resolve_protocol = AsyncMock()
    led._send_command_while_connected = AsyncMock()
    loop.run_until_complete(led._send_command(b"\x01"))
    args, _ = led._send_command_while_connected.await_args
    assert args[0] == [b"\x01"]


def test_send_command_passes_through_list(loop, led):
    led._ensure_connected = AsyncMock()
    led._resolve_protocol = AsyncMock()
    led._send_command_while_connected = AsyncMock()
    loop.run_until_complete(led._send_command([b"\x01", b"\x02"]))
    args, _ = led._send_command_while_connected.await_args
    assert args[0] == [b"\x01", b"\x02"]


def test_send_command_while_connected_success(loop, led):
    led._send_command_locked = AsyncMock()
    loop.run_until_complete(led._send_command_while_connected([b"\x01"]))
    led._send_command_locked.assert_awaited_once_with([b"\x01"])


def test_send_command_while_connected_reraises_not_found(loop, led):
    led._send_command_locked = AsyncMock(side_effect=BleakNotFoundError)
    with pytest.raises(BleakNotFoundError):
        loop.run_until_complete(led._send_command_while_connected([b"\x01"]))


def test_send_command_while_connected_reraises_characteristic_missing(loop, led):
    led._send_command_locked = AsyncMock(
        side_effect=CharacteristicMissingError("missing")
    )
    with pytest.raises(CharacteristicMissingError):
        loop.run_until_complete(led._send_command_while_connected([b"\x01"]))


# ---------------------------------------------------------------------------
# Protocol resolution
# ---------------------------------------------------------------------------


def test_resolve_protocol_returns_early_when_resolved(loop, led):
    led._resolve_protocol_event.set()
    led._send_command_while_connected = AsyncMock()
    loop.run_until_complete(led._resolve_protocol())
    led._send_command_while_connected.assert_not_awaited()


def test_resolve_protocol_queries_then_waits(loop, led):
    async def _send(_commands):
        led._resolve_protocol_event.set()

    led._send_command_while_connected = AsyncMock(side_effect=_send)
    loop.run_until_complete(led._resolve_protocol())
    led._send_command_while_connected.assert_awaited_once_with([STATE_COMMAND])
    assert led._resolve_protocol_event.is_set()


# ---------------------------------------------------------------------------
# _ensure_connected
# ---------------------------------------------------------------------------


def test_ensure_connected_returns_early_when_already_connected(loop, led):
    client = Mock()
    client.is_connected = True
    led._client = client
    led._reset_disconnect_timer = Mock()
    loop.run_until_complete(led._ensure_connected())
    led._reset_disconnect_timer.assert_called_once()
    # The existing client is kept; no reconnection attempt was made.
    assert led._client is client


def test_ensure_connected_happy_path(loop, led, monkeypatch):
    client = Mock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.services = Mock()
    monkeypatch.setattr(
        "led_ble.led_ble.establish_connection", AsyncMock(return_value=client)
    )
    led._resolve_characteristics = Mock(return_value=True)
    led._resolve_protocol = AsyncMock()
    led._protocol = None

    loop.run_until_complete(led._ensure_connected())
    try:
        assert led._client is client
        client.start_notify.assert_awaited_once()
        led._resolve_protocol.assert_awaited_once()
    finally:
        if led._disconnect_timer:
            led._disconnect_timer.cancel()


def test_ensure_connected_retries_then_raises_when_chars_missing(
    loop, led, monkeypatch
):
    client = Mock()
    client.is_connected = True
    client.clear_cache = AsyncMock()
    client.disconnect = AsyncMock()
    monkeypatch.setattr(
        "led_ble.led_ble.establish_connection", AsyncMock(return_value=client)
    )
    led._resolve_characteristics = Mock(return_value=False)

    with pytest.raises(CharacteristicMissingError):
        loop.run_until_complete(led._ensure_connected())

    # First attempt clears the service cache and reconnects, second gives up.
    client.clear_cache.assert_awaited_once()
    assert client.disconnect.await_count == 2


# ---------------------------------------------------------------------------
# Extra branch coverage
# ---------------------------------------------------------------------------


def test_notification_resolves_protocol_only_once(led):
    packet = bytearray([0x81, KNOWN_MODEL, 0x23, 0x01, 0x02, 0x03, 10, 20, 30, 40, 5])
    led._notification_handler(0, packet)
    first_protocol = led._protocol
    # A second packet must not re-resolve the protocol.
    led._notification_handler(0, packet)
    assert led._protocol is first_protocol


def test_execute_disconnect_swallows_stop_notify_error(loop, led):
    client = Mock()
    client.is_connected = True
    client.stop_notify = AsyncMock(side_effect=BleakError("boom"))
    client.disconnect = AsyncMock()
    led._client = client
    led._read_char = Mock()

    # stop_notify failing must not prevent disconnect.
    loop.run_until_complete(led._execute_disconnect())
    client.disconnect.assert_awaited_once()
    assert led._client is None


def test_send_command_while_connected_reraises_bleak_exceptions(loop, led):
    led._send_command_locked = AsyncMock(side_effect=BleakError("comm failed"))
    with pytest.raises(BleakError):
        loop.run_until_complete(led._send_command_while_connected([b"\x01"]))


# ---------------------------------------------------------------------------
# _send_command_locked error recovery
#
# The locked sender must disconnect (to reset state for a later retry) and
# re-raise on a BLE error. The retry decorator wraps this method, so we
# neutralise asyncio.sleep to keep the backoff/retry delays out of the test.
# ---------------------------------------------------------------------------


def test_send_command_locked_disconnects_on_dbus_error(loop, led, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    led._execute_command_locked = AsyncMock(
        side_effect=BleakDBusError("org.bluez.Error.Failed", [])
    )
    led._execute_disconnect = AsyncMock()

    with pytest.raises(BleakDBusError):
        loop.run_until_complete(led._send_command_locked([b"\x01"]))

    # A DBus error backs off then disconnects before propagating.
    led._execute_disconnect.assert_awaited()


def test_send_command_locked_disconnects_on_bleak_error(loop, led, monkeypatch):
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    led._execute_command_locked = AsyncMock(side_effect=BleakError("boom"))
    led._execute_disconnect = AsyncMock()

    with pytest.raises(BleakError):
        loop.run_until_complete(led._send_command_locked([b"\x01"]))

    led._execute_disconnect.assert_awaited()


# ---------------------------------------------------------------------------
# Lock guards (concurrency edge paths)
# ---------------------------------------------------------------------------


def test_ensure_connected_double_checked_lock(loop, led, monkeypatch):
    """A peer that connects while we wait for the lock is honoured on recheck.

    Exercises the "connection already in progress" log and the second
    ``is_connected`` check performed *after* the lock is acquired.
    """
    led._reset_disconnect_timer = Mock()
    # If the post-lock recheck fails to short-circuit, we'd fall through to a
    # real reconnect — make that loud rather than hanging.
    monkeypatch.setattr(
        "led_ble.led_ble.establish_connection",
        AsyncMock(side_effect=AssertionError("should not reconnect")),
    )
    client = Mock()
    client.is_connected = True

    async def run():
        await led._connect_lock.acquire()
        task = asyncio.ensure_future(led._ensure_connected())
        # Let the task log the in-progress branch and block acquiring the lock.
        await asyncio.sleep(0)
        # A concurrent connection lands before we release the lock.
        led._client = client
        led._connect_lock.release()
        await task

    loop.run_until_complete(run())

    assert led._client is client
    led._reset_disconnect_timer.assert_called()


def test_send_command_while_connected_waits_for_operation_lock(loop, led):
    """The operation-in-progress branch logs, then proceeds once the lock frees."""
    led._send_command_locked = AsyncMock()

    async def run():
        await led._operation_lock.acquire()
        task = asyncio.ensure_future(led._send_command_while_connected([b"\x01"]))
        # Let the task log the in-progress branch and block on the lock.
        await asyncio.sleep(0)
        led._operation_lock.release()
        await task

    loop.run_until_complete(run())
    led._send_command_locked.assert_awaited_once_with([b"\x01"])


# ---------------------------------------------------------------------------
# _ensure_connected / _execute_disconnect extra branches
# ---------------------------------------------------------------------------


def test_ensure_connected_skips_protocol_resolve_when_already_set(
    loop, led, monkeypatch
):
    client = Mock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.services = Mock()
    monkeypatch.setattr(
        "led_ble.led_ble.establish_connection", AsyncMock(return_value=client)
    )
    led._resolve_characteristics = Mock(return_value=True)
    led._resolve_protocol = AsyncMock()
    led._protocol = Mock()  # already resolved from a prior connection

    loop.run_until_complete(led._ensure_connected())
    try:
        led._resolve_protocol.assert_not_awaited()
    finally:
        if led._disconnect_timer:
            led._disconnect_timer.cancel()


def test_execute_disconnect_without_read_char_skips_stop_notify(loop, led):
    client = Mock()
    client.is_connected = True
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    led._client = client
    led._read_char = None  # no characteristic to unsubscribe from

    loop.run_until_complete(led._execute_disconnect())

    client.stop_notify.assert_not_awaited()
    client.disconnect.assert_awaited_once()
    assert led._client is None
