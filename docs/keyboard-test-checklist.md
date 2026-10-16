# Keyboard Prototype Test Checklist

This checklist records the manual per-platform verification of physical key positions and learned labels described in Technical Design 8.1 and 11.3. Run the probe with `uv run python -m vuechoixgarde.ui.keyboard_probe`; it stores learned labels in memory only.

## Test setup and procedure

For every platform/session below:

1. Start the probe and keep focus in its window. Confirm the four default slot captions initially read `W`, `A`, `S`, `D`.
2. Use a QWERTY keyboard. Press each physical default position once without modifiers. Confirm `position` reports `KeyW`, `KeyA`, `KeyS`, `KeyD` respectively and that the slot captions show the characters produced by that layout.
3. Repeat with QWERTZ and AZERTY layouts. On AZERTY, the default labels should become `Z`, `Q`, `S`, `D` after pressing the four positions once.
4. On an ISO keyboard, press the key next to left Shift (the `IntlBackslash` position) and the Backquote position. Record the reported Qt values and positions. On macOS, explicitly note whether Qt reports the known ISO Backquote/IntlBackslash swap; the prototype does not normalize it.
5. Press a character-producing key with Shift, Control, Alt, and (where available) AltGr. Each event should report `modifier active=True`; it must not update a learned label or be treated as a slot activation. KeypadModifier by itself is not a blocking modifier.
6. Hold a default slot key long enough to produce auto-repeat. Repeated events should report `auto-repeat=True` and must not trigger repeated slot actions. This probe has no file actions; verify the field and resulting label instead.
7. Press a dead-key accent, then a key that completes the composition. Record whether the dead-key event has empty/non-printable text and verify that it does not replace the prior label. The composed character on the following event may be learned if it is a single printable character.
8. Repeat the key-position check under both Linux X11 and Linux Wayland sessions where available. Record the session type; native codes delivered by Qt are the values under test.

A valid position should be independent of the active layout. A blank or unexpected position, modifier misclassification, or label change on a dead key should be recorded as a failure rather than corrected by editing the mapping during the test.

## Results

| Platform / session | Layout | Default positions correct (W/A/S/D) | Learned labels correct | ISO IntlBackslash / Backquote | Modifiers / AltGr blocked | Dead key retained prior label | Auto-repeat identified | Pass / notes |
|---|---|---|---|---|---|---|---|---|
| Linux X11 | QWERTY | | | | | | | |
| Linux X11 | QWERTZ | | | | | | | |
| Linux X11 | AZERTY | | | | | | | |
| Linux Wayland | QWERTY | | | | | | | |
| Linux Wayland | QWERTZ | | | | | | | |
| Linux Wayland | AZERTY | | | | | | | |
| Windows | QWERTY | | | | | | | |
| Windows | QWERTZ | | | | | | | |
| Windows | AZERTY | | | | | | | |
| macOS | QWERTY | | | | | | | |
| macOS | QWERTZ | | | | | | | |
| macOS | AZERTY | | | | | | | |
