# Create an Alarm Panel

If you don't already have an alarm panel, set up a default manual as below, which creates the
state machine for armed/disarmed status. This is all you need in the way of alarm support for AutoArm to function.

You can also choose whether a PIN code is needed or not to arm or disarm. AutoArm has its own delay time
handling for buttons, so recommended to keep the times at zero if not needed for any other purposes.

```yaml
alarm_control_panel:
  - platform: manual
    name: Home Alarm Control
    code_arm_required: false
    arming_time: 0
    delay_time: 0
    disarm_after_trigger: false
    trigger_time: 0
```

This can then be added to AutoArm like, notice how the `name` is made lower case and spaces replaced
with underscores to create an `entity_id`.

```yaml
autoarm:
  alarm_panel:
    entity_id: alarm_panel.home_alarm_control
```
