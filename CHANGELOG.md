# Changelog

## 1.3.0
- Improved Home Assistant alignment
  - AutoArm's sensors are now proper Home Assistant entities, on an **AutoArm** device, so they can be renamed, given an area, or disabled in the UI, and are removed with the integration
  - Entity ids are unchanged, though some states are different:
    - `binary_sensor.autoarm_initialized` is now `on` or `off` rather than `valid` or `invalid`
    - `sensor.autoarm_last_calculation` is now the time of the last calculation, with whether it changed the state in the `changed` attribute, rather than `True` or `False`
    - The last calculation, intervention and calendar event sensors are `unknown` until there's something to show, rather than `unavailable`
  - The initialized and failures sensors are diagnostic, and the failures count keeps long term statistics
  - Entity names are translated
  - Home Assistant Context is passed down to all actions and state changes so each can be traced back to a cause, either something external like a button press or action call, or Auto Arm's internal mechanisms
  - Changes Auto Arm makes show what caused them in the logbook, from a new `autoarm_triggered` event, rather than the alarm panel action Auto Arm called, whether from its own schedule or calendar, or a button, mobile action, occupancy change or voice command, which the event links back to
- New installs change the alarm panel using its actions by default, rather than setting its state directly
  - Existing installs keep their current setting, and can switch with **Change state using the alarm panel's actions** in the options
  - When using actions, `pending` is kept within AutoArm rather than set on the panel, since panels have no action for it
  - `armed_custom_bypass` can now be set using the panel's actions
- Fixed AutoArm mistaking its own change for a manual one, when using the panel's actions, when the change was triggered by another state change, such as a button press. This could send a panel changed notification, and hold off automatic changes as a manual intervention would
- Buttons only act on a press, so a binary sensor button turning back `off`, or a button dropping out or coming back online, no longer counts as a manual intervention

## 1.2.0
- Support for Alarm Control Panels, such as Alarmo, that require direct service calls to change state. Contributed by @tabascoz
  - Switched on by **Change state using the alarm panel's actions** in the options
  - Panels with an exit delay no longer have their final change to armed treated as a manual intervention
- The improved `supernotify.notify` action can now be used for notifications, original one still works
  - Offered in the **Notification Action** list when Supernotify is installed
- The **Notification Action** chosen in the options is now used rather than the YAML default, and notifications work without any YAML
- Assist, the native voice and chat agent for Home Assistant, can now be used to arm and disarm the panel, and get an explanation for the current armed state.
  - This is non-AI, so conversation flexibility is limited, however doesn't require any AI subscription or local service.
  - Arming and explaining are on by default. Disarming by voice is off by default, since no code is asked for, and can be switched on in the options
  - Using speech-to-text requires a Nabu Casa subscription, or use of the on device STS if app and device support it
## 1.1.5
- Fixed compatibility issues with `notify.send_message` new style notifications
- Move documentation site build to *properdocs*
- Built and tested against Home Assistant 2026.9.1

## 1.1.4
- Show **Alarm Control Panel** entity in config UI, and allow it to be changed
- Added translations for es,hi,nl,pl,pt and zh-Hans languages

## 1.1.3
- Dependencies updated.
- Tests fixed for recent HA versions
## 1.1.2
- Dependencies and tests updated for both py3.13 (HomeAssistant 2026.2.x ) and py3.14 with recent version of HA.
- Tests fixed for recent HA versions which start a timer for `sun` integration
## 1.1.1
### Diagnostics
- Improvements to `change_context` passed to events
### Notifications
- By default, only notify on public alarm states, e.g. ignore `pending`
### Internals
- Clean up new issues from updated mypy
## 1.1.0
### Auto Transitions
- `reset_decision` attribute now records what drove decision for state reset
### Occupancy
- Occupancy changes can selectively override recurring calendar event based states, with configurable list of states, defaulting to `disarmed`,`armed_home` and `armed_night`. So if the calendar says `disarmed` but you've left the house it will override automatically to `armed_away`.
  - Effects occupancy driven changes, which continue even if a calendar event in progress, and start of calendar event, which won't
  override an occupancy state
### Events
- An `autoarm_change` event is now fired on the Home Assistant bus when alarm state is changed by autoarm
### International
- Strings now translated into Italian, French, German and Japanese
### Other
- Removed noisy internal alarm states from config dialogs
- Add context for every arming change, in debug logs and the `autoarm_change` event
## 1.0.0
### Configuration
- The basic setup, along with calendars, occupancy and some tuning is now UI based using Home Assistant ConfigFlow and ConfigEntry, with automated migration of existing YAML config
### Occupancy
- Logic now clearly distinguishes occupancy not configured vs occupied and unoccupied
### Auto Transitions
- Refreshed logic, including for undefined occupancy
### Notifications
- Actionable Notifications set by default when Supernotify used for notification
- Advanced config in YAML can set targets for notifications, per profile or in `common` profile
### Fixes
- Notifications now better respect which alarm states are in scope per profile


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
