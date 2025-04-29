from __future__ import annotations
import colorsys
from math import floor
from flux_led.protocol import ProtocolBase
from led_ble.led_ble import LevelWriteMode


class ProtocolFairy(ProtocolBase):
    """Protocol for Hello Fairy devices."""

    @property
    def name(self) -> str:
        """The name of the protocol."""
        return "Fairy"

    def construct_state_query(self) -> bytearray:
        """The bytes to send for a query request."""
        return self.construct_message(bytearray([0xAA, 0x01, 0x00]))

    def construct_state_change(self, turn_on: int) -> bytearray:
        """The bytes to send for a state change request."""
        return self.construct_message(
            bytearray([0xAA, 0x02, 0x01, 1 if turn_on else 0])
        )

    def construct_pause(self, pause: bool) -> bytearray:
        """The bytes to send for pausing or unpausing."""
        return self.construct_message(bytearray([0xAA, 0x11, 0x01, 1 if pause else 0]))

    def construct_ir_state(self, turn_on: bool) -> bytearray:
        """The bytes to send for enabling/disabling the IR remote."""
        return self.construct_message(
            bytearray([0xAA, 0x0F, 0x01, 1 if turn_on else 0])
        )

    def construct_levels_change(
        self,
        persist: int,
        red: int | None,
        green: int | None,
        blue: int | None,
        warm_white: int | None,
        cool_white: int | None,
        write_mode: LevelWriteMode,
    ) -> list[bytearray]:
        """The bytes to send for a level change request."""
        h, s, v = colorsys.rgb_to_hsv(
            (red or 0) / 255, (green or 0) / 255, (blue or 0) / 255
        )
        h_scaled = min(359, floor(h * 360))
        s_scaled = round(s * 1000)
        v_scaled = round(v * 1000)
        return [
            self.construct_message(
                bytearray(
                    [
                        0xAA,
                        0x03,
                        0x07,
                        0x01,
                        h_scaled >> 8,
                        h_scaled & 0xFF,
                        s_scaled >> 8,
                        s_scaled & 0xFF,
                        v_scaled >> 8,
                        v_scaled & 0xFF,
                    ]
                )
            )
        ]

    def construct_preset_pattern(
        self, pattern: int, speed: int, brightness: int
    ) -> list[bytearray]:
        """The bytes to send for a preset pattern."""
        return [
            self.construct_message(
                bytearray(
                    [
                        0xAA,
                        0x03,
                        0x04,
                        0x02,
                        pattern & 0xFF,
                        (brightness >> 8) & 0xFF,
                        brightness & 0xFF,
                    ]
                )
            ),
            self.construct_message(bytearray([0xAA, 0x0C, 0x01, min(speed, 100)])),
        ]

    def construct_custom_effect(
        self, rgb_list: list[tuple[int, int, int]], speed: int, transition_type: str
    ) -> list[bytearray]:
        """The bytes to send for a custom effect."""
        data_bytes = len(rgb_list) * 3 + 1
        hue_message = bytearray(data_bytes + 3)
        hue_message[0:4] = [0xAA, 0xDA, data_bytes, 0x01]
        for [i, [r, g, b]] in enumerate(rgb_list):
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if v < 0.25:
                h = 0xFE  # black
            elif s < 0.25:
                h = 0xFF  # white
            else:
                h = floor(h * 0xAF)
            # necessary to satisfy both flake and ruff:
            a = i * 3 + 4
            b = a + 3
            hue_message[a:b] = [i >> 8, i & 0xFF, h]
        return [
            *self.construct_motion(speed, 0),
            self.construct_message(hue_message),
            *self.construct_motion(speed, 2),
        ]

    def construct_motion(self, speed: int, transition: int) -> list[bytearray]:
        """The bytes to send for motion speed and transition."""
        return [
            self.construct_message(
                bytearray([0xAA, 0xD0, 0x04, transition, 0x64, speed, 0x01])
            )
        ]

    def construct_message(self, raw_bytes: bytearray) -> bytearray:
        """Calculate checksum of byte array and add to end."""
        csum = sum(raw_bytes) & 0xFF
        raw_bytes.append(csum)
        return raw_bytes
