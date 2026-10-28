# 0.3

Chord inversions, synth note hold, 10-minute idle timeout, dark inactive steps and empty clips, and drum availability lighting. 40 host-mocked checks pass.

# 0.2 — JC Records

Row mute/solo, expandable step pages, clip Performance mode, drum pad blocks, mixer pan/fader views, four knob banks, adjustable arp page, maximum brightness, button LEDs and JC RECORDS sleep animation.

# 0.1.1 — startup repair

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
