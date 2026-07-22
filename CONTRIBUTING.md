# Contributing to Tune Betaflight PID

Thank you for helping make Blackbox-based Betaflight tuning safer and more reproducible. The strongest contributions include a real `.bbl` finding, a parser or analysis improvement, a compatibility correction, or a documented tuning decision that another pilot can audit.

## Issue reports

Please include the Betaflight version, board/craft, motor and propeller setup, ESC protocol, RPM-filter status, log duration, and the exact command used. Describe the symptom and the expected result. If you have a baseline log, identify the matched flight windows.

Before uploading evidence, remove receiver identifiers, GPS coordinates, private video links, credentials, and GitHub tokens. A summary of the relevant metrics is usually safer than a complete personal log.

## Analyzer and rule changes

Keep the analysis conservative. New heuristics should:

- preserve the hard gates for missing stable windows, impacts, failsafe, and unsupported firmware;
- distinguish configured RPM filtering from verified RPM telemetry;
- avoid changing I-term or feedforward without controlled evidence;
- explain the parameter delta and the next test's abort conditions;
- include a regression case or a small synthetic fixture when practical.

Run the analyzer's relevant checks before opening a pull request. Do not silently widen filters, raise D, or use motor-output limits to hide a mechanical or control-loop problem.

## Pull requests

Explain what changed, why it is safe, which Betaflight versions it targets, how it was tested, and what remains unverified. Keep user-facing documentation in English and preserve the attribution notice and license terms. Do not add dependencies or network downloads without explaining the impact.

## Flight-test safety

Remove propellers for all configuration work. Use known-good propellers and batteries for flight tests, change one parameter family at a time, and land immediately for abnormal vibration, sound, current, motor temperature, failsafe, or control response. This project is a decision aid, not a flight authorization or a universal preset.

## Related project

The [POKRION High-Speed Micro Quadcopter Platform](https://github.com/pokrc/POKRION-Speed-Drone) provides an example airframe and flight-test context for this workflow.
