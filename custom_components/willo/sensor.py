"""Entité capteur pour WILLO : version firmware."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
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
    """Configure les entités sensor WILLO."""
    coordinator: WILLOCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WILLOFirmwareSensor(coordinator, entry)])


class WILLOFirmwareSensor(CoordinatorEntity[WILLOCoordinator], SensorEntity):
    """Capteur affichant la version du firmware WILLO."""

    _attr_icon = "mdi:chip"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(self, coordinator: WILLOCoordinator, entry: ConfigEntry) -> None:
        """Initialise le capteur firmware."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "Version Firmware"
        self._attr_unique_id = f"{entry.entry_id}_firmware"

    @property
    def native_value(self) -> str | None:
        """Retourne la version firmware."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("firmware")

    @property
    def available(self) -> bool:
        """Disponible si le coordinator a des données valides."""
        return self.coordinator.last_update_success
