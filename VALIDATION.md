# JC Records Fire 0.3 validation

40 host-mocked tests pass, including entry-point execution without __file__, note cleanup, clip scene releases, mute/solo, step extension, hidden melody preservation, parameter paging, FPC mapping, and rendering each mode. These tests do not emulate FL audio timing or the physical Fire.

Earlier 0.1.1 initialized in FL Studio 2026.1.7 API 45, and the user confirmed STEP/pad/NOTE worked. The new 0.2 features still require physical testing. Performance mode requires a prepared FL Playlist. Plugin mappings depend on exposed parameter names. Internal melody export requires manual Piano Roll import.

On 28 October 2026, selected the updated script for FL STUDIO FIRE input/output port 1. FL Script Output confirmed: JC Records Fire 0.2 initialized | API 45 | output 1. No startup traceback was shown. FL retained the old 0.1.2 controller-list label from its cached list, while executing 0.2. New physical controls and audio remain unverified.

0.3: 40 host-mocked tests pass, including chord inversions, hold release, latch separation, inactive-step darkness and unavailable pad lighting. New hardware behaviour remains to be verified.

The user confirmed general operation and requested subsequent palette and status-indicator refinements. All mode palettes and red/green mute/solo indicator mappings have automated coverage; final physical verification of the latest indicators remains pending.

FL Studio 2026.1.7 Script Output confirmed JC Records Fire 0.3 initialized | API 45 | output 1 after reload on 28 October 2026, with no startup traceback. Physical testing of the new chord and hold controls remains pending.
