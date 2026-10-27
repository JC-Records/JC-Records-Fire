# JC Records Fire 0.2 Beta

A colourful Akai Fire controller script for FL Studio 2026.1.7 (MIDI scripting API 45). Includes expandable Channel Rack sequencing, chords and arpeggiation, FPC-style drums, clip launching, mixer faders and paged synth/FX controls. Beta: see VALIDATION.md for what has been tested.

## Install

1. Download this repository using **Code → Download ZIP**, then extract it.
2. Create a folder named **JC Records Fire** inside your FL Studio User data folder under **Settings/Hardware**.
3. Copy `device_DJ_RUSTY_Fire.py`, `rusty_core.py`, `jc_controls.py` and `settings.json` into that folder. Keep the Python filenames unchanged.
4. In FL's MIDI settings, enable the **FL STUDIO FIRE** input and select **JC Records Fire 0.2 Beta**. Refresh the script list or restart FL if it is missing.
5. Give the Fire input and output the same unused port number. Output is required for pad lights and OLED.
6. Start with a test project. Select only one controller script for this Fire input.

For upgrades from DJ RUSTY Fire, replace the four files in that existing Hardware folder instead of creating a second installation. Back up its Sessions and Exports folders first. FL may retain the older controller-list label until its list is refreshed.

No watcher executable, MIDI bridge or external Python package is required. The previous loader fix initialized successfully in FL Studio 2026.1.7 (MIDI API 45); the 0.2 expansion needs physical verification. Full controller feature testing remains incomplete.

## Main controls

Select means pressing the large encoder. Mute buttons are numbered top to bottom.

| Control | Action |
|---|---|
| STEP | Four Channel Rack rows by sixteen steps |
| SHIFT + STEP | Polyphonic melodic grid |
| NOTE | Scale keyboard and chords |
| DRUM | Drum notes; FPC uses exposed kit assignments |
| PERFORM | Playlist clip performance grid |
| KNOB MODE | Cycle Channel / Mixer / User 1 synth / User 2 FX |
| Left/right arrows | STEP: step pages and auto-extend; other modes: parameter pages |
| SHIFT + arrows with User 2 (ALT too in STEP) | Select FX slot 1-10 |
| ALT + arrows in STEP/MELODY | Plugin parameter page |
| Select encoder turn | Select Channel Rack instrument |
| SHIFT + Select turn | Select pattern |
| Select press | Show selected instrument |
| SHIFT + Select press | Rescan parameter names |
| SHIFT + ALT + Select press | Save parameter report in Diagnostics |
| Play / Stop / Record | FL transport; Stop releases script-owned notes |
| Pattern/Song | Toggle FL pattern/song playback |
| Browser | Show Browser; in MELODY show Piano Roll |
| SHIFT + Browser | Save internal-sequence session |
| ALT + Browser | Export current internal melody to MIDI |
| SHIFT + ALT + Browser | Load latest internal session, playback OFF |

Mode/channel/pattern/transport changes release script-owned notes. Stop is the panic control for this script.

## Drum step sequencer

STEP displays four consecutive Channel Rack channels, sixteen steps per row. Tap a pad to toggle the native FL step on release. Up/down changes Channel Rack banks. Round buttons mute rows; SHIFT + round solos; ALT + round selects. Grid left/right selects pages, automatically extending the pattern up to 256 steps. SHIFT + grid arrows changes length by sixteen steps. Length changes affect the whole FL pattern; shortening can hide later steps.

Hold a step and turn knobs for velocity, pan, pitch and Mod X. Knob edits prevent that pad toggling off on release. SHIFT + pad writes an accented step. Track-select buttons select rows; SHIFT + track-select toggles channel mute.

These edits write FL Channel Rack steps and are saved with the FLP. Tap toggles an existing step off; hold and turn a knob to edit it instead.

## Melodic / chord sequencer

SHIFT + STEP opens a separate polyphonic grid. Columns are time and rows are scale degrees, higher at the top. Up/down changes pitch range. Grid arrows select sixteen-step pages. SHIFT + grid arrows changes the loop from 16 to 64 steps; longer hidden notes are retained in the internal bank.

Set root, scale and chord type in NOTE mode first. Tap a cell to add/remove its note or chord. SHIFT + cell copies its whole step; ALT + cell pastes. Hold a cell and turn knobs for velocity, gate, probability and ratchets. Steps can contain multiple notes; probability applies to a whole step and ratchets retrigger it 1-4 times.

