"""Tests for the model database (pure, hardware-free logic)."""

from __future__ import annotations

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
)


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
