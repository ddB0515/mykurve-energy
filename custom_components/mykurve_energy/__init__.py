"""The MyKurve Energy integration."""

from datetime import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant

from mykurve import MyKurveApi
from .const import CONF_ACC_NUMBER, CONF_MFA_SECRET, CONF_TOKEN_EXPIRY, DOMAIN
_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MyKurve Energy from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = MyKurveAuth(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


class MyKurveAuth:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._api = MyKurveApi()
        self._entry = entry
        self._hass = hass

    async def _get_entry_token(self):
        _LOGGER.debug("_get_entry_token")
        # No token saved, generate one
        if (
            CONF_TOKEN_EXPIRY not in self._entry.data
            or CONF_API_TOKEN not in self._entry.data
        ):
            await self._update_token()

        # Token is expired, generate a new one
        if self._entry.data[CONF_TOKEN_EXPIRY] <= datetime.now().timestamp():
            await self._update_token()

        return self._entry.data[CONF_API_TOKEN]

    async def _update_token(self):
        _LOGGER.debug("_update_token")
        username = self._entry.data[CONF_USERNAME]
        password = self._entry.data[CONF_PASSWORD]
        mfa_secret = self._entry.data.get(CONF_MFA_SECRET) or None
        token = await self._api.get_token(username, password, mfa_secret=mfa_secret)
        account = await self._api.get_accounts(token.access_token)
        account_no = account.accounts[0].accountNumber
        expire_time = datetime.now().timestamp() + token.expires_in

        _LOGGER.debug("New token: %s", token.access_token)
        _LOGGER.debug("Account: %s", account_no)
        _LOGGER.debug("expire_time: %s", expire_time)
        self._hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_API_TOKEN: token.access_token,
                CONF_ACC_NUMBER: account_no,
                CONF_TOKEN_EXPIRY: expire_time,
            },
        )

    async def async_get_access_token(self):
        _LOGGER.debug("async_get_access_token")
        """Get API Token from HASS Storage"""
        token = await self._get_entry_token()

        return token