ALT + Select toggles internal playback. Enabling it extends the current pattern to at least the internal loop length, so a short pattern can reach all four pages. It never shortens a longer pattern. Start FL playback to audition through the selected channel. Only the selected channel/pattern's internal sequence plays. It is not a multichannel arranger and does not follow individual Playlist clip boundaries in Song mode.

ALT + Browser exports a standard MIDI file into Exports inside the installed script folder. Import it into the intended Piano Roll using FL's MIDI import command. Turn internal playback OFF before playing the imported copy, to avoid doubled notes. Export includes chords, velocity, gate, ratchets and one reproducible probability pass; it does not capture a live arp performance.

This grid does not read or modify existing native Piano Roll notes. The controller API does not provide arbitrary Piano Roll note insertion/deletion. MIDI import is a separate FL action, not a fully hands-free round trip.

## Note mode and arpeggiator

Rows overlap: each row is five scale degrees above the row below. Up/down transposes by octave; SHIFT + up/down transposes the root by semitone.

| NOTE control | Action |
|---|---|
| Mute 1 | Single / triad / seventh / octaves |
| Mute 2 | Minor / major / Dorian / pentatonic / chromatic |
| Mute 3 | Arp latch on/off |
| Mute 4 | Up / down / up-down / random |
| SHIFT + NOTE | Arp on/off |
| SHIFT + knob 1 | 1, 2, 3, 4, 6 or 8 notes per beat |
| SHIFT + knob 2 | Arp gate |
| SHIFT + knob 3 | Octave span 1-4 |
| SHIFT + knob 4 | Arp direction |

Scale-derived chords feed the arp. With latch on, release all pads before playing a new chord to replace it. Stop clears latch. Root, scale, chord and mode changes release held notes.

Default note velocity is fixed at 100 and configurable in settings.json. This does not imply velocity-sensitive Fire pads. Script preview notes are not guaranteed to record through FL's Record button. Use melodic MIDI export for reliable editable note files.

Scheduling runs in OnIdle, anchored to host position while playing and tempo while stopped. It is not sample accurate. Heavy UI activity may cause jitter or missed subdivisions; expired notes are skipped instead of bursting. Use exported MIDI for final playback/rendering.

## Plugin and drum FX knobs

The script discovers the loaded plugin's exposed names/values. Name priorities are supplied for FLEX, Sytrus, 3x Osc, Serum, Vital, FPC, Reeverb 2, Delay 3, Parametric EQ 2, Limiter, Blood Overdrive and Fast Dist. These are preferred names, not verified fixed parameter indices. Matches need checking against your installed versions/presets.

Common macros, filters, envelopes and modulation controls are prioritised. Arrows page through every remaining exposed parameter. OLED labels show actual resolved names. Unmatched priorities are skipped; other plugins get generic name ranking. SHIFT gives fine adjustment except in NOTE, where it controls the arp.

Sampler channels without exposed plugin parameters fall back to volume, pan, pitch and mixer routing. In DRUM, FPC pads use the loaded kit's getPadInfo assignments; pads beyond the reported count are ignored. The first two 4x4 blocks match FPC banks, with pad 1 at the lower left. SHIFT + DRUM toggles Channel Rack pads.

For drum FX, route the drum channel to a mixer insert and load the desired effects. KNOB MODE selects User 2; SHIFT + arrows chooses a slot and arrows choose parameter pages. FX follows the selected mixer track in MIXER mode and the selected channel's mixer destination elsewhere. For FPC separate outputs, select their destination in MIXER mode.

The script does not insert effects, build a complete mixer chain, expose hidden parameters, or automatically map every drum pad's private effects. Direct API parameter writes have not been validated for automation recording. Universal synth support is not claimed.

Edit parameter_profiles in settings.json using exact plugin names and preferred parameter-name strings. SHIFT + ALT + Select saves the actual exposed parameter list for tailoring. Rescan after presets that change parameter names.

## Mixer

SHIFT + PERFORM displays four rows, starting with inserts 1-4; master is excluded. Row-coloured pads show volume, amber marks peak activity, red indicates mute. Tap a column to set volume. Leftmost is silence; rightmost is normalized maximum, not necessarily 0 dB.

In Mixer knob mode, knobs adjust these four faders. SHIFT controls pan and ALT gives fine volume adjustment. Up/down changes banks. Track-select selects a row; round buttons mute it, SHIFT solos and ALT arms it. ALT + Select switches pad faders between volume and pan. SHIFT + pad mutes and ALT + pad solos. KNOB MODE switches to selected-track FX controls.

## JC Records sleep show

