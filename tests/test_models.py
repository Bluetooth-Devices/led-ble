"""Tests for the LEDBLEState dataclass."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from led_ble import LEDBLEState


def test_defaults():
    state = LEDBLEState()
    assert state.power is False
    assert state.rgb == (0, 0, 0)
    assert state.w == 0
    assert state.model_num == 0
    assert state.preset_pattern == 0
    assert state.mode == 0
    assert state.speed == 0
    assert state.version_num == 0


def test_positional_construction_matches_notification_order():
    # Mirrors how _notification_handler builds the state from a packet.
    state = LEDBLEState(True, (10, 20, 30), 40, 0xE3, 1, 2, 3, 5)
    assert state.power is True
    assert state.rgb == (10, 20, 30)
    assert state.w == 40
    assert state.model_num == 0xE3
    assert state.version_num == 5


def test_is_frozen():
    state = LEDBLEState()
    with pytest.raises(FrozenInstanceError):
        state.power = True  # type: ignore[misc]


def test_replace_returns_new_instance():
    state = LEDBLEState()
    updated = replace(state, power=True)
    assert updated.power is True
    assert state.power is False
    assert updated is not state
