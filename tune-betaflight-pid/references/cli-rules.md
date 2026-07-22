# Betaflight CLI Rules

## Version scope

The bundled generator emits direct settings verified for Betaflight 4.4/4.5. For another firmware family, inspect that version's `src/main/cli/settings.c` or official CLI dump before presenting the commands. Never assume renamed or removed settings remain valid.

## Direct values and simplified tuning

- Generate raw `p_*`, `i_*`, `d_*`, `d_min_*`, and explicit filter values.
- Turn simplified PID/filter modes off in the generated candidate so a later `simplified_tuning apply` does not silently overwrite the evidence-based values.
- Do not mix simplified sliders and raw overrides in one CLI unless their derived results have been calculated and verified.
- Keep feedforward and I unchanged unless the flight contains suitable controlled excitation and the analysis explicitly supports changing them.

## Parameter safeguards

- `dshot_bidir`: set only after confirming ESC firmware compatibility.
- `motor_poles`: use the actual rotor magnet count, not stator slot count.
- `motor_pwm_protocol`: preserve an existing digital protocol; do not blindly convert analog ESCs to DShot.
- `rpm_filter_harmonics`: use 3 as a conservative diagnostic default when bidirectional DShot is confirmed; do not claim it is active without eRPM evidence.
- `dyn_notch_count`: retain enough dynamic notches when RPM filtering is absent; do not remove dynamic notch protection on an unknown airframe.
- `dterm_lpf*` and `gyro_lpf*`: lower cutoff means more filtering and more delay. Strengthen filtering before reducing it on noisy data.
- `tpa_rate`/`tpa_breakpoint`: change only when high-throttle, low-command windows show materially worse D/noise than matched lower-throttle windows.
- `motor_output_limit`: leave unchanged unless the user explicitly requests a real power/speed cap.
- `dyn_idle_min_rpm`: leave unchanged unless solving verified low-RPM desync or authority loss.
- `thrust_linear`: leave unchanged unless tuning motor linearization as a separate controlled task.

## Handoff format

Keep comments in the CLI so the user sees gates and reasons. End with exactly one active `save`. Recommend taking `diff all` before applying. Never claim a candidate is flight-safe without a short test and new log.
