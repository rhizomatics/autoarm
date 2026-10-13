# Create an Alarm Panel

If you don't already have an alarm panel, set up a default manual as below, which creates the
state machine for armed/disarmed status. This is all you need in the way of alarm support for Auto Arm to function.

You can also choose whether a PIN code is needed or not to arm or disarm. Auto Arm has its own delay time
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

## Selecting the Alarm Panel in Auto Arm

The alarm panel entity is selected during the Auto Arm UI config flow. Go to **Settings** > **Devices & Services** > **Add Integration**, search for **Auto Arm**, and select your alarm panel entity.

## How Auto Arm Changes the Panel

Auto Arm changes the panel's state by calling its actions, `alarm_control_panel.alarm_arm_away`,
`alarm_control_panel.alarm_disarm` and so on, just as a dashboard card or automation would. This works for
a *manual* panel, and for integrations that do more than hold a state when armed or disarmed, such as
[Alarmo](https://github.com/nielsfaber/alarmo), which arms its child areas when its master panel is armed.

This is controlled by **Change state using the alarm panel's actions** in the **Advanced** section of the Auto Arm options, which is on for new installs.

- If the panel needs a code to arm or disarm, give Auto Arm one, see [Panels That Need a Code](#panels-that-need-a-code).
- If the action fails, or doesn't change the state, Auto Arm leaves the panel alone rather than set the state behind the integration's back. A warning is logged.
- An exit delay is fine: when the panel goes to `arming`, and then to the armed state, Auto Arm doesn't mistake that for someone changing it by hand.

### Panels That Need a Code

Some alarm panels want a code before they will arm or disarm. Auto Arm raises a repair in **Settings** > **Repairs**
when the panel is set up that way and there is no code for it to use. There are three ways to deal with it:

- Set **Alarm panel code** in the **Advanced** section of the Auto Arm options, and Auto Arm passes it to the panel's actions.
- Set a default code for the alarm panel entity in Home Assistant, from the entity's own settings. Home Assistant then
  supplies it to every action called without a code, not only those from Auto Arm.
- Switch the code requirement off in the panel's own integration.

The code set in Auto Arm is handled with some care, though it is not a vault:

- It is typed into a masked field, and is never shown again or sent back to the browser. Leave the field blank to keep
  the stored code, type a new one to replace it, or tick **Remove the stored alarm panel code**.
- It is stored encrypted in the Auto Arm config entry, with a key derived from this Home Assistant's own id. That keeps
  it from being read off a screen or picked out of a file, but anyone with a full copy of the Home Assistant
  configuration directory, or a backup of it, has both and can recover the code.
- It is left out of Auto Arm's logs, events and diagnostics downloads.
- Auto Arm has to hand the code in the clear to the alarm panel's action, as any automation would, so it can be seen
  by anything in Home Assistant that watches action calls, and what the panel's own integration does with it is up to that integration.
- A config entry restored onto a different Home Assistant install can't be decrypted, and the code needs to be set again.

### Setting the State Directly

With the option switched off, Auto Arm sets the panel's state directly instead. This was the default before
1.3.0, and installs from then keep it until the option is changed. It works with a *manual* panel, including
one that needs a code, but not with integrations like Alarmo, which will overwrite the state or be left out of step.
