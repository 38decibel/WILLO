"""Coordinator BLE for WILLO."""
from __future__ import annotations

import logging
from datetime import time as dt_time, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .client import WilloClient

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(minutes=5)


class WILLOCoordinator(DataUpdateCoordinator):
    """Data coordinator for WILLO via BLE."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        super().__init__(hass, _LOGGER, name="WILLO", update_interval=POLL_INTERVAL)
        self.hass = hass
        self.address = address
        self.client = WilloClient(hass, address)
        self._led_state: bool = False
        # Schedule slot times (defaults match Wiliv Willo app recommendations)
        self.slot1_start: dt_time = dt_time(7, 0)
        self.slot1_end: dt_time = dt_time(9, 0)
        self.slot2_start: dt_time = dt_time(16, 0)
        self.slot2_end: dt_time = dt_time(22, 0)
        # Optional Schedule Helper entity ID
        self.schedule_entity_id: str | None = None

    async def set_led(self, state: bool) -> None:
        await self.client.set_led(state)
        self._led_state = state

    async def set_schedule(self, bits: str) -> None:
        await self.client.set_schedule(bits)

    async def async_shutdown(self) -> None:
        """Disconnect the BLE client cleanly on unload."""
        await self.client.disconnect()

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

    def bits_from_schedule_entity(self, entity_id: str) -> str:
        """Build a 24-bit schedule string from a HA Schedule Helper entity for today.

        Reads the weekday time blocks directly from the entity's state attributes.
        The Schedule Helper stores each day's blocks under keys like 'monday',
        'tuesday', etc.  Each block is a dict with 'from' and 'to' keys
        (format 'HH:MM:SS').

        Returns '0' * 24 if the entity is not found or its attributes are missing.
        """
        _WEEKDAY_KEYS = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        bits = ["0"] * 24

        state = self.hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning(
                "Schedule Helper entity '%s' not found — returning empty schedule",
                entity_id,
            )
            return "".join(bits)

        today_key = _WEEKDAY_KEYS[dt_util.now().weekday()]
        day_blocks = state.attributes.get(today_key, [])

        for block in day_blocks:
            try:
                start_h = int(str(block.get("from", "0:0:0")).split(":")[0])
                end_h = int(str(block.get("to", "0:0:0")).split(":")[0])
                # end_h == 0 means midnight (end of day) — treat as 24
                effective_end = end_h if end_h != 0 else 24
                for h in range(start_h, min(effective_end, 24)):
                    bits[h] = "1"
            except (ValueError, AttributeError, KeyError):
                _LOGGER.warning(
                    "Could not parse schedule block from %s: %s",
                    entity_id,
                    block,
                )

        _LOGGER.debug(
            "Schedule Helper '%s' today (%s) → %s",
            entity_id,
            today_key,
            "".join(bits),
        )
        return "".join(bits)

    async def _async_update_data(self) -> dict:
        data = await self.client.get_data()

        schedule = data.get("schedule", "0" * 24)

        # Update slot times from the received schedule (if not using a Schedule Helper)
        if len(schedule) == 24 and not self.schedule_entity_id:
            self.bits_to_slots(schedule)

        return {
            "led": self._led_state,
            "schedule": schedule,
            "firmware": data.get("firmware", ""),
            "connected": True,
        }
