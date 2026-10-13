# 2.0.0

## 🚨 Breaking changes

Python 3.13 support removed, along with support for Home Assistant versions 2026.3 and earlier.

Newer releases may work on older installations, but there will no longer
be the automated testing to assure it.

Auto Arm will continue to be automatically tested against a **6 month** release range of Home Assistant.

There are no other known breaking changes - existing configurations will be migrated as-is.

## ✨ Enhancements

Starting from v2.0.0, Auto Arm now has an opinion about the easiest way to set up a house for auto arming, and streamlined the configuration around that. All of the previous advanced options remain available, to tune things just the way you like.

Existing installations will have configuration automatically migrated where changed, although recommended to update to the new recipe for ease of use.


### New Terms

- **Bedtime** - defined separately from sunrise or sunset, and aligns better with Home Assistant definitions of *Armed Night* as being organized around sleeping patterns rather than darkness.
  - Previously conflated with *diurnal*, which now means sun-driven timing, within any constraints provided.
- **Morning** - used to refer to the *constrained* sunrise, using the no earlier/later times that have always been available
- **Evening** - like *morning* for sunset times


### Recommended Recipe
A new [recommended recipe](./configuration/examples/recommended_recipe.md) has been added, and the integration settings re-organized to make this easier to set up.

Set up is now a single page asking for the alarm panel, bedtime sensor, calendar and people, with a link to the recipe and advanced stuff in their own boxes. Each step now instructions and an optional direct link to create any missing calendar, alarm panel or times of the day sensor

None of this removes existing functionality, and all of it can be overridden or tuned for your needs. It is, however, the simplest to set up with the least ongoing administration, of any automated way to manage alarms.

#### Out of the Box
  If there is no configuration given, other than the name of the alarm control panel:

- Diurnal (`sun` integration) is used as the back-stop to control day/night ('diurnal') alarm settings, alarm will be *Disarmed* during the day and *Armed Night* at night

