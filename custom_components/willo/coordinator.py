"""Coordinator BLE pour WILLO."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from bleak import BleakClient
from bleak.exc import BleakError

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
    """Coordinateur de données pour WILLO via BLE."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialise le coordinateur."""
        super().__init__(
            hass,
            _LOGGER,
            name="WILLO",
            update_interval=POLL_INTERVAL,
        )
        self.address = address
        self._buffer = ""
        self._response_event: asyncio.Event = asyncio.Event()
        self._led_state: bool = False

    # ------------------------------------------------------------------
    # Internal BLE helpers
    # ------------------------------------------------------------------

    def _notification_handler(self, sender: int, data: bytearray) -> None:
        """Accumule les fragments de notification jusqu'au délimiteur '*'."""
        self._buffer += data.decode(errors="replace")
        if "*" in self._buffer:
            self._response_event.set()

    def _consume_response(self) -> str:
        """Retourne la réponse complète accumulée et vide le buffer."""
        response = self._buffer
        self._buffer = ""
        return response

    async def _send_command(
        self, client: BleakClient, cmd: str, expect_response: bool = True
    ) -> str:
        """Envoie une commande et attend la réponse (jusqu'à '*')."""
        self._buffer = ""
        self._response_event.clear()
        await client.write_gatt_char(NUS_TX, cmd.encode(), response=False)
        if expect_response:
            try:
                await asyncio.wait_for(
                    self._response_event.wait(), timeout=COMMAND_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.debug("Pas de réponse pour la commande '%s'", cmd)
        return self._consume_response()

    @staticmethod
    def _parse_response(raw: str, cmd_letter: str) -> str | None:
        """Extrait la valeur entre '#X!' et '*' d'une réponse brute."""
        prefix = f"#{cmd_letter}!"
        if prefix in raw and "*" in raw:
            start = raw.index(prefix) + len(prefix)
            end = raw.index("*", start)
            return raw[start:end]
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def set_led(self, state: bool) -> None:
        """Envoie la commande LED ON ou OFF."""
        cmd = CMD_LED_ON if state else CMD_LED_OFF
        try:
            async with BleakClient(self.address) as client:
                await client.start_notify(NUS_RX, self._notification_handler)
                await self._send_command(client, cmd, expect_response=False)
                await client.stop_notify(NUS_RX)
        except BleakError as err:
            raise UpdateFailed(f"Erreur BLE (set_led): {err}") from err
        self._led_state = state

    async def set_schedule(self, bits: str) -> None:
        """Envoie un nouveau planning horaire (24 chars '0'/'1')."""
        if len(bits) != 24 or not all(c in "01" for c in bits):
            raise ValueError(f"Planning invalide : '{bits}' (attendu 24 bits 0/1)")
        cmd = f"#H!{bits}*"
        try:
            async with BleakClient(self.address) as client:
                await client.start_notify(NUS_RX, self._notification_handler)
                await self._send_command(client, cmd)
                await client.stop_notify(NUS_RX)
        except BleakError as err:
            raise UpdateFailed(f"Erreur BLE (set_schedule): {err}") from err

    # ------------------------------------------------------------------
    # DataUpdateCoordinator._async_update_data
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Se connecte, synchronise date/heure, lit firmware et planning."""
        try:
            async with BleakClient(self.address) as client:
                await client.start_notify(NUS_RX, self._notification_handler)

                # Synchronisation date et heure
                now = datetime.now()
                date_str = now.strftime("%y%m%d")
                time_str = now.strftime("%H%M%S")
                await self._send_command(client, f"#D!{date_str}*")
                await self._send_command(client, f"#T!{time_str}*")

                # Lecture version firmware
                raw_v = await self._send_command(client, "#V?")
                firmware = self._parse_response(raw_v, "V") or ""

                # Lecture planning horaire
                raw_h = await self._send_command(client, "#H?")
                schedule = self._parse_response(raw_h, "H") or "0" * 24

                await client.stop_notify(NUS_RX)

        except BleakError as err:
            raise UpdateFailed(f"Erreur BLE : {err}") from err

        return {
            "led": self._led_state,
            "schedule": schedule,
            "firmware": firmware,
            "connected": True,
        }
