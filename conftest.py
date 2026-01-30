from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.local_calendar import CONF_CALENDAR_NAME, LocalCalendarStore  # type: ignore
from homeassistant.components.local_calendar.const import DOMAIN as LOCAL_CALENDAR_DOMAIN  # type: ignore
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse, callback
from homeassistant.exceptions import DependencyError
from homeassistant.helpers import entity_platform
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import AsyncMock, MockConfigEntry

from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.hass_api import HomeAssistantAPI
from custom_components.autoarm.helpers import AppHealthTracker
from custom_components.autoarm.notifier import Notifier


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations) -> None:  # noqa: ANN001, ARG001
    """Enable custom integrations in all tests."""
    return


@pytest.fixture(name="skip_notifications", autouse=True)
def skip_notifications_fixture() -> Generator[None, Any, None]:
    """Prevents HomeAssistant from attempting to create and dismiss persistent notifications.

    These calls would fail without this fixture since the persistent_notification
    integration is never loaded during a test.
    """
    with (
        patch("homeassistant.components.persistent_notification.async_create"),
        patch("homeassistant.components.persistent_notification.async_dismiss"),
    ):
        yield


@pytest.fixture
def hass_api(hass: HomeAssistant) -> HomeAssistantAPI:
    hass_api = HomeAssistantAPI(hass)
    return hass_api  # noqa: RET504


@pytest.fixture
async def local_calendar(
    hass: HomeAssistant, calendar_platform: entity_platform.EntityPlatform, name: str = "testing_calendar"
) -> CalendarEntity:

    await async_setup_component(hass=hass, domain=LOCAL_CALENDAR_DOMAIN, config={})
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(
        domain=LOCAL_CALENDAR_DOMAIN, title=name, state=ConfigEntryState.LOADED, data={CONF_CALENDAR_NAME: name}
    )
    config_entry.runtime_data = AsyncMock(spec=LocalCalendarStore)
    config_entry.runtime_data.async_load.return_value = ""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_forward_entry_setups(config_entry, [Platform.CALENDAR])
    await hass.async_block_till_done()

    calendar: CalendarEntity = calendar_platform.domain_entities[f"calendar.{slugify(name)}"]  # type: ignore
    return calendar


@pytest.fixture
async def test_config_calendars(hass: HomeAssistant) -> None:

    await async_setup_component(hass=hass, domain=LOCAL_CALENDAR_DOMAIN, config={})
    await hass.async_block_till_done()
    for cal_name in ("family_events", "alarm_control"):
        config_entry = MockConfigEntry(
            domain=LOCAL_CALENDAR_DOMAIN, title=cal_name, state=ConfigEntryState.LOADED, data={CONF_CALENDAR_NAME: cal_name}
        )
        config_entry.runtime_data = AsyncMock(spec=LocalCalendarStore)
        config_entry.runtime_data.async_load.return_value = ""
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_forward_entry_setups(config_entry, [Platform.CALENDAR])
    await hass.async_block_till_done()


@pytest.fixture
async def calendar_platform(hass: HomeAssistant) -> entity_platform.EntityPlatform:
    await async_setup_component(hass=hass, domain="calendar", config={})
    platforms: list[entity_platform.EntityPlatform] = entity_platform.async_get_platforms(hass, "calendar")
    if platforms:
        return platforms[0]
    raise DependencyError(["calendar"])


@pytest.fixture
def mock_armer_real_hass(hass: HomeAssistant) -> AlarmArmer:
    mocked = AsyncMock(spec=AlarmArmer)
    mocked.hass = hass
    mocked.app_health_tracker = Mock(spec=AppHealthTracker)
    mocked.notifier = AsyncMock(spec=Notifier)
    return mocked


class MockAction(BaseNotificationService):
    """A test class for notification services."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[tuple[str, str | None, str | None, dict[str, Any]]] = []

    @callback
    async def async_send_message(
        self, message: str = "", title: str | None = None, target: str | None = None, **kwargs: dict[str, Any]
    ) -> None:
        self.calls.append((message, title, target, kwargs))


@pytest.fixture
def mock_notify(hass: HomeAssistant) -> MockAction:
    mock_action: MockAction = MockAction()
    hass.services.async_register(
        "notify", "send_message", mock_action.async_send_message, supports_response=SupportsResponse.NONE
    )  # type: ignore
    hass.services.async_register(
        "notify", "supernotify", mock_action.async_send_message, supports_response=SupportsResponse.NONE
    )  # type: ignore

    return mock_action
