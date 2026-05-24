# LED BLE

<p align="center">
  <a href="https://github.com/bluetooth-devices/led-ble/actions?query=workflow%3ACI">
    <img src="https://img.shields.io/github/workflow/status/bluetooth-devices/led-ble/CI/main?label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://led-ble.readthedocs.io">
    <img src="https://img.shields.io/readthedocs/led-ble.svg?logo=read-the-docs&logoColor=fff&style=flat-square" alt="Documentation Status">
  </a>
  <a href="https://codecov.io/gh/bluetooth-devices/led-ble">
    <img src="https://img.shields.io/codecov/c/github/bluetooth-devices/led-ble.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://python-poetry.org/">
    <img src="https://img.shields.io/badge/packaging-poetry-299bd7?style=flat-square&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAASCAYAAABrXO8xAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAJJSURBVHgBfZLPa1NBEMe/s7tNXoxW1KJQKaUHkXhQvHgW6UHQQ09CBS/6V3hKc/AP8CqCrUcpmop3Cx48eDB4yEECjVQrlZb80CRN8t6OM/teagVxYZi38+Yz853dJbzoMV3MM8cJUcLMSUKIE8AzQ2PieZzFxEJOHMOgMQQ+dUgSAckNXhapU/NMhDSWLs1B24A8sO1xrN4NECkcAC9ASkiIJc6k5TRiUDPhnyMMdhKc+Zx19l6SgyeW76BEONY9exVQMzKExGKwwPsCzza7KGSSWRWEQhyEaDXp6ZHEr416ygbiKYOd7TEWvvcQIeusHYMJGhTwF9y7sGnSwaWyFAiyoxzqW0PM/RjghPxF2pWReAowTEXnDh0xgcLs8l2YQmOrj3N7ByiqEoH0cARs4u78WgAVkoEDIDoOi3AkcLOHU60RIg5wC4ZuTC7FaHKQm8Hq1fQuSOBvX/sodmNJSB5geaF5CPIkUeecdMxieoRO5jz9bheL6/tXjrwCyX/UYBUcjCaWHljx1xiX6z9xEjkYAzbGVnB8pvLmyXm9ep+W8CmsSHQQY77Zx1zboxAV0w7ybMhQmfqdmmw3nEp1I0Z+FGO6M8LZdoyZnuzzBdjISicKRnpxzI9fPb+0oYXsNdyi+d3h9bm9MWYHFtPeIZfLwzmFDKy1ai3p+PDls1Llz4yyFpferxjnyjJDSEy9CaCx5m2cJPerq6Xm34eTrZt3PqxYO1XOwDYZrFlH1fWnpU38Y9HRze3lj0vOujZcXKuuXm3jP+s3KbZVra7y2EAAAAAASUVORK5CYII=" alt="Poetry">
  </a>
  <a href="https://github.com/ambv/black">
    <img src="https://img.shields.io/badge/code%20style-black-000000.svg?style=flat-square" alt="black">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/led-ble/">
    <img src="https://img.shields.io/pypi/v/led-ble.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/led-ble.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/led-ble.svg?style=flat-square" alt="License">
</p>

Control a wide range of LED BLE devices

## Installation

Install this via pip (or your favourite package manager):

`pip install led-ble`

## Usage

`led-ble` controls a device given a `bleak` `BLEDevice`. The helper
`get_device` (re-exported from `bleak-retry-connector`) resolves one from a
Bluetooth address:

```python
import asyncio

from led_ble import get_device, LEDBLE


async def main() -> None:
    ble_device = await get_device("AA:BB:CC:DD:EE:FF")
    led = LEDBLE(ble_device)

    # Connect and read the current state.
    await led.update()
    print(led.name, led.rgb, led.brightness, "on" if led.on else "off")

    await led.turn_on()
    await led.set_rgb((255, 0, 0))          # red
    await led.set_rgb((0, 255, 0), 128)     # green at ~50% brightness
    await led.set_brightness(64)

    # Effects (names come from led.effect_list).
    await led.async_set_effect(led.effect_list[0], speed=50, brightness=100)

    await led.turn_off()
    await led.stop()  # disconnect


asyncio.run(main())
```

Register a callback to be notified whenever the device state changes:

```python
unregister = led.register_callback(lambda state: print("new state:", state))
# ... later
unregister()
```

## Supported devices

Devices are matched by the model number they report on connect. The built-in
model database lives in
[`model_db.py`](src/led_ble/model_db.py); unknown devices fall back to the
generic `LEDENET_ORIGINAL_RGBW` protocol, which works for many flux_led-based
controllers.

### Adding support for a new device

If your device speaks one of the
[flux_led](https://github.com/Danielhiversen/flux_led) protocols but is not
recognised (or is mis-detected), you can register it at runtime — no fork
required:

```python
from flux_led.const import COLOR_MODES_RGB_W
from flux_led.models_db import MinVersionProtocol
from flux_led.protocol import PROTOCOL_LEDENET_ORIGINAL_RGBW

from led_ble import LEDBLEModel, register_model

register_model(
    LEDBLEModel(
        model_num=0x77,                      # byte 1 of the state response
        models=["SP107E"],                   # advertised names (informational)
        description="SP107E RGBW controller",
        protocols=[MinVersionProtocol(0, PROTOCOL_LEDENET_ORIGINAL_RGBW)],
        color_modes=COLOR_MODES_RGB_W,
    )
)
```

Call `register_model` once at import time, before constructing `LEDBLE`. To
contribute the device upstream so everyone benefits, add the same
`LEDBLEModel` to the `MODELS` list in `model_db.py` and open a pull request.

Devices that use a non-flux_led protocol or different GATT characteristics are
not yet supported by registration alone.

## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- prettier-ignore-start -->
<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- markdownlint-disable -->
<!-- markdownlint-enable -->
<!-- ALL-CONTRIBUTORS-LIST:END -->
<!-- prettier-ignore-end -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

## Credits

This package was created with
[Cookiecutter](https://github.com/audreyr/cookiecutter) and the
[browniebroke/cookiecutter-pypackage](https://github.com/browniebroke/cookiecutter-pypackage)
project template.
