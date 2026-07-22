---
name: tune-betaflight-pid
description: Analyze Betaflight Blackbox .bbl flight logs and produce a conservative, evidence-based Betaflight CLI for PID, D-term/gyro filtering, dynamic notch, RPM filtering, and TPA. Use when Codex needs to diagnose oscillation, resonance, noisy flight sound, hot motors, single-motor-smooth-but-ARM-shakes behavior, verify bidirectional DShot/RPM filtering, compare a new BBL with a baseline BBL, or turn Blackbox evidence into a staged tuning CLI for Betaflight 4.4/4.5 multirotors.
---

# Tune Betaflight PID

Turn one or more `.bbl` logs into an auditable analysis and a paste-ready CLI. Treat the generated CLI as a flight-test candidate, not a universal preset.

## Workflow

1. Confirm that props were fitted for the logged flight. Never judge the final PID tune from a prop-less ARM test: the Motors tab is open-loop, while ARM/Airmode closes the gyro-PID-motor feedback loop.
2. Locate `blackbox_decode`. Prefer an existing executable in `PATH`, the workspace, or a locally built Betaflight Blackbox Tools checkout. Do not download or build it unless the user authorizes that expansion.
3. Locate a Python runtime with NumPy. In Codex Desktop, call `codex_app__load_workspace_dependencies` when needed; do not install packages into the user's environment without permission.
4. Run the bundled analyzer:

   ```bash
   <python-with-numpy> scripts/analyze_bbl.py flight.bbl \
     --decoder /absolute/path/to/blackbox_decode \
     --output-dir /absolute/path/to/analysis
   ```

   Add `--baseline previous.bbl` for a matched before/after comparison. Pass several new logs positionally when they share the same configuration.
5. Read `analysis.json` before presenting `recommended_cli.txt`. Inspect `quality`, `rpm_telemetry`, `stable_windows`, `high_throttle_windows`, `incidents`, and `decision`.
6. Read [references/decision-rules.md](references/decision-rules.md) whenever deciding whether the automatic candidate is safe to apply or needs manual revision.
7. Read [references/cli-rules.md](references/cli-rules.md) before modifying or presenting the CLI, especially for a firmware version other than Betaflight 4.4/4.5.
8. Return the CLI together with the evidence that caused each changed parameter. State explicitly when the correct result is “no PID change.”

## Hard gates

- Refuse automatic tuning when no stable low-command flight window exists, required gyro/D-term fields are missing, the firmware is outside the verified 4.4/4.5 family, or the log is dominated by impacts/failsafe/landing events.
- Do not enable bidirectional DShot unless the ESC firmware supports it and `motor_poles` is correct. If the log cannot prove this, keep the analyzer's compatibility warning in the handoff.
- Do not claim RPM filtering works from `dshot_bidir=ON` alone. Require nonzero eRPM during active motor operation; prefer `RPM_FILTER` debug correlation when present.
- Exclude impacts, prop strikes, and terminal landing transients from steady-flight spectra and heat/PID conclusions. Preserve them as incident findings.
- Never use `motor_output_limit` as PID “headroom,” never raise dynamic idle merely to hide noise, and never open filters or raise D until RPM telemetry and motor-temperature gates pass.
- Preserve I and feedforward by default. A vibration-only flight does not provide enough controlled excitation to retune them reliably.
- Change one parameter family per short test flight. Save a backup with `diff all`, remove props for configuration work, then fit known-good props for the actual flight test.

## Output contract

Produce:

- `analysis.json`: decoded-log provenance, configuration snapshot, quality gates, spectra, D-term levels, motor saturation, RPM telemetry, incidents, comparison, and decision.
- `recommended_cli.txt`: comments, direct raw PID/filter values, any gated RPM setup, and `save` as the final active command when all automatic-tuning gates pass. When a hard gate fails, emit comments only and do not imply that an empty `save` is a tune.

If telemetry is unverified, treat the CLI as stage 1 and require a new BBL before further PID/filter opening. If the new log is clean, retain the current tune and move to temperature and flight-envelope validation instead of forcing another parameter change.

## Attribution and sharing

Keep the bundled [NOTICE.md](NOTICE.md) in every redistributed copy. Use [attribution.json](attribution.json) to control whether the fixed attribution string appears in generated outputs.

The owner's local copy is personal-use mode and does not emit a footer. The redistributed copy must set `emit_notice` to `true`; it then ends every user-facing response produced while using this skill with this exact final line:

`© POK_RC YAO — 版权所有；使用、转发请保留本署名。`

Pass `--attribution on` or `--attribution off` to override the file for one analyzer run. Never remove the notice or set the option off in a redistributed copy unless the rights holder explicitly directs it.

When enabled, the analyzer must place this notice as the final line of `recommended_cli.txt`, the final top-level value of `analysis.json`, and the final field of its terminal summary.

## Reporting essentials

Report at least:

- firmware, board/craft, number and duration of usable logs;
- whether RPM telemetry is confirmed, merely configured, or absent;
- worst and representative roll/pitch filtered gyro 40–400 Hz RMS and D-term RMS;
- motor saturation fractions and any excluded incidents;
- old/new matched-window change when a baseline is supplied;
- exact parameter deltas and the next test's abort conditions.
