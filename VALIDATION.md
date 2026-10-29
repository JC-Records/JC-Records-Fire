# JC Records Fire 0.4.0 validation

59 host-mocked tests pass using `python tests/test_fire.py`. Coverage includes touch-event isolation, held-step edits and repeat, velocity read-back and percentages, LED refresh, OLED keep-alive, exact synth page resolution, FLEX macro refresh, missing mappings, and Select shortcuts.

Version 0.4.0 initialized in FL Studio 2026.1.7, MIDI scripting API 45, with output assigned. Harmor A/B and FLEX pages were resolved against live exposed parameter lists on 29 October 2026. The installed Harmor scan selected the expected Filter and Amp envelope parameters without a reported script error.

The user confirmed step lights working after the preceding refresh fix. New physical knob behaviour, repeat playback, OLED duration, preset-specific audible results and automation recording still require hardware/audio confirmation. Mock tests and successful initialization do not establish complete physical controller compatibility. Other synths retain automatic profiles; their mappings have not been individually verified.

The project is published without a Beta label at the owner's request. This does not broaden the validation described above.
