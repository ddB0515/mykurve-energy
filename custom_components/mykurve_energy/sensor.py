"""Support for MyKurve Energy Pricing data"""

from __future__ import annotations
from datetime import timedelta, datetime
import logging
import asyncio
from dataclasses import dataclass
from collections.abc import Callable

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from mykurve import MyKurveApi
from mykurve.data_classes import Dashboard

from . import MyKurveAuth
from .const import DOMAIN, CONF_ACC_NUMBER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)

@dataclass(frozen=True, kw_only=True)
class MyKurveSensorEntityDescription(SensorEntityDescription):
    """MyKurve Energy sensor description."""
    value_fn: Callable[[Dashboard], StateType | datetime]

ENERGY_METER_SENSOR_TYPES = (
    MyKurveSensorEntityDescription(
        key=f"{DOMAIN}_usage_kwh",
        icon="mdi:fire",
        name="Energy usage kWh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda res: res.lastMeterReading,
    ),
    MyKurveSensorEntityDescription(
        key=f"{DOMAIN}_price_gbp",
        icon="mdi:cash-multiple",
        name="Energy price usage",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        value_fn=lambda res: res.tariffHistory.tariffInForceNow.rate,
    ),
    MyKurveSensorEntityDescription(
        key=f"{DOMAIN}_remaining_balance_gbp",
        icon="mdi:cash",
        name="Remaining balance",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda res: res.combinedBalance,
    ),
    MyKurveSensorEntityDescription(
        key=f"{DOMAIN}_todays_usage_kwh",
        icon="mdi:lightning-bolt",
        name="Today's usage",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda res: res.todaysUsage,
    ),
    MyKurveSensorEntityDescription(
        key=f"{DOMAIN}_todays_usage_cost_gbp",
        icon="mdi:cash-clock",
        name="Today's usage cost",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="GBP",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda res: res.todaysUsageCost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """MyKurve Energy Sensor Setup"""
    myKurveAuth: MyKurveAuth = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        (MyKurveSensor(myKurveAuth, entry, description)
        for description in ENERGY_METER_SENSOR_TYPES),
        True
    )

class MyKurveSensor(SensorEntity):
    """Entity object for MyKurve Energy sensor"""

    entity_description: MyKurveSensorEntityDescription

    def __init__(
        self,
        mykurveauth: MyKurveAuth,
        entry: ConfigEntry,
        description: MyKurveSensorEntityDescription,
    ) -> None:
        self.dashboard = None
        self.mykurve_auth = mykurveauth
        self.api = MyKurveApi()
        self.entry = entry

        """Set up the sensor with the initial values."""
        self._attr_unique_id = description.key
        self._attr_name = description.name
        self.entity_description = description

    async def async_update(self) -> None:
        """Get the MyKurve Energy data from the web service"""
        # if self._price and self._price.end_at >= utcnow():
        #     return  # Power price data is still valid

        async with asyncio.timeout(30):
            await self.mykurve_auth.async_get_access_token()
            token = self.entry.data[CONF_API_TOKEN]
            acc_number = self.entry.data[CONF_ACC_NUMBER]
            _LOGGER.debug(f"Updated info for account: {acc_number}")
            self.dashboard = await self.api.get_dashboard(token, acc_number)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.dashboard)