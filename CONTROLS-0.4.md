# JC Records Fire 0.4.0 — synth and step controls

Press NOTE to play and automatically use USER1 synth knobs. Turn Select to choose the Channel Rack instrument. Press Select to open its editor. KNOB MODE still switches Channel / Mixer / USER1 synth / USER2 effects.

## Harmor

Each row below is a page of four knobs, left to right. Pages 1–5 control part A; pages 6–10 repeat the same layout for part B. Envelope controls are Harmor's exposed time scales and sustain offset; their audible result depends on the preset envelope.

| Page | Knob 1 | Knob 2 | Knob 3 | Knob 4 |
|---|---|---|---|---|
| Filter | Filter 1 frequency | Resonance/noise amount | Envelope amount | Filter width |
| Amp envelope | Attack scale | Decay scale | Sustain offset | Release scale |
| Time | Pluck decay | Blur attack | Blur decay | Blur mix |
| Phaser | Mix | Width | Offset | Motion speed |
| Filter envelope | Attack scale | Decay scale | Sustain offset | Release scale |

Use grid left/right in NOTE, or ALT + turn Select, to change pages. Remaining exposed parameters follow under MORE pages. Missing or ambiguous exact-name mappings stay unassigned, rather than controlling another parameter. SHIFT+Select rescans. In NOTE, SHIFT knobs remain arp controls; use USER1 in STEP without holding a pad for fine synth edits with SHIFT.

## FLEX

Pages: Filter; Amp envelope; Filter envelope; Delay; Reverb; Macros 1–4; Macros 5–8; More. The macro names follow the loaded preset. Standard filter and envelope pages stay separate from those macros.

Other synths retain existing automatic discovery/profile ordering; they do not yet have Harmor's verified named pages.

## Step sequencer

Hold one or more steps, then turn:

| Controls | Knob 1 | Knob 2 | Knob 3 | Knob 4 |
|---|---|---|---|---|
| Normal | Velocity | Native note repeat | Mod X | Mod Y |
| SHIFT | Accent / velocity (8-unit changes) | Pitch | Timing shift | Native note repeat |

Repeat cycles through Off and FL's straight, dotted and triplet repeat rates. Changes are stored in FL's step parameters, not a parallel playback engine. Mod X/Y depend on the receiving instrument. No pan is assigned in this step-edit layout. Knob touch alone still does nothing. Hold + turn marks the step edited, so release leaves it enabled.

Select while holding a step edits repeat; SHIFT + Select rotation edits velocity finely. Neither drops held steps. Otherwise: Select chooses channels; SHIFT + Select rotation chooses patterns; ALT + Select rotation chooses parameter pages. In Mixer, Select chooses tracks and follows their four-track bank. Existing Select press opens the instrument; ALT+Select press retains mixer pan/volume view and melody playback functions.

## Validation

59 host-mocked tests pass. Exact Harmor A/B and FLEX pages were resolved against the live FL Studio 2026 parameter lists on 29 October 2026. This verifies destinations, not every preset's audible response. Physical controller verification is pending.
