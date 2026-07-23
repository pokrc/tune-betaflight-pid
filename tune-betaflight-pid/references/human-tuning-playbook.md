# Human PID Tuning Principles for the Adaptive Policy

This reference encodes repeatable human-tuning practice. It does not replace inspecting the aircraft, measuring motor temperature, or testing in a controlled environment.

## Control-loop roles

| Term | Primary job | Evidence before changing it | Automatic policy |
| --- | --- | --- | --- |
| P | Correct present attitude error | Persistent low-command closed-loop oscillation after mechanical/RPM checks | Only reduce, and less than D |
| I | Correct sustained bias | Controlled hold/translation evidence and a clear I-term symptom | Preserve by default |
| D | Damp rapid change | Elevated low-command D RMS, motor heat, propwash, or closed-loop noise | Reduce before P; never raise automatically |
| Feedforward | Follow commanded stick changes | Repeatable stick-response data without vibration confounds | Preserve by default |
| Filters | Reject sensor/motor noise | RPM status, raw vs filtered gyro, D-term energy, and latency trade-off | Strengthen only for severe noise; never open automatically |
| TPA | Reduce authority at high throttle | Matched low-command high-throttle D energy materially above lower-throttle energy | Change only when the high/low D ratio is at least 2x |

## Evidence-to-action patterns

1. **Clean, RPM-confirmed low-command windows**: retain the tune. A no-change result is success, not a failure to tune.
2. **Moderate low-command filtered gyro and D energy**: reduce D by a bounded amount and P by a smaller bounded amount. Keep I and feedforward fixed.
3. **Severe low-command noise with RPM confirmed**: reduce D first, reduce P conservatively, and strengthen filtering only if necessary. Require a new Blackbox log before another family changes.
4. **High-throttle-only D increase**: retain low-throttle PID and use a limited TPA stage if the measured high/low D ratio is at least 2x.
5. **RPM unverified or absent**: do not change PID or filters. First establish compatible bidirectional DShot, correct motor poles, active eRPM, and a prop-on validation log.
6. **Impact, prop strike, landing transient, or failsafe**: exclude the event from steady metrics and report a mechanical inspection requirement. Do not treat it as a PID signal.
7. **Motor heat without matching D/noise evidence**: inspect propellers, motor bell/shaft/bearings, fasteners, wiring, ESC settings, battery condition, and cooling. Current alone does not identify PID heat.

## Automation invariants

- Never raise P, D, filter cutoffs, dynamic idle, motor-output limit, or thrust linearization automatically.
- Never set bidirectional DShot unless the operator explicitly confirms ESC support and the log supplies an actual motor-pole value.
- Never combine RPM setup with a PID/filter adjustment in one generated stage.
- Never use a previous log as a baseline unless throttle and command envelopes are comparable.
- Never emit active tuning commands when firmware/version, required fields, or stable-window gates fail.
- Always end an active stage with a short prop-on test and a new BBL; preserve `diff all` before changes.

## Adaptive decision modes

| Mode | Meaning | Active CLI allowed? | Required next evidence |
| --- | --- | --- | --- |
| `hold` | A hard gate failed | No | Prop-on log with required fields and a supported firmware/configuration |
| `rpm_validation` | PID evidence exists but RPM is absent/unverified | No | ESC compatibility confirmation and eRPM/RPM_FILTER Blackbox evidence |
| `rpm_setup` | Operator confirmed compatible ESC support | Yes, telemetry setup only | Reboot, telemetry check, then a prop-on BBL |
| `retain` | Current tune is clean in accepted windows | No | Temperature/flight-envelope validation only |
| `tpa_only` | High-throttle D energy is disproportionate while low throttle is clean | Yes, TPA only | Matched high-throttle BBL |
| `noise_reduction` | RPM-confirmed low-command vibration exceeds the clean band | Yes, one bounded PID/filter stage | New matched BBL before any further change |
