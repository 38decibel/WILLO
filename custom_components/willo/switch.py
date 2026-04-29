"""Switch entities for WILLO: LED control."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WILLOCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WILLO switch entities from a config entry."""
    coordinator: WILLOCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WILLOLedSwitch(coordinator, entry)])


class WILLOLedSwitch(CoordinatorEntity[WILLOCoordinator], SwitchEntity):
    """Switch for the WILLO device LED."""

    _attr_icon = "mdi:lightbulb"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WILLOCoordinator, entry: ConfigEntry) -> None:
        """Initialise the LED switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "LED"
        self._attr_unique_id = f"{entry.entry_id}_led"

    @property
    def is_on(self) -> bool:
        """Return the LED state (tracked locally)."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get("led", False))

    @property
    def available(self) -> bool:
        """Available when the coordinator has valid data."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the LED."""
        await self.coordinator.set_led(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the LED."""
        await self.coordinator.set_led(False)
        self.async_write_ha_state()
