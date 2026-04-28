import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME

DOMAIN = "willo"

class WILLOConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_ADDRESS].upper())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "WILLO"),
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS, default="B0:B2:1C:84:61:D6"): str,
                vol.Optional(CONF_NAME, default="WILLO"): str,
            }),
        )