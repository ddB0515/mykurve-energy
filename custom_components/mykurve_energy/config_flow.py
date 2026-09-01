"""Config Flow for MyKurve Energy integration"""

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from mykurve import MyKurveApi
from mykurve.exceptions import AuthenticationFailed, MfaCodeRequired, MyKurveApiException

from .const import CONF_MFA_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_MFA_SECRET): str,
    }
)


class MyKurveConfigFlow(ConfigFlow, domain=DOMAIN):
    """MyKurve Energy config flow."""

    VERSION = 1

    async def _validate_input(self, user_input):
        api = MyKurveApi()

        try:
            async with asyncio.timeout(30):
                token = await api.get_token(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    mfa_secret=user_input.get(CONF_MFA_SECRET) or None,
                )
        except TimeoutError as err:
            raise CannotConnect from err
        except AuthenticationFailed as err:
            raise InvalidAuth from err
        except MfaCodeRequired as err:
            raise MfaRequired from err
        except MyKurveApiException as err:
            raise CannotConnect from err

        return token is not None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle gathering login info"""
        errors = {}
        if user_input is not None:
            try:
                await self._validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MfaRequired:
                errors["base"] = "mfa_required"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(
                    f"{DOMAIN}_{user_input[CONF_USERNAME]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"MyKurve Energy: {user_input[CONF_USERNAME]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class MfaRequired(HomeAssistantError):
    """Error to indicate the account needs a 2FA secret to complete login."""