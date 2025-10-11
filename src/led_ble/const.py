BASE_UUID_FORMAT = "0000{}-0000-1000-8000-00805f9b34fb"

# "ff01" - 0x97 socket - LEDnetWF010097DAB37A, LEDnetWF01001C49D272
# "ffd4" - Triones:B30200000459C - legacy


STATE_COMMAND = b"\xef\x01\x77"


class CharacteristicMissingError(Exception):
    """Raised when a characteristic is missing."""


HELLO_FAIRY_WRITE_CHARACTERISTIC = "49535343-8841-43f4-a8d4-ecbe34729bb3"
HELLO_FAIRY_READ_CHARACTERISTIC = "49535343-1e4d-4bd9-ba61-23c647249616"

POSSIBLE_WRITE_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff01", "ffd5", "ffd9", "ffe5", "ffe9"]
] + [HELLO_FAIRY_WRITE_CHARACTERISTIC]

POSSIBLE_READ_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff02", "ffd0", "ffd4", "ffe0", "ffe4"]
] + [HELLO_FAIRY_READ_CHARACTERISTIC]


QUERY_STATE_BYTES = bytearray([0xEF, 0x01, 0x77])
