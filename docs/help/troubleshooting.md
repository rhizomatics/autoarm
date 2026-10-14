# Troubleshooting

## Repair Issues

Auto Arm uses the Home Assistant repair system to report configuration problems:

- **Invalid Transition Condition**: A transition condition template failed validation. Check the condition syntax in your YAML.
- **YAML core configuration is deprecated**: Core settings have been migrated to the UI config entry. Remove the migrated keys from YAML (see the [Migration Guide](../configuration/migration.md)).
- **YAML notify configuration is deprecated**: The `notify` section has been replaced by deeper Supernotify integration in the options, and will be removed when Home Assistant 2027.4 is released. Move what is still needed to the **Notifications** section of the options, or to Supernotify scenarios, and remove it from YAML.

## Reload After YAML Changes

After modifying YAML configuration (transitions, buttons, notify, etc.), call the `autoarm.reload` service or restart Home Assistant for changes to take effect.

## Debug Logging

Enable debug logging for Auto Arm to see detailed operation logs:

```yaml
logger:
  logs:
    custom_components.autoarm: debug
```

All Auto Arm log messages use the `AUTOARM` prefix for easy filtering.

## Options

- [AI Agents](./ai_help.md) can give very good help these days, even the free one built into [Google Search](./ai_help.md#google-and-ai-assisted-help).
- [Troubleshooting your configuration](https://www.home-assistant.io/docs/configuration/troubleshooting/) has the generic Home Assistant advice
- Auto Arm has a [Diagnostics](https://www.home-assistant.io/integrations/diagnostics/) bundle available from the integration page
- Have a look at the [What's New](https://autoarm.rhizomatics.org.uk/changelog/), including any breaking changes, and any of the known [Issues](https://github.com/rhizomatics/autoarm/issues) or [Support Discussions](https://github.com/rhizomatics/autoarm/discussions).
- Use the [Tools](https://www.home-assistant.io/docs/tools/dev-tools/) to call the action directly, listen to events, or view states
  - Since Auto Arm manages Home Assistant contexts, you can see the entire history of a why an alarm state changed, what the original trigger was, and also downstream things notifications, all laid out in the state history
  - Supernotify also has some of additional actions to `enquire_configuration`,`reload` configuration and `reset_state`, and offers lots of diagnostic entities


## Advanced Agent Usage
- If you have a desktop or coding agent, then giving it access to Home Assistant config make it much easier to resolve issues and correct config.
  - Easiest way of doing that is with the [Samba Share](https://github.com/home-assistant/addons/tree/master/samba) app for Home Assistant.
  - For example, on a Mac you can have the local `/Volumes/config` reading the main `\config` directory of Home Assistant.
  - Caution is due where passwords and other secrets inside the Home Assistant directory could be exposed.
- The *Assist* integration also supports [MCP](https://www.home-assistant.io/integrations/mcp/) for queries
- For more advanced usage, the [Home Assistant REPL](../developer/ha_repl.md) developer shell can give easy agent access to the APIs, or deep access direct into the live internals and database with `live` mode. The latter is the sharpest tool available for agents.
