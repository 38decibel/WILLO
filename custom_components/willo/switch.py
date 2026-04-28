"""Entités switch pour WILLO : LED et planning horaire."""
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
    """Configure les entités switch WILLO."""
    coordinator: WILLOCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = [WILLOLedSwitch(coordinator, entry)]
    entities += [WILLOHourSwitch(coordinator, entry, hour) for hour in range(24)]
    async_add_entities(entities)


class WILLOLedSwitch(CoordinatorEntity[WILLOCoordinator], SwitchEntity):
    """Switch pour la LED de la boîte WILLO."""

    _attr_icon = "mdi:lightbulb"
    _attr_has_entity_name = True

    def __init__(self, coordinator: WILLOCoordinator, entry: ConfigEntry) -> None:
        """Initialise le switch LED."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_name = "LED"
        self._attr_unique_id = f"{entry.entry_id}_led"

    @property
    def is_on(self) -> bool:
        """Retourne l'état de la LED (tracké localement)."""
        if self.coordinator.data is None:
            return False
        return bool(self.coordinator.data.get("led", False))

    @property
    def available(self) -> bool:
        """Disponible si le coordinator a des données valides."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Allume la LED."""
        await self.coordinator.set_led(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Éteint la LED."""
        await self.coordinator.set_led(False)
        self.async_write_ha_state()


class WILLOHourSwitch(CoordinatorEntity[WILLOCoordinator], SwitchEntity):
    """Switch représentant une heure du planning WILLO."""

    _attr_icon = "mdi:clock-outline"
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WILLOCoordinator, entry: ConfigEntry, hour: int
    ) -> None:
        """Initialise le switch pour l'heure donnée."""
        super().__init__(coordinator)
        self._entry = entry
        self._hour = hour
        self._attr_name = f"Heure {hour:02d}h"
        self._attr_unique_id = f"{entry.entry_id}_hour_{hour:02d}"

    @property
    def is_on(self) -> bool:
        """Retourne True si cette heure est active dans le planning."""
        if self.coordinator.data is None:
            return False
        schedule: str = self.coordinator.data.get("schedule", "0" * 24)
        if len(schedule) != 24:
            return False
        return schedule[self._hour] == "1"

    @property
    def available(self) -> bool:
        """Disponible si le coordinator a des données valides."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active cette heure dans le planning."""
        new_schedule = self._build_schedule(self._current_schedule(), self._hour, "1")
        await self.coordinator.set_schedule(new_schedule)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive cette heure dans le planning."""
        new_schedule = self._build_schedule(self._current_schedule(), self._hour, "0")
        await self.coordinator.set_schedule(new_schedule)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    @staticmethod
    def _build_schedule(schedule: str, hour: int, value: str) -> str:
        """Retourne un nouveau planning avec le bit de l'heure mis à `value`."""
        return schedule[:hour] + value + schedule[hour + 1 :]

    def _current_schedule(self) -> str:
        """Retourne le planning actuel ou un planning vide."""
        if self.coordinator.data is None:
            return "0" * 24
        schedule = self.coordinator.data.get("schedule", "0" * 24)
        return schedule if len(schedule) == 24 else "0" * 24
