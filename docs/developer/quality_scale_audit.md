# Home Assistant Quality Scale Audit

This document provides a comprehensive audit of the AutoArm integration against the [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/).

**Audit Date:** February 2026
**Integration Version:** 0.8.0-beta1
**Auditor:** Automated analysis

## Summary

| Tier | Done | Exempt | Todo | Total |
|------|------|--------|------|-------|
| Bronze | 14 | 3 | 2 | 19 |
| Silver | 5 | 4 | 2 | 11 |
| Gold | 7 | 7 | 7 | 21 |
| Platinum | 1 | 1 | 1 | 3 |
| **Total** | **27** | **15** | **12** | **54** |

**Current Tier Achievement:** Bronze (with most Silver and several Gold requirements met)

**Path to Silver:** Complete `action-exceptions` and `test-coverage` rules.

---

## Bronze Tier

The Bronze tier represents the baseline standard for all integrations.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `action-setup` | Done | Services registered in `async_setup` ([autoarming.py:132-161](../../custom_components/autoarm/autoarming.py)) |
| `common-modules` | Done | Logic separated into `const.py`, `helpers.py`, `hass_api.py`, `calendar.py` |
| `dependency-transparency` | Done | All dependencies are standard HA components declared in `manifest.json` |
| `docs-actions` | Done | Services documented in `services.yaml` and README |
| `docs-high-level-description` | Done | Clear overview in README.md |
| `docs-installation-instructions` | Done | HACS installation documented |
| `entity-event-setup` | Done | Events subscribed in `initialize_*` methods using proper HA tracking functions |
| `runtime-data` | Done | Uses `HassKey[AutoArmData]` for typed runtime data storage |
| `test-before-setup` | Done | Validates config via voluptuous schemas; `ConfigEntryNotReady` on init failure; raises repair issues for invalid transitions |
| `config-flow` | Done | UI config flow for alarm panel, calendars, persons, and occupancy defaults |
| `config-flow-test-coverage` | Done | Config flow and options flow covered by tests |
| `test-before-configure` | Done | Config flow validates entity selections; YAML validated via voluptuous |
| `unique-config-entry` | Done | Unique ID set to domain; `_abort_if_unique_id_configured()` prevents duplicates |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `appropriate-polling` | Exempt | Event-driven integration; calendar polling is configurable |
| `entity-unique-id` | Exempt | Uses fixed entity IDs for integration-scoped singletons |
| `has-entity-name` | Exempt | Entities created via `async_set`, not entity classes |

### Todo Rules

| Rule | Status | Action Required |
|------|--------|-----------------|
| `brands` | Todo | Submit logo/icon to Home Assistant brands repository |
| `docs-removal-instructions` | Todo | Add removal instructions to documentation |

---

## Silver Tier

The Silver tier focuses on reliability and robustness.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `config-entry-unloading` | Done | `shutdown()` method properly cleans up all listeners |
| `docs-configuration-parameters` | Done | Parameters documented in `automated_arming.md` and examples |
| `entity-unavailable` | Done | Entities initialized to "unavailable" when appropriate |
| `integration-owner` | Done | @jeyrb declared as code owner |
| `log-when-unavailable` | Done | Consistent "AUTOARM" prefix; appropriate log levels |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `docs-installation-parameters` | Exempt | Config flow parameters are self-descriptive entity selectors |
| `parallel-updates` | Exempt | No parallel device polling |
| `reauthentication-flow` | Exempt | No authentication required |

### Todo Rules

| Rule | Status | Action Required |
|------|--------|-----------------|
| `action-exceptions` | Todo | Raise `HomeAssistantError` on service failures instead of just logging |
| `test-coverage` | Todo | Increase test coverage threshold to 95% (currently `--cov-fail-under=0`) |

---

## Gold Tier

