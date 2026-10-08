# Known Limitations

## Single Alarm Panel

Auto Arm supports only one alarm control panel per installation.

## YAML for Advanced Features

While core settings (alarm panel, calendars, persons, occupancy defaults) are managed via the UI config flow, advanced features require YAML configuration:

- Transition conditions
- Physical button mappings
- Notification profiles
- Rate limiting
- Per-calendar state pattern overrides and poll intervals

## Calendar Polling

Calendar events are detected by polling, not real-time events. The default poll interval is 15 seconds per calendar. Very short calendar events (shorter than the poll interval) may be missed. This is a Home Assistant limitation, necessitated by
the different styles of calendar supported, for example, Google Calendars.

## Manual Intervention Lock

When a manual intervention occurs (button press, mobile action, or alarm panel change), Auto Arm will not override the state until the next occupancy change or another manual intervention. This is by design, but can be surprising if you expect automatic state changes to resume immediately.

## Alarm Panel Compatibility

Auto Arm works with any entity that implements the `alarm_control_panel` domain. However, some panels may not support all alarm states (e.g., `armed_vacation` or `armed_custom_bypass`). When Auto Arm uses the panel's actions, as it does by default, an unsupported state is rejected by the panel, a warning is logged, and the panel is left as it was. Panels that need a code to arm or disarm can't be changed through their actions, since Auto Arm has no code to give.

## Python and Home Assistant Compatibility

The component automatically runs the entire test suite for the latest Home Assistant, and the 6 months old version, so that broad range of compatibility is maintained for the majority of Home Assistant users.

2026.2 was the last Home Assistant release to support Python 3.13. This has been supported for longer than the usual 6 months, however automated testing will drop when 2026.11 is released in November. Auto Arm *may* continue to work with older releases, but it will no longer be assured.

If you can't move off Python 3.13 then don't upgrade Auto Arm beyond the last supported version.