After 90 seconds without input, while stopped with no held/latched notes, pads cycle plasma, rainbow waves, a comet and scrolling JC RECORDS text. OLED shows JC Records / FIRE AFTER DARK. Input wakes the display and performs its normal action. Playback restores the working display.

settings.json exposes sleep_seconds, brightness (0.05-1) and frame_rate (5-30). This runs while FL and the script are active, not while the computer/USB device is asleep or powered off.

## Saving and recovery

Save the FLP for native steps, mixer and plugin changes. Internal melodies need SHIFT + Browser to save a dated JSON snapshot. Snapshots are also attempted at script shutdown and before project loading; crashes cannot guarantee saving.

Sessions use pattern numbers and global channel indices, not stable plugin IDs. Restore only into the matching project/channel order. Loading a project clears the internal bank and disables playback. Channel deletion/replacement stops notes and resets the internal bank after attempting a snapshot. Channel/pattern reordering can still invalidate saved destinations. Internal melodies are not embedded in the FLP: back up Sessions and Exports alongside your project.

## Verification

See VALIDATION.md. Automated tests use a simulated FL host, not physical hardware. Before live use, verify ports, encoders, FPC assignments, OLED, FX targeting, clock timing, project changes and note cleanup on your Fire. Successful script initialization and output assignment have been observed in FL Studio. Full physical control testing and audio audition remain incomplete.

Official API reference: https://www.image-line.com/fl-studio-learning-content/fl-studio-online-manual/html/midi_scripting.htm

## Row colours

STEP only, top to bottom: cyan, purple, amber and green. Other modes have distinct palettes described below. Inactive pads show dim versions of the row colour; active steps are brighter. White pressed-pad/playhead highlights, red mixer mute indicators and amber peak markers override the row colour. Sleep animations keep their animated palette.

## Extra 0.2 controls

- PERFORM: launch configured Playlist Performance clips. FL Performance mode must already be enabled and clips arranged in its live area. Launches use FL track snapping. Arrows move through 16 clip columns; up/down moves through four tracks. SHIFT + pad launches the visible four-track column; ALT + pad or a round button stops a track. Empty cells remain dim, queued clips pulse, playing clips brighten. Clip release follows the track trigger settings.
- SHIFT + PERFORM: mixer. Four coloured horizontal faders, track selection, mute/solo/arm and volume/pan view.
- Channel knobs: volume, pan, pitch, mixer route; SHIFT gives fine continuous adjustment.
- Mixer knobs: four row volumes in mixer mode (SHIFT for pan, ALT for fine); elsewhere selected-track volume, pan, stereo separation and low EQ gain.
- User 1: priority-mapped instrument controls. User 2: priority-mapped FX controls. Arrows page exposed parameters; in STEP hold ALT to page parameters instead of steps. SHIFT selects FX slots (SHIFT + ALT in STEP).
- ALT + NOTE: latch the arp editing knob page. SHIFT + knobs also edits rate, gate, octaves and direction. SHIFT + NOTE toggles arp playback.
- ALT + NOTE-mode knobs: velocity, root, chord type, brightness (when arp editing page is off).
- Brightness starts at maximum. Rows are cyan, purple, amber and green. All addressable button LEDs are enabled with state highlights; their colours are constrained by the Fire's hardware.

The entry filename retains its old name for compatibility; the displayed controller name and animation are JC Records.

## Mode palettes

STEP keeps cyan, purple, amber and green rows. NOTE uses an ice-blue keyboard with gold roots. MELODY uses a violet-to-pink time gradient with bright active notes. DRUM uses orange, coral, violet and teal 4x4 blocks. PERFORM uses coloured scene groups, gold queued clips and green playing clips. MIXER uses green/amber/red volume bars, white peak markers and blue/pink pan positions. Pressed notes and playheads remain highlighted. Sleep retains its JC RECORDS animation.

Round mute buttons: bright = active, dim = muted, flashing = solo. These single-colour LEDs follow Channel Rack and mixer state, including changes made in FL.

The small rectangular indicators beside the round buttons show bright green for active, bright red for muted, and flashing green for solo in STEP/MELODY/DRUM and MIXER. They follow mute/solo instead of channel selection.

## Development

Run `python tests/test_fire.py` with Python 3.10 or newer. Tests mock the FL host and do not require a connected Fire. The controller itself runs inside FL Studio; launching the entry script with desktop Python will not provide the FL modules.

Licensed GPL-3.0-or-later. See COPYING and THIRD_PARTY.md for the licence and reference-project credits.