The Gold tier represents best-in-class user experience.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `docs-data-update` | Done | Update mechanisms documented (events, polling, manual triggers) |
| `docs-examples` | Done | Example configs in `docs/configuration/examples/` |
| `docs-supported-functions` | Done | All features documented in README and automated_arming.md |
| `docs-use-cases` | Done | Use cases illustrated in "Why use alarm control panels?" section |
| `exception-translations` | Done | Issue messages use translation keys with placeholders |
| `repair-issues` | Done | Raises repair issues for invalid transition conditions |
| `reconfiguration-flow` | Done | Options flow allows reconfiguring calendars, persons, occupancy defaults, and no-event mode |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `devices` | Exempt | Orchestrates existing entities; doesn't represent physical devices |
| `discovery` | Exempt | User-configured entities; nothing to discover |
| `discovery-update-info` | Exempt | No discovery |
| `docs-supported-devices` | Exempt | Works with any compatible HA entities |
| `dynamic-devices` | Exempt | No device registry usage |
| `entity-disabled-by-default` | Exempt | All entities are essential |
| `stale-devices` | Exempt | No device registry usage |

### Todo Rules

| Rule | Status | Action Required |
|------|--------|-----------------|
| `diagnostics` | Todo | Implement `diagnostics.py` for debugging support |
| `docs-known-limitations` | Todo | Add dedicated limitations section to docs |
| `docs-troubleshooting` | Todo | Add troubleshooting guide |
| `entity-category` | Todo | Add EntityCategory if refactored to entity classes |
| `entity-device-class` | Todo | Add device classes (e.g., diagnostic for initialized sensor) |
| `entity-translations` | Todo | Refactor to use translation keys for entity names |
| `icon-translations` | Todo | Implement icon translations |

---

## Platinum Tier

The Platinum tier represents technical excellence.

### Completed Rules

| Rule | Status | Notes |
|------|--------|-------|
| `async-dependency` | Done | No external dependencies; fully async using HA APIs |

### Exempt Rules

| Rule | Status | Reason |
|------|--------|--------|
| `inject-websession` | Exempt | No external HTTP calls |

### Todo Rules

| Rule | Status | Action Required |
|------|--------|-----------------|
| `strict-typing` | Todo | Enforce strict typing; add `py.typed` marker; eliminate `Any` types |

---

## Recommendations

### Priority 1: Achieve Silver Tier

1. **`action-exceptions`**: Modify service handlers to raise `HomeAssistantError` with descriptive messages when operations fail.

2. **`test-coverage`**: Set `--cov-fail-under=95` in `pyproject.toml` and add tests to reach threshold.

### Priority 2: Documentation Improvements

1. **`docs-removal-instructions`**: Add a "Removing AutoArm" section explaining how to uninstall via HACS and clean up YAML.

2. **`docs-known-limitations`**: Document known limitations:
   - Advanced features (transitions, buttons, notifications) require YAML configuration
   - Single alarm panel per installation
   - Calendar polling interval limitations

3. **`docs-troubleshooting`**: Add common issues and solutions:
   - Invalid transition conditions (check repair issues)
   - Calendar not updating (verify poll interval)
   - Button not responding (check entity_id)

### Priority 3: Brand Submission

1. **`brands`**: Submit integration logo/icon to [home-assistant/brands](https://github.com/home-assistant/brands) repository.

### Priority 4: Gold Tier Enhancements (Optional)

These would require refactoring to use proper entity classes:

1. **`diagnostics`**: Implement diagnostics to expose configuration and state.
2. **`entity-category`/`entity-device-class`**: Refactor entities to use HA entity classes.
3. **`entity-translations`**: Enable translated entity names.

---

## Code Quality Notes

### Strengths

- Clean separation of concerns across modules
- Comprehensive error tracking via `failures` counter and repair issues
- Rate limiting prevents arming loops
- Proper async/await throughout
- Good test coverage for core functionality
- Consistent logging with "AUTOARM" prefix
- Support for graceful shutdown and reload

### Areas for Improvement

- Some methods in `autoarming.py` are lengthy and could be refactored
- A few `Any` type hints remain that could be more specific
- Entities use `async_set` directly rather than entity classes
- No `diagnostics.py` for debugging support

---

## References

- [Home Assistant Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- [Quality Scale Rules](https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/)
- [Home Assistant Brands Repository](https://github.com/home-assistant/brands)
