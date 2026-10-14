---
tags:
  - faq
  - support
  - help
title: Frequently Asked Questions
description: Answers to support queries
---
# Frequently Asked Questions

## Why is Alarm State Not Changing?

**Check the initialized sensor**: Look at `binary_sensor.autoarm_initialized`, on the Auto Arm device in **Settings** > **Devices & Services**. If it's off, there is a configuration issue, and its attributes show which stage of setup failed. `sensor.autoarm_failures` counts setup and runtime errors.

**Check the alarm panel's actions**: Auto Arm arms and disarms using the panel's actions. If the panel needs a code that Auto Arm hasn't been given, a repair is raised, and if the action is rejected, a warning is logged and the panel is left alone. See [Create Panel](../configuration/create_panel.md#how-auto-arm-changes-the-panel).

**Check the last calculation sensor**: `sensor.autoarm_last_calculation` shows when Auto Arm last worked out the state, with attributes for what it decided and why, such as `reset_decision`.

**Check for manual intervention lock**: After a manual change (button press, mobile action, panel change), Auto Arm will not override the state until the next occupancy change. Use the `autoarm.reset_state` service to clear the lock.

**Check transition conditions**: Open Settings > System > Repairs to see if any transition conditions have validation errors. Fix the conditions in your YAML configuration and reload.

## Why are Calendar Events Not Detected?

**Check poll interval**: Calendar events are detected by polling. If events are very short, increase the poll interval or ensure events span at least 15 minutes.

**Check state patterns**: Verify that your calendar event summaries match the configured state patterns. The default patterns are `Away`, `Home`, `Night`, `Disarmed`, and `Vacation`/`Holiday`. Custom patterns use regex matching.

**Check the last calendar event sensor**: Look at `sensor.autoarm_last_calendar_event`, on the Auto Arm device, for the most recently detected event.

## Why are Notifications Not Sending?

**Check notify profile configuration**: If the deprecated YAML `notify` section is used, notifications require at least one non-common profile to match. The `common` profile only provides base configuration (service, data) that is merged into matched profiles, with default `silent` and `normal` profiles created if no explicit ones given.

**Check the service name**: Ensure the notify service exists. The `notify.` prefix is stripped automatically, so `notify.mobile_app` becomes a call to the `mobile_app` service in the `notify` domain.
