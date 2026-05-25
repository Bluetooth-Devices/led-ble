from enum import IntEnum

BASE_UUID_FORMAT = "0000{}-0000-1000-8000-00805f9b34fb"

# "ff01" - 0x97 socket - LEDnetWF010097DAB37A, LEDnetWF01001C49D272
# "ffd4" - Triones:B30200000459C - legacy


STATE_COMMAND = b"\xef\x01\x77"


class CharacteristicMissingError(Exception):
    """Raised when a characteristic is missing."""


# "ffe5" potentially invalid, try last
POSSIBLE_WRITE_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff01", "ffd5", "ffd9", "ffe9", "ffe5"]
]
POSSIBLE_READ_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff02", "ffd0", "ffd4", "ffe0", "ffe4"]
]

QUERY_STATE_BYTES = bytearray([0xEF, 0x01, 0x77])


# Color order / device-type configuration (see issue #18).
#
# Wire format reverse-engineered from the LEDBLUE app:
#   set:   0x22 <color_order> <device_type> 0x33
#   query: 0xE2 0x01 0x77  ->  0xE2 <color_order> <device_type> 0x33
#
# The trailing 0x33 is a fixed suffix (not a checksum: the bytes do not sum to
# it). Pending hardware verification by the maintainer.
COLOR_ORDER_SET_PREFIX = 0x22
COLOR_ORDER_SUFFIX = 0x33
COLOR_ORDER_QUERY = bytes([0xE2, 0x01, 0x77])
COLOR_ORDER_RESPONSE_PREFIX = 0xE2
COLOR_ORDER_RESPONSE_LEN = 4


class ColorOrder(IntEnum):
    """Physical ordering of the strip's color channels."""

    RGB = 0x01
    GRB = 0x02
    BRG = 0x03


class DeviceType(IntEnum):
    """Channel configuration of the device."""

    RGB = 0x01
    RGBW = 0x02  # RGB / W
    RGB_AND_W = 0x03  # RGB & W
