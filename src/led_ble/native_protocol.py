from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from flux_led.const import COLOR_MODE_RGB

from .color import calculate_brightness, rgb_unscaled
from .govee import (
    GOVEE_H6196_MODEL_NUM,
    UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC,
    build_h6196_brightness_packet,
    build_h6196_power_packet,
    build_h6196_rgb_packet,
    is_h6196_light_name,
)
from .model_db import LEDBLEModel
from .models import LEDBLEState

H6196_MODEL_DATA = LEDBLEModel(
    model_num=GOVEE_H6196_MODEL_NUM,
    models=["ihoment_H6196"],
    description="Govee H6196 RGB Controller",
    protocols=[],
    color_modes={COLOR_MODE_RGB},
)


@dataclass(frozen=True)
class NativeCommand:
    """A native protocol command and the optimistic state it implies."""

    commands: tuple[bytes, ...] = ()
    state: LEDBLEState | None = None


class NativeProtocol(Protocol):
    """Protocol for BLE LED devices that do not speak the Flux LED protocol."""

    model_data: LEDBLEModel
    read_characteristics: Sequence[str]
    write_characteristics: Sequence[str]

    def initial_state(self, state: LEDBLEState) -> LEDBLEState:
        """Return initial state once the protocol is resolved."""

    def update(self, state: LEDBLEState) -> NativeCommand:
        """Return the update command."""

    def set_power(self, state: LEDBLEState, is_on: bool) -> NativeCommand:
        """Return a power command."""

    def set_brightness(self, state: LEDBLEState, brightness: int) -> NativeCommand:
        """Return a brightness command."""

    def set_rgb(self, state: LEDBLEState, rgb: tuple[int, int, int]) -> NativeCommand:
        """Return an RGB command."""

    def set_rgbw(
        self, state: LEDBLEState, rgbw: tuple[int, int, int, int]
    ) -> NativeCommand:
        """Return an RGBW command."""

    def set_white(self, state: LEDBLEState, brightness: int) -> NativeCommand:
        """Return a white command."""

    def parse_notification(
        self, state: LEDBLEState, data: bytearray
    ) -> LEDBLEState | None:
        """Parse a notification into a new state."""

    @property
    def effect(self) -> str | None:
        """Return the current effect."""

    @property
    def effect_list(self) -> list[str]:
        """Return supported effects."""


class GoveeH6196Protocol:
    """Native protocol support for Govee H6196/iHoment BLE light strips."""

    model_data: LEDBLEModel = H6196_MODEL_DATA
    read_characteristics: Sequence[str] = ()
    write_characteristics: Sequence[str] = (UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC,)

    def initial_state(self, state: LEDBLEState) -> LEDBLEState:
        """Return initial state once the protocol is resolved."""
        return replace(state, model_num=GOVEE_H6196_MODEL_NUM)

    def update(self, state: LEDBLEState) -> NativeCommand:
        """Return the update command."""
        return NativeCommand(state=self.initial_state(state))

    def set_power(self, state: LEDBLEState, is_on: bool) -> NativeCommand:
        """Return a power command."""
        initial_state = self.initial_state(state)
        return NativeCommand(
            (build_h6196_power_packet(is_on),),
            replace(initial_state, power=is_on),
        )

    def set_brightness(self, state: LEDBLEState, brightness: int) -> NativeCommand:
        """Return a brightness command."""
        initial_state = self.initial_state(state)
        rgb = rgb_unscaled(state.rgb) if any(state.rgb) else (255, 255, 255)
        new_state = replace(
            initial_state,
            rgb=calculate_brightness(rgb, brightness),
        )
        return NativeCommand((build_h6196_brightness_packet(brightness),), new_state)

    def set_rgb(self, state: LEDBLEState, rgb: tuple[int, int, int]) -> NativeCommand:
        """Return an RGB command."""
        initial_state = self.initial_state(state)
        return NativeCommand(
            (build_h6196_rgb_packet(rgb),),
            replace(initial_state, rgb=rgb, w=0, preset_pattern=0),
        )

    def set_rgbw(
        self, state: LEDBLEState, rgbw: tuple[int, int, int, int]
    ) -> NativeCommand:
        """Return an RGBW command."""
        rgb = rgbw[:3] if any(rgbw[:3]) else (rgbw[3], rgbw[3], rgbw[3])
        return self.set_rgb(state, rgb)

    def set_white(self, state: LEDBLEState, brightness: int) -> NativeCommand:
        """Return a white command."""
        return self.set_rgb(state, (brightness, brightness, brightness))

    def parse_notification(
        self, state: LEDBLEState, data: bytearray
    ) -> LEDBLEState | None:
        """Parse a notification into a new state."""
        return None

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @property
    def effect_list(self) -> list[str]:
        """Return supported effects."""
        return []


def native_protocol_for_device(
    ble_device: BLEDevice, advertisement_data: AdvertisementData | None
) -> NativeProtocol | None:
    """Return a native protocol for a discovered device."""
    advertisement_name = advertisement_data.local_name if advertisement_data else None
    if is_h6196_light_name(ble_device.name) or is_h6196_light_name(advertisement_name):
        return GoveeH6196Protocol()
    return None
