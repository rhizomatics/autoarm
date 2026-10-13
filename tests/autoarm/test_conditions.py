import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.helpers import config_validation as cv

from custom_components.autoarm.const import DEFAULT_TRANSITIONS, ConditionVariables
from custom_components.autoarm.hass_api import HomeAssistantAPI


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.values(), ids=DEFAULT_TRANSITIONS.keys())
def test_default_transitions_validated(schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(schema)
    assert condition


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.keys())
async def test_default_transitions_built(hass_api: HomeAssistantAPI, schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(DEFAULT_TRANSITIONS[schema])
    checker = await hass_api.build_condition(condition, validate=True, name=schema)
    assert checker


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.keys())
async def test_default_transitions_evaluated(hass_api: HomeAssistantAPI, schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(DEFAULT_TRANSITIONS[schema])
    checker = await hass_api.build_condition(condition, validate=True, name=schema)
    assert checker
    hass_api.evaluate_condition(checker)


@pytest.mark.parametrize(
    ("programmed_bedtime", "after_bedtime", "expected"),
    [
        # nothing is going to set armed night for a bedtime, so the night is armed night
        (False, False, "armed_night"),
        # the evening before bedtime
        (True, False, "disarmed"),
        # the dark after bedtime has ended
        (True, True, "armed_home"),
    ],
)
async def test_default_transitions_for_occupied_night(
    hass_api: HomeAssistantAPI, programmed_bedtime: bool, after_bedtime: bool, expected: str
) -> None:
    condition_variables = ConditionVariables(
        occupied=True,
        unoccupied=False,
        night=True,
        state=AlarmControlPanelState.PENDING,
        occupied_defaults={"day": AlarmControlPanelState.ARMED_HOME, "night": AlarmControlPanelState.DISARMED},
        after_bedtime=after_bedtime,
        programmed_bedtime=programmed_bedtime,
        occupied_after_bedtime=AlarmControlPanelState.ARMED_HOME,
    )
    selected: list[str] = []
    for state in ("disarmed", "armed_home", "armed_night"):
        checker = await hass_api.build_condition(cv.CONDITIONS_SCHEMA(DEFAULT_TRANSITIONS[state]), validate=True, name=state)
        assert checker
        if hass_api.evaluate_condition(checker, condition_variables):
            selected.append(state)

    assert selected == [expected]


def test_condition_variables_expose_bedtime() -> None:
    variables = ConditionVariables(None, None, True, AlarmControlPanelState.PENDING, {}, bedtime=True).as_dict()

    assert variables["bedtime"] is True
    assert variables["after_bedtime"] is False
    assert variables["programmed_bedtime"] is True
    assert variables["occupied_after_bedtime_state"] == "armed_home"
