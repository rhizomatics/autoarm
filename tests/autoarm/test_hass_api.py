
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from custom_components.autoarm.hass_api import ConditionVariables, HomeAssistantAPI


async def test_evaluate_with_bad_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITION_SCHEMA({"condition": "xor"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_condition(condition, strict=True)


async def test_evaluates_good_true_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    cvars = ConditionVariables(occupied=True, night=False)
    condition = cv.CONDITION_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ occupied and not night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is True


async def test_evaluates_good_false_condition(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    cvars = ConditionVariables(occupied=True, night=False)
    condition = cv.CONDITION_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ occupied and night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is False


async def test_evaluates_ignores_missing_vars(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)
    condition = cv.CONDITION_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    checker = await hass_api.build_condition(condition, strict=False)
    assert checker is not None
    assert hass_api.evaluate_condition(checker) is False


async def test_evaluates_detects_missing_vars(hass: HomeAssistant) -> None:
    hass_api = HomeAssistantAPI(hass)

    condition = cv.CONDITION_SCHEMA({"condition": "template", "value_template": "{{ notification_priority == 'critical' }}"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_condition(condition, strict=True)
