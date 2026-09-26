"""Sensors reporting AutoArm's decisions and failures."""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .autoarming import AlarmArmer, AutoArmConfigEntry
from .const import ChangeSource
from .entity import AutoArmEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AutoArmSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[AlarmArmer], StateType | dt.datetime]
    attributes_fn: Callable[[AlarmArmer], dict[str, Any] | None]


def _status_value(key: str) -> Callable[[AlarmArmer], Any]:
    return lambda armer: armer.status[key].value if key in armer.status else None


def _status_attributes(key: str) -> Callable[[AlarmArmer], dict[str, Any] | None]:
    return lambda armer: armer.status[key].attributes if key in armer.status else None


SENSORS: tuple[AutoArmSensorEntityDescription, ...] = (
    AutoArmSensorEntityDescription(
        key="failures",
        translation_key="failures",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda armer: armer.app_health_tracker.failures,
        attributes_fn=lambda armer: {"initialization_errors": armer.app_health_tracker.initialization_errors},
    ),
    AutoArmSensorEntityDescription(
        key="last_calculation",
        translation_key="last_calculation",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_status_value("last_calculation"),
        attributes_fn=_status_attributes("last_calculation"),
    ),
    AutoArmSensorEntityDescription(
        key="last_intervention",
        translation_key="last_intervention",
        device_class=SensorDeviceClass.ENUM,
        options=[str(source) for source in ChangeSource],
        value_fn=_status_value("last_intervention"),
        attributes_fn=_status_attributes("last_intervention"),
    ),
    AutoArmSensorEntityDescription(
        key="last_calendar_event",
        translation_key="last_calendar_event",
        value_fn=_status_value("last_calendar_event"),
        attributes_fn=_status_attributes("last_calendar_event"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AutoArmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities(AutoArmSensor(entry.runtime_data, entry, description) for description in SENSORS)


class AutoArmSensor(AutoArmEntity, SensorEntity):
    entity_description: AutoArmSensorEntityDescription

    def __init__(self, armer: AlarmArmer, entry: AutoArmConfigEntry, description: AutoArmSensorEntityDescription) -> None:
        super().__init__(armer, entry, Platform.SENSOR, description)

    @property
    def native_value(self) -> StateType | dt.datetime:
        return self.entity_description.value_fn(self.armer)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self.entity_description.attributes_fn(self.armer)
