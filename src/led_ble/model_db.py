from __future__ import annotations

from dataclasses import dataclass

from flux_led.const import COLOR_MODE_RGBW, COLOR_MODES_RGB_W
from flux_led.models_db import MinVersionProtocol
from flux_led.protocol import PROTOCOL_LEDENET_ORIGINAL_RGBW

DEFAULT_MODEL = 0xE3


@dataclass(frozen=True)
class LEDBLEModel:

    model_num: int  # The model number aka byte 1
    models: list[str]  # The model names from discovery
    description: str  # Description of the model ({type} {color_mode})
    protocols: list[
        MinVersionProtocol
    ]  # The device protocols, must be ordered highest version to lowest version
    color_modes: set[
        str
    ]  # The color modes to use if there is no mode_to_color_mode_mapping

    def protocol_for_version_num(self, version_num: int) -> str:
        protocol = self.protocols[-1].protocol
        for min_version_protocol in self.protocols:
            if version_num >= min_version_protocol.min_version:
                protocol = min_version_protocol.protocol
                break
        return protocol


MODELS = [
    LEDBLEModel(
        model_num=0x04,
        models=["Triones:C10511000166"],
        description="Controller RGB&W",
        protocols=[
            MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW),
        ],
        color_modes={COLOR_MODE_RGBW},  # Formerly rgbwcapable
    ),
    LEDBLEModel(
        model_num=0x10,
        models=["Dream~MAC"],
        description="Controller Dream",
        protocols=[
            MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW),
        ],
        color_modes=COLOR_MODES_RGB_W,  # Formerly rgbwcapable
    ),
    LEDBLEModel(
        model_num=0x15,
        models=["LEDBlue-C2AF4BD5"],
        description="Bulb RGB/W",
        protocols=[
            MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW),
        ],
        color_modes=COLOR_MODES_RGB_W,  # Formerly rgbwcapable
    ),
    LEDBLEModel(
        model_num=0x54,
        models=["LEDBLE-DE1254F9"],
        description="Controller RGB&W",
        protocols=[
            MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW),
        ],
        color_modes=COLOR_MODES_RGB_W,  # Formerly rgbwcapable
    ),
    LEDBLEModel(
        model_num=0xE3,
        models=["QHM-095F"],
        description="Controller RGB/W",
        protocols=[
            MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW),
        ],
        color_modes=COLOR_MODES_RGB_W,  # Formerly rgbwcapable
    ),
]


MODEL_MAP: dict[int, LEDBLEModel] = {model.model_num: model for model in MODELS}


def get_model(model_num: int, fallback_protocol: str | None = None) -> LEDBLEModel:
    """Return the LEDNETModel for the model_num."""
    return MODEL_MAP.get(
        model_num,
        _unknown_ledble_model(
            model_num, fallback_protocol or PROTOCOL_LEDENET_ORIGINAL_RGBW
        ),
    )


def is_known_model(model_num: int) -> bool:
    """Return true of the model is known."""
    return model_num in MODEL_MAP


UNKNOWN_MODEL = "Unknown Model"


def _unknown_ledble_model(model_num: int, fallback_protocol: str) -> LEDBLEModel:
    """Create a LEDNETModel for an unknown model_num."""
    return LEDBLEModel(
        model_num=model_num,
        models=[],
        description=UNKNOWN_MODEL,
        protocols=[MinVersionProtocol(0, fallback_protocol)],
        color_modes=COLOR_MODES_RGB_W,
    )


def get_model_description(model_num: int) -> str:
    """Return the description for a model."""
    return get_model(model_num).description
