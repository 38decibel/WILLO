from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from homeassistant.components.bluetooth import BluetoothServiceInfo

_MANUAL_OPTION = "__manual__"
_MANUAL_LABEL = "Enter manually / Saisie manuelle"
_DEFAULT_NAME = "WILLO"


class WILLOConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered_devices: dict[str, str] = {}  # address -> display label
        self._discovered_address: str | None = None
        self._discovered_name: str | None = None

    # ------------------------------------------------------------------
    # Découverte automatique via manifest.json (bluetooth: local_name MBAM*)
    # Appelé par HA dès qu'un appareil MBAM* est détecté à proximité
    # ------------------------------------------------------------------
    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ):
        """Appelé automatiquement par HA quand un appareil MBAM* est détecté."""
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        self._discovered_address = discovery_info.address
        self._discovered_name = discovery_info.name or _DEFAULT_NAME
        self.context["title_placeholders"] = {"name": self._discovered_name}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None):
        """Confirmation d'un appareil découvert automatiquement."""
        if user_input is not None:
            return await self._async_create_entry(
                address=self._discovered_address,
                name=user_input.get(CONF_NAME, self._discovered_name or _DEFAULT_NAME),
                schedule_entity=user_input.get(CONF_SCHEDULE_ENTITY, ""),
            )

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "name": self._discovered_name,
                "address": self._discovered_address,
            },
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_NAME, default=self._discovered_name or _DEFAULT_NAME
                ): str,
                vol.Optional(CONF_SCHEDULE_ENTITY, default=""): str,
            }),
        )

    # ------------------------------------------------------------------
    # Flow manuel : ajout via "Ajouter une intégration"
    # ------------------------------------------------------------------
    async def async_step_user(self, user_input=None):
        """Point d'entrée : scan des appareils MBAM* et routage."""
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
        """L'utilisateur choisit un appareil détecté ou bascule en saisie manuelle."""
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
        """Saisie manuelle de l'adresse MAC (fallback)."""
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

    # ------------------------------------------------------------------
    # Logique commune de création de l'entrée
    # ------------------------------------------------------------------
    async def _async_create_entry(
        self, address: str, name: str, schedule_entity: str
    ):
        """Finalise et crée l'entrée de configuration."""
        await self.async_set_unique_id(address.upper())
        self._abort_if_unique_id_configured()
        data: dict = {CONF_ADDRESS: address.upper(), CONF_NAME: name}
        if schedule_entity:
            data[CONF_SCHEDULE_ENTITY] = schedule_entity
        return self.async_create_entry(title=name or _DEFAULT_NAME, data=data)