#### Times the Day Sensor for Bedtime
- Add a [Times of the Day](https://www.home-assistant.io/integrations/tod/) integration to manage bedtime for *Armed Night* so it can reflect how you live rather than what the sunrise/sunset is doing over the course of the year
- The `sun` integration is still used for any gap between daylight and bedtime, so the house will be *Armed Home* for dark evenings prior to bedtime, and likewise for dark mornings

#### Calendar Set Up
- Add a calendar to use *Armed Vacation* state
  - Can also use calendars for any other state, for example as an alternative to a *Times of the Day* sensor to manage bedtimes, or to set *Disarmed* time bands.
- Local calendars can be used with repeated events to reduce maintenance, or remote calendars, like Google, integrated via Home Assistant

#### People with Device Trackers
- Every *Person* created in Home Assistant is pre-added to the occupied list
  - New installs only, existing installs keep their settings and can change them in the **Advanced** section
- If people have *Device Trackers* associated with them, typically the Home Assistant mobile app, then *Occupancy* is automatically factored into alarm state
  - Where *presence* is available, alarm states default to *Disarmed* for occupied daytime, *Armed Home* for occupied evening


### Times of the Day Sensors
- [Times of the Day](https://www.home-assistant.io/integrations/tod/) sensors can now set the alarm state, as an alternative to a recurring calendar event
  - Choose the bedtime sensor up front, and sensors for the other alarm states in the new **Advanced - Times of the Day Sensor** section of the options
  - Changes have a new `tod` source, included in the default `quiet` notification profile, and are linked in the logbook to the sensor's state change

### Bedtime
- A specific *Times of the Day* sensor for `armed_night`
  -  `armed_night` switches on / off by the Times of Day, using the Home Assistant definition of `armed_night` as bed time
    - at whatever time of day or night that is, or however light or dark it is, so suitable for shift workers and high latitudes as well as everyone else
  - Sunrise and sunset during bedtime are ignored
  - When bedtime ends the state is worked out from occupancy and the sun, and again at sunrise if it ended in the dark
  - With everyone out bedtime is ignored, and someone coming home trips it back on
  - A live calendar event takes priority, so a bedtime sensor can be left running through a vacation in the calendar

### Physical Buttons
- New **Buttons** section in the options, for any number of buttons for each alarm state and for a reset, each with a delay in seconds
  - The delay is zero unless set, other than for `armed_away`, which starts at 120 seconds
  - Buttons in YAML are copied into the options the first time, and the options used from then on
- The reset button always gets a notification in reply, even when the state stays as it is, and says if it has cancelled a delayed change from another button

### Alarm Panels That Need a Code
- New **Alarm panel code** in the **Advanced** section of the options, passed to the alarm panel's actions when arming or disarming
  - Stored encrypted, never shown again once set, and left out of logs and diagnostics, see [Panels That Need a Code](configuration/create_panel.md#panels-that-need-a-code) for what that does and doesn't protect against
- A repair is raised if the alarm panel wants a code and there isn't one, either set in Auto Arm or as the Home Assistant default code for the panel

### Notifications
- The alarm states are now the humane versions, e.g. "Armed Night" rather than `armed_night`
- Changes made by a Times of the Day sensor name the sensor, e.g. "by Bedtime Times of the Day sensor"
- New installs have `supernotify.notify` as the notification action if Supernotify is already installed
- With Supernotify installed, the options have **Targets**, to pick people, entities, devices, areas or labels, **Custom targets** for addresses and numbers, and **Deliveries** to limit which Supernotify deliveries are used
  - These replace **Notification Targets**, and targets already set are carried over as custom targets
- A warning is logged at start up if notifications are enabled using `notify.send_message` with no **Notification Targets**, since nothing can then be sent
- With Supernotify as the notification action
  - New **Priority** options for scheduled changes (Times of the Day sensor, calendar, sunrise, sunset), occupancy changes, and manual changes (alarm panel, button, mobile action, voice)
  - Scenarios are applied for the new alarm state, such as `autoarm-armed_away` or `autoarm-disarmed`, plus `autoarm-armed` for any armed state, for Supernotify scenarios of those names to pick up
- Mobile action titles are now translated, and actions that would do nothing are left out, such as *Disarm* when already disarmed or *Arm Away* when already armed away
- The options now say that only a simple message can be sent when Supernotify isn't available
- The YAML `notify` section is **deprecated**, replaced by deeper Supernotify integration in the options, and will be removed when Home Assistant 2027.4 is released
  - It still works until then, with a repair raised as a reminder

### Calendar Occupancy Override
- New switch so that someone coming home on the last day of an `armed_away` or `armed_vacation` calendar event ends the event there and then, rather than at its end time
  - On by default, including for existing installs, and applies to one-off as well as recurring events
  - Needs an arrival that day, so someone always shown as home, for example without location sharing, doesn't end the event
  - Part of the [recommended recipe](./configuration/examples/recommended_recipe.md)

### Simplified Settings Panel
- The options are grouped by what drives the alarm state
  - **Presence** has the arriving and leaving triggers, and the calendar states presence can override
  - **Diurnal - Sun** has the occupied states, and the morning and evening triggers with their earliest and latest times, where morning is sunrise and evening is sunset, each kept within those times
    - **Occupied state between morning and evening**, default state between morning (sunrise with any constraints) and evening (sunset with any constraints)
    - **Occupied state between bedtime and morning** is new, for the dark after bedtime ends, and is `armed_home` unless changed
    - **Occupied state between evening and bedtime**, as before for the night
    - If nothing sets `armed_night` for bedtime that day, neither a bedtime sensor nor an `armed_night` calendar event, it's `armed_night` from evening whatever the evening state is set to
  - **Buttons** has the physical buttons
  - **Notifications** comes after these, ahead of the advanced sections, **Advanced - Times of the Day Sensor** and **Advanced**
  - **Advanced** holds **Change state using the alarm panel's actions** and the calendar end settings, now **When a calendar arming override ends** and **When a calendar disarming override ends**
    - The rate limit, and the delays after someone arrives or leaves home, are now set here rather than in YAML
    - `rate_limit` and `occupancy.delay_time` in YAML are copied into the options the first time, and the options used from then on
    - The delay after someone leaves home is now 2 minutes unless set, in YAML or the options, where before there was none
- The bedtime sensor, calendars and people are now **Bedtime - Times of the Day Sensor**, **Occupancy - Calendars** and **Presence - People for Occupancy Based Arming**

## 📚 Documentation
  - New [Recommended Recipe](configuration/examples/recommended_recipe.md) for a complete set up that handles day/night, leaving home and extended vacations.

## 📝 Other changes
- Built and tested against Home Assistant 2026.10.0
- Context for the *Logbook* and *Activity* views in Home Assistant improved
- Compatibility added for the Voluptuous->Probatio change in recent versions of Home Assistant while maintaining backward compatibility

# 1.4.0

## ✨ Enhancements

### Calendar Triggers
- New and changed calendar events can now be picked up faster than the usual Home Assistant 15 minute poll interval, when the current or next event changed
  - Internally, it subscribes to the calendar entity state, which is changed by Home Assistant when a calendar is edited
- Calendar-triggered notifications landing close together, such as one event ending as another begins, are now coalesced into a single net-change notification instead of two, with a configurable `notify_grace_period` (YAML, default one minute)
- Calendar Events can suppress sunrise/sunset (diurnal events) so that if you have an ARMED_NIGHT calendar event, the alarm will go to a daytime state when that event ends, rather than being immediately overridden by state of `sun`
  - Previously alarm state could flap between armed/disarmed in the morning, especially where sunrise differs hugely across the year
  - The single **Arming state when a calendar event ends** is split into separate settings for an armed and a disarmed event ending, with new **By occupancy** and **By occupancy and sun** choices, and a changed **Auto** as the default
    - **By occupancy** ignores day and night: an armed event ending disarms, or arms away if everyone is out, and a disarmed event ending arms home, or away if everyone is out
    - **By occupancy and sun** works the state out from occupancy and day or night, as `auto` did before, and is `auto_sun` in YAML
    - **Auto** is now **By occupancy and sun** only if the sunrise or sunset trigger is active that day, otherwise **By occupancy**, so with the default triggers an event ending goes by occupancy alone
    - Existing settings carry over to both, so an existing `auto` takes on the new **Auto** behaviour - choose **By occupancy and sun** to keep the old one
    - Other resets, such as sunrise or the reset button, now return to the live event's state, or follow the setting for the kind of event that last ended today, or with no calendar activity today, work as if there were no calendars. Before, the no-event setting applied to them on any day
### Trigger Control
- New **Triggers** section in the options, to choose what starts a re-evaluation of the alarm state
  - **Sunrise** and **Sunset** can each be on, off, or auto, where auto switches the trigger off on days with calendar activity and back on for days without
  - **Someone arrives home** and **Someone leaves home** can each be switched off
  - Triggers only change when the state is worked out, not how - a reset button, action or calendar event ending still work it out as usual, with day and night still choosing between armed states
### Simplified Settings Panel
- New **Advanced** section in the options, holding **Change state using the alarm panel's actions**, the occupied day and night defaults, and the calendar end settings
### Notifications
- The **Notifications** section in the options is now last, matching where actions sit at the bottom of an automation
- Added **Extra Notification Data** to the options, for extra service data such as mobile app notification actions or a channel, without needing YAML
## 🐛 Bug fixes

- Auto Arm no longer moves the alarm panel through `pending` to recalculate the state, such as when a calendar event ends
  - The panel goes straight to the new state, so there is one `autoarm_change` event from the previous state rather than two via `pending`
  - No more spurious notifications, or automations triggered by `pending`, and the panel can't be left in `pending` if the change doesn't happen


# 1.3.0
- Improved Home Assistant alignment
  - Auto Arm's sensors are now proper Home Assistant entities, on an **Auto Arm** device, so they can be renamed, given an area, or disabled in the UI, and are removed with the integration
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
  - When using actions, `pending` is kept within Auto Arm rather than set on the panel, since panels have no action for it
  - `armed_custom_bypass` can now be set using the panel's actions
- Fixed Auto Arm mistaking its own change for a manual one, when using the panel's actions, when the change was triggered by another state change, such as a button press. This could send a panel changed notification, and hold off automatic changes as a manual intervention would
- Buttons only act on a press, so a binary sensor button turning back `off`, or a button dropping out or coming back online, no longer counts as a manual intervention
- Morning and evening, which are sunrise and sunset kept within their earliest and latest times, now decide day and night for everything that works out the state. Before, only the triggers went by them, so a latest time ahead of the sun did nothing, and anything else re-evaluating before an earliest time, such as someone arriving home, went by the sun
- Changes held back to an earliest time, or by an occupancy or button delay, keep their source, and show as deferred from it, such as `deferred from sunrise`, in the logbook and **Last calculation** sensor. Before, a deferred sunrise, sunset or startup lost its source
- Fixed sunrise and sunset working out the state for the wrong side of the day, when seen before the `sun` entity had changed state. A sunrise could arm for the night, and a sunset do nothing until the latest sunset time
- The logbook names the cause against the alarm panel's change, such as `AutoArm (sunrise)` or `AutoArm (times of the day sensor Bedtime)`, since newer Home Assistant versions show only the name there

# 1.2.0
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

# 1.1.5
- Fixed compatibility issues with `notify.send_message` new style notifications
- Move documentation site build to *properdocs*
- Built and tested against Home Assistant 2026.9.1

# 1.1.4
- Show **Alarm Control Panel** entity in config UI, and allow it to be changed
- Added translations for es,hi,nl,pl,pt and zh-Hans languages

# 1.1.3
- Dependencies updated.
- Tests fixed for recent HA versions

# 1.1.2
- Dependencies and tests updated for both py3.13 (HomeAssistant 2026.2.x ) and py3.14 with recent version of HA.
- Tests fixed for recent HA versions which start a timer for `sun` integration

# 1.1.1
## Diagnostics
- Improvements to `change_context` passed to events
## Notifications
- By default, only notify on public alarm states, e.g. ignore `pending`
## Internals
- Clean up new issues from updated mypy

# 1.1.0
## Auto Transitions
- `reset_decision` attribute now records what drove decision for state reset
## Occupancy
- Occupancy changes can selectively override recurring calendar event based states, with configurable list of states, defaulting to `disarmed`,`armed_home` and `armed_night`. So if the calendar says `disarmed` but you've left the house it will override automatically to `armed_away`.
  - Effects occupancy driven changes, which continue even if a calendar event in progress, and start of calendar event, which won't
  override an occupancy state
## Events
- An `autoarm_change` event is now fired on the Home Assistant bus when alarm state is changed by autoarm
## International
- Strings now translated into Italian, French, German and Japanese
## Other
- Removed noisy internal alarm states from config dialogs
- Add context for every arming change, in debug logs and the `autoarm_change` event

# 1.0.0
## Configuration
- The basic setup, along with calendars, occupancy and some tuning is now UI based using Home Assistant ConfigFlow and ConfigEntry, with automated migration of existing YAML config
## Occupancy
- Logic now clearly distinguishes occupancy not configured vs occupied and unoccupied
## Auto Transitions
- Refreshed logic, including for undefined occupancy
## Notifications
- Actionable Notifications set by default when Supernotify used for notification
- Advanced config in YAML can set targets for notifications, per profile or in `common` profile
## Fixes
- Notifications now better respect which alarm states are in scope per profile


# 0.8.0
## Notifications
- All arm changes can be notified if configured
- Support for Supernotify scenarios
- Any profiles can be used now, with `normal` and `quiet` retained as defaults
  - Profiles are defined by the `source`, with `quiet` defaulting to `button` and `panel` for backward compatibility
  - Profiles can be further refined by listing under `state` only changes only to or from the list of states
- Notification data can have `source` and `profile` populated by adding key with null value to config
## Calendar Integration
- Calendar event matching will look anywhere in description or summary not only the start of summary
- Calendar event matching looks for alarm states constants anywhere in summary or description, for example `ARMED_HOME`
    - This is in addition to any regular expression matches set up, for example `Trip.*` mapped to `ARMED_VACATION`
## Internal
- `Notifier` and `AppHealthTracker` refactored out of main class
- Test coverage massively improved for notifications

# 0.7.1
## Calendar Integration
- Better handling of changes or removal of calendar entries currently driving live alarm state
## Internal
- All dependencies now managed by uv and `pyproject.toml`

# 0.7.0
## Fixes
- Alarm Control Panel attributes no longer overwritten
- Entity naming corrected for Home Assistant consistency, now `sensor.autoarm_XXXX` or `binary_sensor.autoarm_XXXX`
- Configuration exposure moved from entity to `enquire_configuration` action, to avoid huge output to Developer states panel
- Exposed `reset_state` action
- Exposed `sensor.autoarm_failures` entity
- Home Assistant Quality Scale audited and improvements started

# 0.6.6
## Features
- New `reset_service` action available
- Delay time now available for occupancy checks, separately selectable for ->`home` and ->`not_home`
## Internal
- Simplified logic for delayed actions

# 0.6.5
## Features
- Now exposes a `last_intervention` entity for button, mobile action or direct panel change
- Panel state now given a `changed_by` attribute value, and this now used to prevent events from changes induced by autoarm being treated as interventions
- More attributes on `last_calculation`
- Logging noise reduction

# 0.6.4
## Features
- Now exposes a `last_calculation` entity with the key facts used
## Internal
- Integration tests now set up alarm panels

# 0.6.3
## Fixes
- Incorrect import from test
- Reinstate config allow extra
- Prevent exposed config entity including datetime objs, and ensure with new test

# 0.6.0
## Features
- Internal logic for automatic state calc replaced by regular Home Assistant conditions
- Configuration cleaned up into logical, extensible sections
## Internal
- All manual actions now recorded as interventions
- Regular housekeeping for interventions and calendar tracking
- Further typing with ChangeSource and AlarmControlPanelState
- Primary class documentation page

# 0.5.2
- Clean up dead code for mobile actions

# 0.5.1
- Clean up the pre-calendar bedtime config and mechanism
- Add new `occupied_daytime_state` config to allow choice, e.g. between `armed_home` and `disarmed`

# 0.5.0
- Productionizing of private code
- Component now reloadable
- Multiple calendar integration
