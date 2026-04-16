import logging

import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import config_validation as cv

from custom_components.autoarm.hass_api import ConditionErrorLoggingAdaptor, ConditionVariables, HomeAssistantAPI

_LOGGER = logging.getLogger(__name__)


async def test_evaluate_with_bad_condition(hass_api: HomeAssistantAPI) -> None:

    condition = cv.CONDITIONS_SCHEMA({"condition": "xor"})
    with pytest.raises(HomeAssistantError):
        await hass_api.build_condition(condition, strict=True)


async def test_evaluates_good_true_condition(hass_api: HomeAssistantAPI) -> None:
    cvars = ConditionVariables(True, False, False, AlarmControlPanelState.DISARMED, {})
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ autoarm.occupied and not autoarm.night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is True


async def test_evaluates_good_false_condition(hass_api: HomeAssistantAPI) -> None:

    cvars = ConditionVariables(True, False, False, AlarmControlPanelState.DISARMED, {})
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ autoarm.occupied and autoarm.night}}""",
    })
    checker = await hass_api.build_condition(condition, strict=True)
    assert checker is not None
    assert hass_api.evaluate_condition(checker, cvars) is False


async def test_evaluates_with_undefined_occupancy(hass_api: HomeAssistantAPI) -> None:
    cvars = ConditionVariables(None, None, False, AlarmControlPanelState.DISARMED, {}, None, None, None)
    condition = cv.CONDITIONS_SCHEMA({
        "condition": "template",
        "value_template": """
                        {{ autoarm.occupied and not autoarm.night}}""",
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


def test_raise_issue_no_hass() -> None:
    api = HomeAssistantAPI(None)
    api.raise_issue("id", "key", {})


async def test_build_condition_no_hass() -> None:
    api = HomeAssistantAPI(None)
    with pytest.raises(ValueError, match="HomeAssistant not available"):
        await api.build_condition([])


def test_evaluate_condition_no_hass() -> None:
    api = HomeAssistantAPI(None)
    with pytest.raises(ValueError, match="HomeAssistant not available"):
        api.evaluate_condition(lambda _: True)


def test_evaluate_condition_raises_exception(hass_api: HomeAssistantAPI) -> None:
    def bad_cond(_vars: object) -> bool:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        hass_api.evaluate_condition(bad_cond)


def test_condition_error_logging_adaptor_captures_container() -> None:
    from homeassistant.exceptions import ConditionError, ConditionErrorContainer

    adaptor = ConditionErrorLoggingAdaptor(_LOGGER)
    err = ConditionError("test error")
    container = ConditionErrorContainer("outer", errors=[err])
    adaptor.capture((container,))
    assert len(adaptor.condition_errors) == 1


def test_condition_error_logging_adaptor_captures_bare_error() -> None:
    from homeassistant.exceptions import ConditionError

    adaptor = ConditionErrorLoggingAdaptor(_LOGGER)
    err = ConditionError("bare error")
    adaptor.capture((err,))
    assert len(adaptor.condition_errors) == 1


def test_condition_error_logging_adaptor_error() -> None:
    from homeassistant.exceptions import ConditionError, ConditionErrorContainer

    adaptor = ConditionErrorLoggingAdaptor(_LOGGER)
    err = ConditionError("test error")
    container = ConditionErrorContainer("outer", errors=[err])
    # msg needs 2 %s because impl calls logger.error(msg, args_tuple, kwargs_dict)
    adaptor.error("%s %s", container)
    assert len(adaptor.condition_errors) == 1
