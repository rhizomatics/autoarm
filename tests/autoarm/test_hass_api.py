import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import config_validation as cv

from custom_components.autoarm.hass_api import ConditionVariables, HomeAssistantAPI


async def test_evaluate_with_bad_condition(hass_api: HomeAssistantAPI) -> None:

    condition = cv.CONDITIONS_SCHEMA({"condition": "xor"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_condition(condition, strict=True)


async def test_evaluates_good_true_condition(hass_api: HomeAssistantAPI) -> None:
    cvars = ConditionVariables(True, False, AlarmControlPanelState.DISARMED, {})
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ autoarm.occupied and not autoarm.night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is True


async def test_evaluates_good_false_condition(hass_api: HomeAssistantAPI) -> None:

    cvars = ConditionVariables(True, False, AlarmControlPanelState.DISARMED, {})
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ autoarm.occupied and autoarm.night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is False


async def test_evaluates_ignores_missing_vars(hass_api: HomeAssistantAPI) -> None:
    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    checker = await hass_api.build_condition(condition, strict=False)
    assert checker is not None
    assert hass_api.evaluate_condition(checker) is False


async def test_evaluates_detects_missing_vars(hass_api: HomeAssistantAPI) -> None:

    condition = cv.CONDITIONS_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    with pytest.raises(ConditionError):
        await hass_api.build_condition(condition, strict=True, validate=True)
