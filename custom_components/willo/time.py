"""Time entities for WILLO schedule slots."""
from __future__ import annotations

import logging
from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SCHEDULE_ENTITY, DOMAIN
from .coordinator import WILLOCoordinator

_LOGGER = logging.getLogger(__name__)

# (slot_key, display_name, icon, default_value)
_SLOT_DEFS: list[tuple[str, str, str, time]] = [
    ("slot1_start", "Schedule Slot 1 Start", "mdi:clock-start", time(7, 0)),
    ("slot1_end", "Schedule Slot 1 End", "mdi:clock-end", time(9, 0)),
    ("slot2_start", "Schedule Slot 2 Start", "mdi:clock-start", time(16, 0)),
    ("slot2_end", "Schedule Slot 2 End", "mdi:clock-end", time(22, 0)),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WILLO time entities from a config entry."""
    coordinator: WILLOCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            WILLOTimeEntity(coordinator, entry, slot_key, name, icon, default)
            for slot_key, name, icon, default in _SLOT_DEFS
        ]
    )


class WILLOTimeEntity(CoordinatorEntity[WILLOCoordinator], TimeEntity):
    """A time entity representing one of the WILLO schedule slot boundaries."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WILLOCoordinator,
        entry: ConfigEntry,
        slot_key: str,
        name: str,
        icon: str,
        default: time,
    ) -> None:
        """Initialise the time entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._slot_key = slot_key
        self._default = default
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{slot_key}"

    @property
    def native_value(self) -> time | None:
        """Return the current slot time value stored in the coordinator."""
        return getattr(self.coordinator, self._slot_key, self._default)

    @property
    def available(self) -> bool:
        """Unavailable when a Schedule Helper entity is configured."""
        if self._entry.data.get(CONF_SCHEDULE_ENTITY):
            return False
        return self.coordinator.last_update_success

    async def async_set_value(self, value: time) -> None:
        """Update the slot time and push the new 24-bit schedule to the device."""
        setattr(self.coordinator, self._slot_key, value)
        await self.coordinator.set_schedule(self.coordinator.slots_to_bits())
        self.async_write_ha_state()
