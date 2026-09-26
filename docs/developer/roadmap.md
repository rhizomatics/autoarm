---
tags:
  - developer
---
# Roadmap

## Occupancy

### Absence-Only Devices

Some devices say something about whether a person is away, but not whether they're home. The usual
example is a tablet that is often left behind:

- **Tablet away**: a good sign its owner is away too.
- **Tablet home**: says nothing, since it's often left at home.

These devices can't be attached to the `person` entity as device trackers, since the person would then
show as home whenever the tablet is. So Auto Arm needs its own link from each device to its owner.

Mobile app devices get attached to a person automatically. When the Companion App registers, `mobile_app`
creates a `device_tracker` and adds it to the person linked to the registering user. So the owner would
already have removed a left-behind tablet's tracker from their person by hand.

#### Linking a Device to its Owner

The config flow UI has no standard way to pair two entities, so these are the choices:

| Option | How the owner is found | UI | Covers |
|---|---|---|---|
| A. Mobile app registration | `user_id` saved with the device's registration, matched to `person.user_id` | One device picker, no pairing | Only Companion App devices |
| B. Config subentries | Picked in an "Occupant" subentry: a person, plus their absence-only trackers | One subentry per person, each listed under the Auto Arm entry | Any device tracker |
| C. Object selector | Rows of *person* and *trackers* on the options page | One list in the Occupancy Tuning section | Any device tracker |
| D. Multi-step options | Pick a person, then that person's trackers, repeat | Menu steps | Any device tracker |
| E. YAML | `occupancy:` mapping of person to trackers | None | Any device tracker |

**A. Mobile App Registration**

- To go from a device tracker to its owner:
    1. Find the tracker's `mobile_app` config entry, using the entity or device registry.
    2. Read the `user_id` from that entry's data. It records the Home Assistant user who registered the app.
    3. Find the `person` whose `user_id` attribute matches.
- The Occupancy Tuning section only needs a `DeviceSelector` or `EntitySelector` filtered to the
  `mobile_app` integration, with the owner worked out as above. No pairing is needed in the UI.
- Limits:
    - The device must run the Companion App with location tracking. Router, Bluetooth or other trackers have no user link.
    - The owner is whoever registered the app. That's wrong for a child's tablet set up on a parent's
      account, or a shared family tablet.
    - The person must be linked to a Home Assistant user.

**B. Config Subentries**

- The Home Assistant pattern for things under an entry that users add, edit and remove, each with
  its own form. Each subentry would be a person, plus any absence-only trackers.
- The people chosen now in the options would move into these subentries, with a migration.
- Most work to build, but the clearest to use, and it leaves room for more per-person settings later,
  such as the occupancy delay times now only in YAML.

**C. Object Selector**

- An `ObjectSelector` with `fields` for a person and trackers, and `multiple`, gives a list of rows in
  one form.
- Less work than subentries, but needs checking in the options flow: how it looks, and how entity
  pickers work inside it on the minimum supported Home Assistant version.

**D. Multi-Step Options**

- Works on any version, but gives no overview of the pairings, and it's clumsy to edit.
  Not recommended.

**E. YAML**

- Matches how buttons, transitions and delay times are set up now. Simplest to build, but goes against
  the move to the UI.

A and E can be combined. A covers the common case with no pairing, and E handles trackers outside the
Companion App, or a device registered on the wrong account.

#### Behaviour to Decide

- **The rule.** A person counts as away when any of their absence-only devices is away, even if the
  person entity shows home. A device at home changes nothing.
- **Stale devices.** If a tablet's battery runs flat while it's away, it keeps its last location, and
  its owner would stay away for good. Options:
    - Ignore a device not updated within a set time.
    - Only react to a device *leaving*, not to it being away.
- **Owners with no person entity.** For example, a tablet whose owner isn't one of the chosen people.
  Ignore it with a warning, or reject it in the config flow.
- **Other features.**
    - `at_home`, `not_home`, `is_occupied` and `is_unoccupied` would all apply the rule, so
      transitions and the calendar occupancy override get it for free.
    - The trackers need listening to, alongside the person entities in `initialize_occupancy`.
    - Occupancy delay times: whether they apply to device changes, as they do to person changes.
    - The Assist "why" answer should say when a device made someone count as away.
- **Diagnostics.** Include the resolved device to owner links, so a wrong mobile app owner is easy to spot.

#### Recommendation

Start with A, adding a picker of Companion App devices to a collapsed **Occupancy Tuning** section. Add E as the way out for other trackers or wrong owners. Move to B if the pairing needs a UI, or more per-person settings turn up.

## Alarm Panel Codes

Auto Arm never passes a code when it changes the panel's state, so panels that need a code to arm or disarm, shown by the `code_format` and `code_arm_required` attributes, can't be driven by it. Support
would mean:

- Somewhere to keep the code, such as a password field in the options, or a secret in YAML.
- Passing `code` in the `alarm_control_panel` action calls when the panel needs one.
- Letting Assist disarm only when a code is said, such as "disarm the alarm 1234", checked against the
  panel, rather than disarming for anyone who can talk to Assist.
