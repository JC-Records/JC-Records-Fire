# 0.3

Chord inversions, synth note hold, 10-minute idle timeout, dark inactive steps and empty clips, and drum availability lighting. 40 host-mocked checks pass.

# 0.2 â€” JC Records

Row mute/solo, expandable step pages, clip Performance mode, drum pad blocks, mixer pan/fader views, four knob banks, adjustable arp page, maximum brightness, button LEDs and JC RECORDS sleep animation.

# 0.1.1 â€” startup repair

- Fix NameError at startup caused by assuming FL defines __file__ for the controller entry point.
- Add a regression test using FL-style string execution without __file__.
- Print version, MIDI scripting API and output assignment after initialization.
- Confirm actual loading in FL Studio 2026.1.7/API 45.

## 0.3.1

- Correct knob-bank LED bit-control encoding.
- User 2 skips empty effects and provides two pages of built-in EQ/mixer controls when no effects expose parameters.
- Four regression tests added (44 passing).

## 0.3.2

- Ignore all four encoder touch/release events.
- Remove SHIFT-pad instant accent; use held-step knob edits.
- Add SHIFT held-step Mod Y, timing shift and native note repeat.
- Immediate OLED parameter/value feedback with read-back percentages.
- 48 host-mocked tests pass.

## 0.3.3 velocity stability

Held-step edits survive playback loops and transport transitions. Explicit Stop still clears held notes and edits. Active steps are not re-enabled on each encoder turn. Step parameters use the graph-editor read path with defaults for unassigned values; Mod X/Y use their full 0-255 range. Velocity percentage remains visible while a step is held. 51 host-mocked tests pass; physical confirmation remains pending.

## 0.3.4 step-light refresh

Controller events and FL refresh callbacks now render the lights directly. Full refresh invalidates the LED cache, and meter updates provide an additional periodic callback. Inactive steps remain dark; active/pressed steps keep their row colours. 53 host-mocked tests pass; loaded successfully in FL API 45. Physical pad confirmation remains pending.

## 0.4.0

Exact Harmor A/B sound-design pages and FLEX standard controls/preset macros. NOTE selects USER1. Held steps expose velocity/repeat/Mod X/Mod Y, SHIFT accent/pitch/timing/repeat. Select edits repeat or fine velocity on held steps, ALT pages parameters, and Mixer Select follows track banks. See CONTROLS-0.4.md. Includes 0.3.5 screen keep-alive and 30-second feedback.
