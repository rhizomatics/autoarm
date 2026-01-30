# Changelog

## 0.8.0
### Notifications
- All arm changes can be notified if configured
- Support for Supernotify scenarios
- Any profiles can be used now, with `normal` and `quiet` retained as defaults
  - Profiles are defined by the `source`, with `quiet` defaulting to `button` and `panel` for backward compatibility
  - Profiles can be further refined by listing under `state` only changes only to or from the list of states
- Notification data can have `source` and `profile` populated by adding key with null value to config
### Calendar Integration
- Calendar event matching will look anywhere in description or summary not only the start of summary
- Calendar event matching looks for alarm states constants anywhere in summary or description, for example `ARMED_HOME`
    - This is in addition to any regular expression matches set up, for example `Trip.*` mapped to `ARMED_VACATION`
## Internal
- `Notifier` and `AppHealthTracker` refactored out of main class
- Test coverage massively improved for notifications

## 0.7.1
### Calendar Integration
- Better handling of changes or removal of calendar entries currently driving live alarm state
### Internal
- All dependencies now managed by uv and `pyproject.toml`
## 0.7.0
### Fixes
- Alarm Control Panel attributes no longer overwritten
- Entity naming corrected for Home Assistant consistency, now `sensor.autoarm_XXXX` or `binary_sensor.autoarm_XXXX`
- Configuration exposure moved from entity to `enquire_configuration` action, to avoid huge output to Developer states panel
- Exposed `reset_state` action
- Exposed `sensor.autoarm_failures` entity
- Home Assistant Quality Scale audited and improvements started
## 0.6.6
### Features
- New `reset_service` action available
- Delay time now available for occupancy checks, separately selectable for ->`home` and ->`not_home`
### Internal
- Simplified logic for delayed actions
## 0.6.5
### Features
- Now exposes a `last_intervention` entity for button, mobile action or direct panel change
- Panel state now given a `changed_by` attribute value, and this now used to prevent events from changes induced by autoarm being treated as interventions
- More attributes on `last_calculation`
- Logging noise reduction
## 0.6.4
### Features
- Now exposes a `last_calculation` entity with the key facts used
### Internal
- Integration tests now set up alarm panels
## 0.6.3
### Fixes
- Incorrect import from test
- Reinstate config allow extra
- Prevent exposed config entity including datetime objs, and ensure with new test
## 0.6.0
### Features
- Internal logic for automatic state calc replaced by regular Home Assistant conditions
- Configuration cleaned up into logical, extensible sections
### Internal
- All manual actions now recorded as interventions
- Regular housekeeping for interventions and calendar tracking
- Further typing with ChangeSource and AlarmControlPanelState
- Primary class documentation page
## 0.5.2
- Clean up dead code for mobile actions

## 0.5.1
- Clean up the pre-calendar bedtime config and mechanism
- Add new `occupied_daytime_state` config to allow choice, e.g. between `armed_home` and `disarmed`

## 0.5.0
- Productionizing of private code
- Component now reloadable
- Multiple calendar integration
