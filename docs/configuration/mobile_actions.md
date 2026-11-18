# Mobile Actions

Auto Arm listens out for the result of [Actionable Notifications](https://companion.home-assistant.io/docs/notifications/actionable-notifications/) with the following `action` values:

## Supported Actions

| Action Key         |
| ------------------ |
| ALARM_PANEL_DISARM |
| ALARM_PANEL_RESET  |
| ALARM_PANEL_AWAY   |

## Who Can Use Mobile Actions

By default any Home Assistant user can use these actions. To limit them, choose the users in
**Mobile action users**, in the **Notifications** section of the options. An action from anyone else is ignored,
with a warning in the log.

!!! danger "Disarming by mobile action"
    No code is asked for when a mobile action disarms the alarm, even if Auto Arm has the alarm panel code to use
    itself. Actions don't have to come from a notification Auto Arm sent: anyone who can log in to Home Assistant,
    and so register a mobile app, can send one. Choose **Mobile action users** to keep this to the people who
    should be able to disarm the alarm.

## Add Action to a Mobile Push Notification

Here's how to send a notification to a mobile app, with a Disarm action:

```yaml
action: notify.mobile_app_<your_device_id_here>
data:
  message: "The noisy PIR has detected the kids again"
  data:
    actions:
      - action: "ALARM_PANEL_DISARM" # The key you are sending for the event
        title: "Disarm Alarm" # The button title
        icon: sfsymbols:bell.slash
```

## Adding Actions to Auto Arm's Own Notifications

Auto Arm's own state-change notifications, sent from the **Notifications** section of the Options UI, can carry the
same kind of actions. Set **Extra Notification Data** to include an `actions` list, and every notification Auto Arm
sends gets those buttons:

```yaml
actions:
  - action: "ALARM_PANEL_DISARM"
    title: "Disarm Alarm"
    icon: sfsymbols:bell.slash
```

This is a plain data block, not a template or script - it's merged into every notification's `data` as-is.

With Supernotify as the notification action, all three actions are added without any of this, with titles in the
Home Assistant language.

Whichever way they are added, an action that would do nothing is left out of the notification, so `ALARM_PANEL_DISARM`
isn't offered when the alarm has just been disarmed, nor `ALARM_PANEL_AWAY` when it has just been armed away.
