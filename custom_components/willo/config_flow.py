import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.components.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import CONF_SCHEDULE_ENTITY, DOMAIN

_MANUAL_OPTION = "__manual__"
_MANUAL_LABEL = "Enter manually / Saisie manuelle"
_DEFAULT_NAME = "WILLO"


class WILLOConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, str] = {}  # address -> display label

    async def async_step_user(self, user_input=None):
        """Entry point: scan for MBAM devices and route accordingly."""
        discovered = [
            info
            for info in async_discovered_service_info(self.hass, connectable=True)
            if info.name and info.name.upper().startswith("MBAM")
        ]
        if discovered:
            self._discovered_devices = {
                info.address: f"{info.name} ({info.address})"
                for info in discovered
            }
            return await self.async_step_pick_device()
        return await self.async_step_manual()

    async def async_step_pick_device(self, user_input=None):
        """Let the user pick a discovered device or switch to manual entry."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            if address == _MANUAL_OPTION:
                return await self.async_step_manual()
            return await self._async_create_entry(
                address=address,
                name=user_input.get(CONF_NAME, _DEFAULT_NAME),
                schedule_entity=user_input.get(CONF_SCHEDULE_ENTITY, ""),
            )

        options = [
            {"value": addr, "label": label}
            for addr, label in self._discovered_devices.items()
        ]
        options.append({"value": _MANUAL_OPTION, "label": _MANUAL_LABEL})

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(CONF_NAME, default=_DEFAULT_NAME): str,
                vol.Optional(CONF_SCHEDULE_ENTITY, default=""): str,
            }),
        )

    async def async_step_manual(self, user_input=None):
        """Manual MAC address entry fallback."""
        if user_input is not None:
            return await self._async_create_entry(
                address=user_input[CONF_ADDRESS],
                name=user_input.get(CONF_NAME, _DEFAULT_NAME),
                schedule_entity=user_input.get(CONF_SCHEDULE_ENTITY, ""),
            )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default="B0:B2:1C:84:61:D6"): str,
                vol.Optional(CONF_NAME, default=_DEFAULT_NAME): str,
                vol.Optional(CONF_SCHEDULE_ENTITY, default=""): str,
            }),
        )

    async def _async_create_entry(
        self, address: str, name: str, schedule_entity: str
    ):
        """Shared logic to finalise and create the config entry."""
        await self.async_set_unique_id(address.upper())
        self._abort_if_unique_id_configured()
        data: dict = {CONF_ADDRESS: address.upper(), CONF_NAME: name}
        if schedule_entity:
            data[CONF_SCHEDULE_ENTITY] = schedule_entity
        return self.async_create_entry(title=name or _DEFAULT_NAME, data=data)
