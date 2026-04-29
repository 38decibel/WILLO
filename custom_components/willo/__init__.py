"""WILLO integration setup."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_SCHEDULE_ENTITY, DOMAIN
from .coordinator import WILLOCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor", "time"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WILLO from a config entry."""
    coordinator = WILLOCoordinator(hass, entry.data["address"])

    # First refresh to populate data
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # If a Schedule Helper entity is configured, subscribe to its state changes
    schedule_entity_id: str | None = entry.data.get(CONF_SCHEDULE_ENTITY) or None
    if schedule_entity_id:
        coordinator.schedule_entity_id = schedule_entity_id

        async def _on_schedule_change(_event) -> None:
            bits = await coordinator.bits_from_schedule_entity(schedule_entity_id)
            try:
                await coordinator.set_schedule(bits)
            except Exception as err:  # noqa: BLE001
                _LOGGER.error(
                    "Failed to update WILLO schedule from helper %s: %s",
                    schedule_entity_id,
                    err,
                )

        entry.async_on_unload(
            async_track_state_change_event(
                hass, schedule_entity_id, _on_schedule_change
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a WILLO config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
