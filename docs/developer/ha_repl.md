---
tags:
  - developer
  - debugging
  - ha-repl
  - repl
description: Using the ha-repl developer shell to inspect a running Auto Arm
---
# Developer Shell

[Home Assistant REPL](https://homeassistant-repl.rhizomatics.org.uk) (`ha-repl`) runs Python against a running Home Assistant, either at an interactive prompt or one snippet at a time.

It is for checking how Auto Arm really behaves on a running instance, where the alternative is reading the source and guessing, or adding log lines and restarting.

!!! warning
    In live and exec modes, whatever is typed runs inside Home Assistant, with everything that the `hass` object can reach. Use a development instance or devcontainer unless you are sure of what a statement does.


## Set Up

1. `homeassistant_repl` is one of the development dependencies, so after `uv sync` it runs as `uv run ha-repl`. It needs Python 3.14.
2. Set `HASS_SERVER` and `HASS_TOKEN`, in the environment or a `.env` file in the repository root, or name a server in `~/.config/ha-repl/config.toml`. `ha-repl servers` lists what is configured.
3. For live and exec modes, install the `ha_repl_server` custom component on the Home Assistant instance, at the same version as the `ha-repl` client. API mode works without it.


## Using It

### Installation

```bash
uv tool install homeassistant-repl
```
!!! tip
    Installation isn't essential - if you don't want to that then use
    ```uvx --from homeassistant-repl ha-repl``` instead every time you want to run it.

### Interactive

```bash
ha-repl live
```

```python
>>> ce=hass.config_entries.async_entries("autoarm")[0]
>>> show(ce)
>>> list(obj.find_paths(platform='autoarm')) # also works on API mode
```

`help(thing)` prints a short summary of an object's methods and properties, which is a quick way round an unfamiliar class.

### One Snippet

`exec` runs a snippet and exits, which suits scripts, and is what an AI coding agent uses:

```bash
ha-repl --json exec -t 30 - <<'PY'
{name: (d.last_outcome, d.last_skip_reason) for name, d in deliveries.items()}
PY
```

Objects stay inside Home Assistant and only plain data comes back - strings, numbers, lists and dicts - so shape the last expression that way. Anything else is returned as its `repr()`.

### With Claude Code

The `ha-repl` project publishes a Claude Code plugin in the [Rhizomatics plugin marketplace](https://github.com/rhizomatics/agent-plugins), with a skill that teaches the agent to use `exec` mode:

```bash
claude plugin marketplace add rhizomatics/agent-plugins
claude plugin install homeassistant-repl@rhizomatics
```

Installing it for other agents is covered under [Agent Skill](https://homeassistant-repl.rhizomatics.org.uk/modes/exec_mode/#agent-skill) in the `ha-repl` documentation.
