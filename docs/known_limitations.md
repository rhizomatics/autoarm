# Known Limitations

## Single Alarm Panel

AutoArm supports only one alarm control panel per installation.

## YAML for Advanced Features

While core settings (alarm panel, calendars, persons, occupancy defaults) are managed via the UI config flow, advanced features require YAML configuration:

- Transition conditions
- Physical button mappings
- Notification profiles
- Diurnal (sunrise/sunset) settings
- Rate limiting
- Per-calendar state pattern overrides and poll intervals

## Calendar Polling

Calendar events are detected by polling, not real-time events. The default poll interval is 15 seconds per calendar. Very short calendar events (shorter than the poll interval) may be missed. This is a Home Assistant limitation, necessitated by 
the different styles of calendar supported, for example, Google Calendars.

## Manual Intervention Lock

When a manual intervention occurs (button press, mobile action, or alarm panel change), AutoArm will not override the state until the next occupancy change or another manual intervention. This is by design, but can be surprising if you expect automatic state changes to resume immediately.

## Alarm Panel Compatibility

AutoArm works with any entity that implements the `alarm_control_panel` domain. However, some panels may not support all alarm states (e.g., `armed_vacation` or `armed_custom_bypass`). AutoArm will attempt to set unsupported states, which may fail silently depending on the panel implementation.
