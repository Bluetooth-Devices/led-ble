import asyncio
import logging

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from led_ble import LEDBLE, LEDBLEState

_LOGGER = logging.getLogger(__name__)

ADDRESS = "D0291B39-3A1B-7FF2-787B-4E743FED5B25"


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
    await led.update()
    await led.turn_on()
    await led.set_rgb((255, 0, 0), 255)
    await led.update()

    await asyncio.sleep(1000000)
    cancel_callback()
    await scanner.stop()


logging.basicConfig(level=logging.INFO)
logging.getLogger("led_ble").setLevel(logging.DEBUG)
asyncio.run(run())
