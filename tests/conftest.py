"""Shared test fixtures for led-ble.

The library is async and constructs ``asyncio`` primitives in ``LEDBLE.__init__``
(which calls ``asyncio.get_running_loop()``).  Rather than pull in a plugin we
drive a single explicit event loop per test: the ``loop`` fixture exposes it,
``make_led`` constructs an ``LEDBLE`` *inside* a running loop, and async methods
are exercised with ``loop.run_until_complete(...)``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Callable, cast

import pytest
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from led_ble.led_ble import LEDBLE


class FakeBLEDevice:
    """Minimal stand-in for ``bleak.backends.device.BLEDevice``."""

    def __init__(
        self, address: str = "AA:BB:CC:DD:EE:FF", name: str | None = "LEDnet"
    ) -> None:
        self.address = address
        self.name = name


class FakeAdvertisement:
    """Minimal stand-in for ``AdvertisementData`` (only fields we read)."""

    def __init__(self, rssi: int = -60, local_name: str | None = None) -> None:
        self.rssi = rssi
        self.local_name = local_name


class FakeServices:
    """Stand-in for ``BleakGATTServiceCollection`` characteristic lookup."""

    def __init__(self, chars: dict[str, object] | None = None) -> None:
        self._chars = chars or {}

    def get_characteristic(self, uuid: str) -> object | None:
        return self._chars.get(uuid)


@pytest.fixture
def loop() -> Iterator[asyncio.AbstractEventLoop]:
    """A dedicated event loop, set as current for the duration of the test."""
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        yield new_loop
    finally:
        new_loop.close()
        asyncio.set_event_loop(None)


@pytest.fixture
def make_led(loop: asyncio.AbstractEventLoop) -> Callable[..., LEDBLE]:
    """Factory that builds an ``LEDBLE`` bound to the test's event loop."""

    def _make(
        name: str | None = "LEDnet",
        address: str = "AA:BB:CC:DD:EE:FF",
        advertisement: FakeAdvertisement | None = None,
    ) -> LEDBLE:
        device = cast(BLEDevice, FakeBLEDevice(address, name))
        adv = cast("AdvertisementData | None", advertisement)

        async def _construct() -> LEDBLE:
            return LEDBLE(device, adv)

        return loop.run_until_complete(_construct())

    return _make


@pytest.fixture
def led(make_led: Callable[..., LEDBLE]) -> LEDBLE:
    """A default ``LEDBLE`` instance with no advertisement data."""
    return make_led()
