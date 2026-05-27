"""Tests for the model database (pure, hardware-free logic)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from flux_led.models_db import MinVersionProtocol
from flux_led.protocol import PROTOCOL_LEDENET_ORIGINAL_RGBW

from led_ble.model_db import (
    DEFAULT_MODEL,
    MODEL_MAP,
    MODELS,
    UNKNOWN_MODEL,
    LEDBLEModel,
    get_model,
    get_model_description,
    is_known_model,
    register_model,
)


@pytest.fixture
def restore_registry() -> Iterator[None]:
    """Snapshot and restore the global model registry around a test."""
    saved_map = dict(MODEL_MAP)
    saved_models = list(MODELS)
    try:
        yield
    finally:
        MODEL_MAP.clear()
        MODEL_MAP.update(saved_map)
        MODELS[:] = saved_models


def test_known_models_are_indexed_by_number():
    for model in MODELS:
        assert MODEL_MAP[model.model_num] is model


def test_get_model_returns_known_model():
    model = get_model(0x04)
    assert model.model_num == 0x04
    assert model.models == ["Triones:C10511000166"]
    assert model.description == "Controller RGB&W"


def test_get_model_unknown_returns_fallback_with_default_protocol():
    model = get_model(0xAB)
    assert model.model_num == 0xAB
    assert model.models == []
    assert model.description == UNKNOWN_MODEL
    assert model.protocols == [MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW)]


def test_get_model_unknown_honors_custom_fallback_protocol():
    model = get_model(0xAB, fallback_protocol="LEDENET_ORIGINAL")
    assert model.protocols == [MinVersionProtocol(0, "LEDENET_ORIGINAL")]


def test_is_known_model():
    assert is_known_model(0x04) is True
    assert is_known_model(DEFAULT_MODEL) is True
    assert is_known_model(0xAB) is False


def test_get_model_description_known_and_unknown():
    assert get_model_description(0x15) == "Bulb RGB/W"
    assert get_model_description(0xAB) == UNKNOWN_MODEL


def test_protocol_for_version_num_single_protocol():
    model = get_model(0xE3)
    # Only one protocol registered (min_version 0) -> always selected.
    assert model.protocol_for_version_num(0) == PROTOCOL_LEDENET_ORIGINAL_RGBW
    assert model.protocol_for_version_num(99) == PROTOCOL_LEDENET_ORIGINAL_RGBW


def test_register_model_adds_new_model(restore_registry):
    model = LEDBLEModel(
        model_num=0x77,
        models=["SP107E"],
        description="Custom strip",
        protocols=[MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW)],
        color_modes=set(),
    )
    previous = register_model(model)

    assert previous is None
    assert is_known_model(0x77) is True
    assert get_model(0x77) is model
    assert model in MODELS


def test_register_model_overrides_existing_and_returns_previous(restore_registry):
    original = get_model(0x04)
    replacement = LEDBLEModel(
        model_num=0x04,
        models=["Triones:override"],
        description="Overridden",
        protocols=[MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW)],
        color_modes=set(),
    )
    previous = register_model(replacement)

    assert previous is original
    assert get_model(0x04) is replacement
    assert get_model_description(0x04) == "Overridden"
    # The replaced entry must not linger in the ordered list.
    assert original not in MODELS
    assert MODELS.count(replacement) == 1


def test_register_model_makes_formerly_unknown_model_resolve(restore_registry):
    assert is_known_model(0xAB) is False
    assert get_model(0xAB).description == UNKNOWN_MODEL

    register_model(
        LEDBLEModel(
            model_num=0xAB,
            models=["MyLight"],
            description="My custom light",
            protocols=[MinVersionProtocol(0, "LEDENET_ORIGINAL")],
            color_modes=set(),
        )
    )

    resolved = get_model(0xAB)
    assert resolved.description == "My custom light"
    assert resolved.protocol_for_version_num(0) == "LEDENET_ORIGINAL"


def test_protocol_for_version_num_selects_by_min_version():
    model = LEDBLEModel(
        model_num=0x99,
        models=["test"],
        description="test",
        protocols=[
            MinVersionProtocol(5, "LEDENET_ORIGINAL_RGBW"),
            MinVersionProtocol(0, "LEDENET_ORIGINAL"),
        ],
        color_modes=set(),
    )
    # Version >= 5 -> first (highest) protocol.
    assert model.protocol_for_version_num(7) == "LEDENET_ORIGINAL_RGBW"
    assert model.protocol_for_version_num(5) == "LEDENET_ORIGINAL_RGBW"
    # Version < 5 -> falls through to the lower protocol.
    assert model.protocol_for_version_num(4) == "LEDENET_ORIGINAL"
    assert model.protocol_for_version_num(0) == "LEDENET_ORIGINAL"


def test_protocol_for_version_num_below_all_minimums_uses_default() -> None:
    # When no protocol's min_version is satisfied, the loop completes without
    # a match and the last (lowest) protocol set before the loop is returned.
    model = LEDBLEModel(
        model_num=0x99,
        models=["test"],
        description="test",
        protocols=[
            MinVersionProtocol(5, "PROTO_HIGH"),
            MinVersionProtocol(2, "PROTO_LOW"),
        ],
        color_modes=set(),
    )
    assert model.protocol_for_version_num(1) == "PROTO_LOW"
