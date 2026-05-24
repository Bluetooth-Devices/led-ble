BASE_UUID_FORMAT = "0000{}-0000-1000-8000-00805f9b34fb"

# "ff01" - 0x97 socket - LEDnetWF010097DAB37A, LEDnetWF01001C49D272
# "ffd4" - Triones:B30200000459C - legacy


STATE_COMMAND = b"\xef\x01\x77"


# "ffe5" potentially invalid, try last
POSSIBLE_WRITE_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff01", "ffd5", "ffd9", "ffe9", "ffe5"]
]
POSSIBLE_READ_CHARACTERISTIC_UUIDS = [
    BASE_UUID_FORMAT.format(part) for part in ["ff02", "ffd0", "ffd4", "ffe0", "ffe4"]
]
