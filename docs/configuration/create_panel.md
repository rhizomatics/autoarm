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

## Selecting the Alarm Panel in AutoArm

The alarm panel entity is selected during the AutoArm UI config flow. Go to **Settings** > **Devices & Services** > **Add Integration**, search for **AutoArm**, and select your alarm panel entity in the first step.

## How AutoArm Changes the Panel

AutoArm changes the panel's state by calling its actions, `alarm_control_panel.alarm_arm_away`,
`alarm_control_panel.alarm_disarm` and so on, just as a dashboard card or automation would. This works for
a *manual* panel, and for integrations that do more than hold a state when armed or disarmed, such as
[Alarmo](https://github.com/nielsfaber/alarmo), which arms its child areas when its master panel is armed.

This is controlled by **Change state using the alarm panel's actions** in the AutoArm options, which is on
for new installs.

- The panel mustn't need a code to arm or disarm, as AutoArm doesn't have one to give it.
- If the action fails, or doesn't change the state, AutoArm leaves the panel alone rather than set the state behind the integration's back. A warning is logged.
- An exit delay is fine: when the panel goes to `arming`, and then to the armed state, AutoArm doesn't mistake that for someone changing it by hand.
- Panels have no action for `pending`, so AutoArm keeps that within itself rather than changing the panel, for example when moving on at the end of a calendar event.

### Setting the State Directly

With the option switched off, AutoArm sets the panel's state directly instead. This was the default before
1.3.0, and installs from then keep it until the option is changed. It works with a *manual* panel, including
one that needs a code, but not with integrations like Alarmo, which will overwrite the state or be left out of step.

### Legacy YAML Reference

Before the UI config flow, the alarm panel was specified in YAML. This is still supported for auto-migration, but new installations should use the UI.

```yaml
autoarm:
  alarm_panel:
    entity_id: alarm_panel.home_alarm_control
```
