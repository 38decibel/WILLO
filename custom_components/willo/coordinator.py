"""Coordinator BLE for WILLO."""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time as dt_time, timedelta

from bleak import BleakClient
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
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
        # Schedule slot times (defaults match Wiliv Willo app recommendations)
        self.slot1_start: dt_time = dt_time(7, 0)
        self.slot1_end: dt_time = dt_time(9, 0)
        self.slot2_start: dt_time = dt_time(16, 0)
        self.slot2_end: dt_time = dt_time(22, 0)
        # Optional Schedule Helper entity ID
        self.schedule_entity_id: str | None = None

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

    def slots_to_bits(self) -> str:
        """Convert the 4 slot times to a 24-bit schedule string.

        A slot covers hour h if start <= h < end.
        An end of 00:00 (midnight) means the slot runs from start until end of day.
        Wrap-around (end.hour < start.hour and end != 00:00) is supported.
        If start == end, the slot is disabled.
        """

        def hour_in_slot(h: int, start: dt_time, end: dt_time) -> bool:
            if start == end:
                return False  # disabled
            sh, eh = start.hour, end.hour
            if eh == 0:
                # 00:00 end means "runs from start until end of day (hours start..23)"
                return h >= sh
            if sh < eh:
                return sh <= h < eh
            # wrap-around midnight (e.g. 22:00 → 02:00)
            return h >= sh or h < eh

        bits = [
            "1"
            if (
                hour_in_slot(h, self.slot1_start, self.slot1_end)
                or hour_in_slot(h, self.slot2_start, self.slot2_end)
            )
            else "0"
            for h in range(24)
        ]
        return "".join(bits)

    def bits_to_slots(self, bits: str) -> None:
        """Parse a 24-bit schedule string back into slot start/end times.

        Finds up to 2 contiguous runs of '1' and maps them to slot1 / slot2.
        End time is stored as the first hour *after* the run, or 00:00 when the
        run reaches the end of the day (hour 24 wraps to midnight).
        """
        runs: list[tuple[int, int]] = []
        in_run = False
        run_start = 0
        for i, bit in enumerate(bits):
            if bit == "1" and not in_run:
                in_run = True
                run_start = i
            elif bit == "0" and in_run:
                in_run = False
                runs.append((run_start, i))
        if in_run:
            runs.append((run_start, 24))

        if len(runs) >= 1:
            self.slot1_start = dt_time(runs[0][0], 0)
            # end==24 → store as 00:00 (midnight), handled as "until end of day"
            self.slot1_end = dt_time(runs[0][1] % 24, 0)
        if len(runs) >= 2:
            self.slot2_start = dt_time(runs[1][0], 0)
            self.slot2_end = dt_time(runs[1][1] % 24, 0)

    async def bits_from_schedule_entity(self, entity_id: str) -> str:
        """Build a 24-bit schedule string from a HA Schedule Helper entity for today.

        Reads the schedule configuration from the entity's config entry options/data.
        The expected format is a dict keyed by weekday name (e.g. 'monday') containing
        a list of time-block dicts with 'from' and 'to' keys (HH:MM strings).
        """
        bits = ["0"] * 24
        today = date.today().strftime("%A").lower()

        entity_reg = er.async_get(self.hass)
        entity_entry = entity_reg.async_get(entity_id)

        if entity_entry and entity_entry.config_entry_id:
            config_entry = self.hass.config_entries.async_get_entry(
                entity_entry.config_entry_id
            )
            if config_entry:
                schedule_data = config_entry.options.get(
                    "schedule", config_entry.data.get("schedule", {})
                )
                day_blocks = schedule_data.get(today, [])
                for block in day_blocks:
                    try:
                        start_h = int(block.get("from", "0:0").split(":")[0])
                        end_h = int(block.get("to", "0:0").split(":")[0])
                        # end_h == 0 means midnight (end of day) → treat as 24
                        effective_end = end_h if end_h != 0 else 24
                        for h in range(start_h, min(effective_end, 24)):
                            bits[h] = "1"
                    except (ValueError, AttributeError, KeyError):
                        _LOGGER.warning(
                            "Could not parse schedule block from %s: %s",
                            entity_id,
                            block,
                        )

        return "".join(bits)

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

        # Update slot times from the received schedule (if not using a Schedule Helper)
        if len(schedule) == 24 and not self.schedule_entity_id:
            self.bits_to_slots(schedule)

        return {
            "led": self._led_state,
            "schedule": schedule,
            "firmware": firmware,
            "connected": True,
        }
