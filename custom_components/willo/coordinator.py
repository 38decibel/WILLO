"""Coordinator BLE for WILLO."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DEVICE_NAME = "MBAM UART Service"
NUS_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

CMD_LED_ON = "#I!1*"
CMD_LED_OFF = "#I!0*"

POLL_INTERVAL = timedelta(minutes=5)
COMMAND_TIMEOUT = 3.0


class WILLOCoordinator(DataUpdateCoordinator):
    """Data coordinator for WILLO via BLE."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(hass, _LOGGER, name="WILLO", update_interval=POLL_INTERVAL)
        self.hass = hass
        self.address = address
        self._buffer = ""
        self._response_event: asyncio.Event = asyncio.Event()
        self._led_state: bool = False

    async def _connect(self) -> BleakClient:
        """Establish a reliable BLE connection via bleak-retry-connector."""
        ble_device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise UpdateFailed(
                f"Device {self.address} not found via Bluetooth — is it in range?"
            )
        return await establish_connection(
            BleakClient,
            device=ble_device,
            name=self.address,
        )

    def _notification_handler(self, sender: int, data: bytearray) -> None:
        self._buffer += data.decode(errors="replace")
        if "*" in self._buffer:
            self._response_event.set()

    def _consume_response(self) -> str:
        response = self._buffer
        self._buffer = ""
        return response

    async def _send_command(
        self, client: BleakClient, cmd: str, expect_response: bool = True
    ) -> str:
        self._buffer = ""
        self._response_event.clear()
        await client.write_gatt_char(NUS_TX, cmd.encode(), response=False)
        if expect_response:
            try:
                await asyncio.wait_for(
                    self._response_event.wait(), timeout=COMMAND_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.debug("No response for command '%s'", cmd)
        return self._consume_response()

    @staticmethod
    def _parse_response(raw: str, cmd_letter: str) -> str | None:
        prefix = f"#{cmd_letter}!"
        if prefix in raw and "*" in raw:
            start = raw.index(prefix) + len(prefix)
            end = raw.index("*", start)
            return raw[start:end]
        return None

    async def set_led(self, state: bool) -> None:
        cmd = CMD_LED_ON if state else CMD_LED_OFF
        client = await self._connect()
        try:
            await client.start_notify(NUS_RX, self._notification_handler)
            await self._send_command(client, cmd, expect_response=False)
            await client.stop_notify(NUS_RX)
        except BleakError as err:
            raise UpdateFailed(f"BLE error (set_led): {err}") from err
        finally:
            await client.disconnect()
        self._led_state = state

    async def set_schedule(self, bits: str) -> None:
        if len(bits) != 24 or not all(c in "01" for c in bits):
            raise ValueError(f"Invalid schedule: '{bits}' (expected 24 chars of 0/1)")
        cmd = f"#H!{bits}*"
        client = await self._connect()
        try:
            await client.start_notify(NUS_RX, self._notification_handler)
            await self._send_command(client, cmd)
            await client.stop_notify(NUS_RX)
        except BleakError as err:
            raise UpdateFailed(f"BLE error (set_schedule): {err}") from err
        finally:
            await client.disconnect()

    async def _async_update_data(self) -> dict:
        client = await self._connect()
        try:
            await client.start_notify(NUS_RX, self._notification_handler)

            now = datetime.now()
            await self._send_command(client, f"#D!{now.strftime('%y%m%d')}*")
            await self._send_command(client, f"#T!{now.strftime('%H%M%S')}*")

            raw_v = await self._send_command(client, "#V?")
            firmware = self._parse_response(raw_v, "V") or ""

            raw_h = await self._send_command(client, "#H?")
            schedule = self._parse_response(raw_h, "H") or "0" * 24

            await client.stop_notify(NUS_RX)
        except BleakError as err:
            raise UpdateFailed(f"BLE error: {err}") from err
        finally:
            await client.disconnect()

        return {
            "led": self._led_state,
            "schedule": schedule,
            "firmware": firmware,
            "connected": True,
        }
