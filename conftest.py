from collections.abc import AsyncGenerator, Generator
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.alarm_control_panel import DATA_COMPONENT as ALARM_PANEL_DATA_COMPONENT
from homeassistant.components.alarm_control_panel.const import DOMAIN as ALARM_PANEL_DOMAIN
from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.local_calendar import CONF_CALENDAR_NAME, LocalCalendarStore  # type: ignore[attr-defined]
from homeassistant.components.local_calendar.const import DOMAIN as LOCAL_CALENDAR_DOMAIN  # type: ignore[import-not-found]
from homeassistant.components.notify.legacy import BaseNotificationService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_NAME, EVENT_COMPONENT_LOADED, Platform
from homeassistant.core import Event, HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import DependencyError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.setup import EventComponentLoaded, async_setup_component
from homeassistant.util import slugify
from pytest_homeassistant_custom_component.common import AsyncMock, MockConfigEntry

from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ENTITIES,
    CONF_NO_EVENT_MODE,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_PERSON_ENTITIES,
    CONF_USE_ALARM_SERVICE,
    DEFAULT_CALENDAR_OCCUPANCY_OVERRIDE_STATES,
)
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY
from custom_components.autoarm.hass_api import HomeAssistantAPI
from custom_components.autoarm.helpers import AppHealthTracker
from custom_components.autoarm.notifier import Notifier

if TYPE_CHECKING:
    from homeassistant.helpers.typing import ConfigType

TEST_PANEL = "alarm_control_panel.test_panel"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: Any) -> None:
    """Enable custom integrations in all tests."""
    return


PANEL_ACTIONS = (
    "alarm_arm_away",
    "alarm_arm_home",
    "alarm_arm_night",
    "alarm_arm_vacation",
    "alarm_arm_custom_bypass",
    "alarm_disarm",
)


@pytest.fixture(autouse=True)
def panel_actions(hass: HomeAssistant) -> list[ServiceCall]:
    """Stand in for the alarm_control_panel actions, so AutoArm's default of using them works in tests.

    Panels that are only states are moved to the requested state, real panel entities, such as
    the manual one from the alarm_panel fixture, are asked to change as the real action would.
    Installed again when the alarm_control_panel component loads, since it registers its own actions.
    """
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)
        component = hass.data.get(ALARM_PANEL_DATA_COMPONENT)
        for entity_id in cv.ensure_list(call.data["entity_id"]):
            entity = component.get_entity(entity_id) if component else None
            if entity is not None:
                await getattr(entity, f"async_{call.service}")(code=None)
            else:
                requested = call.service.replace("alarm_arm_", "armed_").replace("alarm_disarm", "disarmed")
                hass.states.async_set(entity_id, requested)

    @callback
    def install(event: Event[EventComponentLoaded] | None = None) -> None:
        if event is None or event.data["component"] == ALARM_PANEL_DOMAIN:
            for service in PANEL_ACTIONS:
                hass.services.async_register(ALARM_PANEL_DOMAIN, service, handler)

    install()
    hass.bus.async_listen(EVENT_COMPONENT_LOADED, install)
    return calls


@pytest.fixture(name="skip_notifications")
def skip_notifications_fixture() -> Generator[None, Any]:
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
    return hass_api


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

    return cast("CalendarEntity", calendar_platform.domain_entities[f"calendar.{slugify(name)}"])


@pytest.fixture
async def alarm_panel(hass: HomeAssistant) -> Any:
    alarm_config: ConfigType = {
        ALARM_PANEL_DOMAIN: {"platform": "manual", CONF_NAME: "Testing", "code_arm_required": False, "arming_time": 0}
    }
    assert await async_setup_component(hass, ALARM_PANEL_DOMAIN, alarm_config)
    return alarm_config[ALARM_PANEL_DOMAIN][CONF_NAME]


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
    mocked: AlarmArmer = AsyncMock(spec=AlarmArmer)
    mocked.hass = hass
    mocked.app_health_tracker = Mock(spec=AppHealthTracker)
    mocked.notifier = AsyncMock(spec=Notifier)
    mocked.calendar_occupancy_override_states = DEFAULT_CALENDAR_OCCUPANCY_OVERRIDE_STATES
    mocked.occupied_defaults = {}
    return mocked


@pytest.fixture
async def autoarmer(hass: HomeAssistant) -> AsyncGenerator[AlarmArmer]:
    uut = AlarmArmer(hass, TEST_PANEL, occupancy={"entity_id": ["person.tester_bob"]})
    await uut.initialize()
    yield uut
    uut.shutdown()


@pytest.fixture
def day(hass: HomeAssistant) -> None:
    hass.states.async_set("sun.sun", "above_horizon")


@pytest.fixture
def night(hass: HomeAssistant) -> None:
    hass.states.async_set("sun.sun", "below_horizon")


@pytest.fixture
def occupied(hass: HomeAssistant) -> None:
    hass.states.async_set("person.tester_bob", "home")


@pytest.fixture
def unoccupied(hass: HomeAssistant) -> None:
    hass.states.async_set("person.tester_bob", "away")


class MockAction(BaseNotificationService):
    """A test class for notification services."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: list[ServiceCall] = []

    async def async_handle(self, call: ServiceCall) -> None:
        self.calls.append(call)


@pytest.fixture
def mock_notify(hass: HomeAssistant) -> MockAction:
    mock_action: MockAction = MockAction()
    hass.services.async_register("notify", "send_message", mock_action.async_handle, supports_response=SupportsResponse.NONE)
    hass.services.async_register("notify", "supernotify", mock_action.async_handle, supports_response=SupportsResponse.NONE)

    return mock_action


@pytest.fixture
async def setup_autoarm(
    hass: HomeAssistant,
    mock_notify: MockAction,
) -> MockConfigEntry:
    """Set up autoarm via ConfigEntry with default test config."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_panel.testing"},
        options={
            CONF_CALENDAR_ENTITIES: [],
            CONF_PERSON_ENTITIES: ["person.house_owner", "person.tenant"],
            CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
            CONF_OCCUPANCY_DEFAULT_NIGHT: None,
            CONF_NO_EVENT_MODE: "auto",
            CONF_USE_ALARM_SERVICE: True,
        },
    )
    entry.add_to_hass(hass)
    hass.data[YAML_DATA_KEY] = {}
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
