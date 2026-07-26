from __future__ import annotations

from collections.abc import Sequence
from enum import IntEnum

UUID_GOVEE_H6196_CONTROL_CHARACTERISTIC = "00010203-0405-0607-0809-0a0b0c0d2b11"

GOVEE_H6196_NAME_PREFIX = "ihoment_H6196"
GOVEE_H6196_MODEL_NUM = 0x6196

PACKET_PREFIX = 0x33
PACKET_LENGTH = 20
PACKET_PAYLOAD_LENGTH = 17


class GoveeH6196Command(IntEnum):
    POWER = 0x01
    BRIGHTNESS = 0x04
    COLOR = 0x05


class GoveeH6196LightMode(IntEnum):
    MANUAL_COLOR = 0x02


def is_h6196_light_name(local_name: str | None) -> bool:
    """Return whether a Bluetooth local name looks like a Govee/iHoment H6196."""
    return bool(local_name and local_name.startswith(GOVEE_H6196_NAME_PREFIX))


def _validate_byte(value: int) -> int:
    if not 0 <= value <= 255:
        raise ValueError("Byte value must be between 0 and 255")
    return value


def _checksum(data: bytes) -> int:
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum & 0xFF


def build_h6196_packet(command: GoveeH6196Command, payload: Sequence[int]) -> bytes:
    """Build a 20-byte Govee H6196 BLE command packet."""
    if len(payload) > PACKET_PAYLOAD_LENGTH:
        raise ValueError("Payload too long")

    payload_bytes = bytes(_validate_byte(value) for value in payload)
    frame = bytes([PACKET_PREFIX, command]) + payload_bytes
    frame += bytes(PACKET_LENGTH - 1 - len(frame))
    return frame + bytes([_checksum(frame)])


def build_h6196_power_packet(is_on: bool) -> bytes:
    """Build a Govee H6196 power command packet."""
    return build_h6196_packet(GoveeH6196Command.POWER, [int(is_on)])


def build_h6196_brightness_packet(brightness: int) -> bytes:
    """Build a Govee H6196 brightness command packet."""
    return build_h6196_packet(
        GoveeH6196Command.BRIGHTNESS, [_validate_byte(brightness)]
    )


def build_h6196_rgb_packet(rgb_color: tuple[int, int, int]) -> bytes:
    """Build a Govee H6196 manual RGB command packet."""
    red, green, blue = rgb_color
    return build_h6196_packet(
        GoveeH6196Command.COLOR,
        [
            GoveeH6196LightMode.MANUAL_COLOR,
            _validate_byte(red),
            _validate_byte(green),
            _validate_byte(blue),
        ],
    )
