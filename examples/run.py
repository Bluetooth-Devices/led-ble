import asyncio
import logging

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from led_ble import LEDBLE, LEDBLEState

_LOGGER = logging.getLogger(__name__)

ADDRESS = "BE:27:E1:00:10:63"  # Hello Fairy-1063PPPP


async def run() -> None:
    scanner = BleakScanner()
    future: asyncio.Future[BLEDevice] = asyncio.Future()

    def on_detected(device: BLEDevice, adv: AdvertisementData) -> None:
        if future.done():
            return
        _LOGGER.info("Detected: %s", device)
        if device.address.lower() == ADDRESS.lower():
            _LOGGER.info("Found device: %s", device.address)
            future.set_result(device)

    scanner.register_detection_callback(on_detected)
    await scanner.start()

    def on_state_changed(state: LEDBLEState) -> None:
        _LOGGER.info("State changed: %s", state)

    device = await future
    led = LEDBLE(device)
    cancel_callback = led.register_callback(on_state_changed)
    _LOGGER.info("update...")
    await led.update()
    _LOGGER.info("turn_on...")
    await led.turn_on()
    _LOGGER.info("set_rgb(red)...")
    await led.set_rgb((255, 0, 0), 255)
    await asyncio.sleep(1)
    _LOGGER.info("set_rgb(green)...")
    await led.set_rgb((0, 255, 0), 128)
    await asyncio.sleep(1)
    _LOGGER.info("set_rgb(blue)...")
    await led.set_rgb((0, 0, 255), 255)
    await asyncio.sleep(1)
    _LOGGER.info("set_rgbw(white)...")
    await led.set_rgbw((255, 255, 255, 128), 255)
    await asyncio.sleep(1)
    _LOGGER.info("set_preset_pattern(1)...")
    await led.async_set_preset_pattern(1, 100, 100)
    await asyncio.sleep(2)
    _LOGGER.info("turn_off...")
    await led.turn_off()
    _LOGGER.info("update...")
    await led.update()
    _LOGGER.info("finish...")
    cancel_callback()
    await scanner.stop()
    _LOGGER.info("done")


logging.basicConfig(level=logging.INFO)
logging.getLogger("led_ble").setLevel(logging.DEBUG)
asyncio.run(run())
