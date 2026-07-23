---
name: tune-betaflight-pid
description: Analyze Betaflight Blackbox .bbl flight logs and automatically select a conservative, evidence-gated Betaflight CLI stage for PID, D-term/gyro filtering, RPM validation, and TPA. Use when Codex needs to diagnose oscillation, resonance, noisy flight sound, hot motors, single-motor-smooth-but-ARM-shakes behavior, verify bidirectional DShot/RPM filtering, compare a new BBL with a baseline BBL, or turn Blackbox evidence into an adaptive BBL-to-CLI workflow for Betaflight 4.4/4.5 multirotors.
---

# Tune Betaflight PID

Turn one or more `.bbl` logs into an auditable analysis and an adaptive, paste-ready CLI stage. Treat “full automatic” as automatic evidence classification and stage selection—not permission to bypass hardware compatibility, prop-on validation, or motor-temperature checks.

## Workflow

1. Confirm that props were fitted for the logged flight. Never judge the final PID tune from a prop-less ARM test: the Motors tab is open-loop, while ARM/Airmode closes the gyro-PID-motor feedback loop.
2. Run `scripts/doctor.py` for raw `.bbl` input. It checks NumPy and discovers `blackbox_decode` through an explicit path, `BLACKBOX_DECODE`, `PATH`, conventional local prefixes, or predictable workspace layouts. If it reports `action_required`, state the exact missing prerequisite; do not download or build software unless the user authorizes it.
3. Locate a Python runtime with NumPy. In Codex Desktop, call `codex_app__load_workspace_dependencies` when needed; do not install packages into the user's environment without permission.
4. Run the bundled analyzer. Its default policy is `auto`: it selects `hold`, `rpm_validation`, `rpm_setup`, `retain`, `tpa_only`, or `noise_reduction` from the evidence.

   ```bash
   <python-with-numpy> scripts/analyze_bbl.py flight.bbl \
     --output-dir /absolute/path/to/analysis
   ```

   Add `--decoder /absolute/path/to/blackbox_decode` only when automatic local discovery cannot find it. Add `--baseline previous.bbl` for a matched before/after comparison. Pass several new logs positionally when they share the same configuration. Use `--print-cli` only when direct standard-output CLI is needed. Only pass `--esc-bidir-confirmed` when the operator has independently confirmed compatible ESC firmware and the actual rotor magnet count.
5. Read `analysis.json` before presenting `recommended_cli.txt`. Inspect `quality`, `rpm_telemetry`, `stable_windows`, `high_throttle_windows`, `incidents`, `comparison`, and `decision.mode`.
6. Read [references/decision-rules.md](references/decision-rules.md) whenever deciding whether the automatic candidate is safe to apply or needs manual revision.
7. Read [references/cli-rules.md](references/cli-rules.md) before modifying or presenting the CLI, especially for a firmware version other than Betaflight 4.4/4.5.
8. Read [references/human-tuning-playbook.md](references/human-tuning-playbook.md) before changing the adaptive policy or explaining PID decisions. It encodes bounded human-tuning patterns and automation invariants.
9. Return the CLI together with the evidence that caused each changed parameter. State explicitly when the correct result is `retain`, `rpm_validation`, or “no PID change.”

## Adaptive modes

- `hold`: no active CLI; one or more hard evidence/version fields failed.
- `rpm_validation`: no PID/filter edit; first obtain valid RPM evidence.
- `rpm_setup`: telemetry-only CLI, available only after explicit `--esc-bidir-confirmed`.
- `retain`: clean accepted windows; no active CLI is the intended output.
- `tpa_only`: high-throttle D energy is materially worse than matched low-command energy; edit TPA only.
- `noise_reduction`: RPM-confirmed, accepted low-command noise is moderate/severe; issue one bounded P/D/filter stage and require a new BBL.

## Hard gates

- Refuse active automatic tuning when no stable low-command flight window exists, required gyro/D-term fields are missing, the firmware is outside the verified 4.4/4.5 family, or the log is dominated by impacts/failsafe/landing events.
- Do not enable bidirectional DShot unless the ESC firmware supports it and `motor_poles` is correct. If the log cannot prove this, keep the analyzer's compatibility warning in the handoff.
- Do not claim RPM filtering works from `dshot_bidir=ON` alone. Require nonzero eRPM during active motor operation; prefer `RPM_FILTER` debug correlation when present.
- Exclude impacts, prop strikes, and terminal landing transients from steady-flight spectra and heat/PID conclusions. Preserve them as incident findings.
- Never use `motor_output_limit` as PID “headroom,” never raise dynamic idle merely to hide noise, and never open filters or raise D until RPM telemetry and motor-temperature gates pass.
- Preserve I and feedforward by default. A vibration-only flight does not provide enough controlled excitation to retune them reliably.
- Never raise P, D, filter cutoffs, dynamic idle, motor-output limit, thrust linearization, or feedforward automatically. The adaptive policy only emits bounded reductions or a telemetry/TPA stage when evidence supports it.
- Never combine RPM setup with PID/filter edits in the same generated stage.
- Change one parameter family per short test flight. Save a backup with `diff all`, remove props for configuration work, then fit known-good props for the actual flight test.

## Output contract

Produce:

- `analysis.json`: decoded-log provenance including decoder path/discovery, configuration snapshot, quality gates, spectra, D-term levels, motor saturation, RPM telemetry, incidents, comparison, decision mode, confidence, baseline trend, and parameter deltas.
- `recommended_cli.txt`: comments plus exactly one active stage when justified. `hold`, `rpm_validation`, and `retain` intentionally contain no active tuning command. An active stage ends with `save`.

If telemetry is unverified, emit `rpm_validation` by default. Use `rpm_setup` only after the operator explicitly confirms ESC compatibility. If the new log is clean, emit `retain` and move to temperature and flight-envelope validation instead of forcing another parameter change.

## Attribution and sharing

Keep the bundled [NOTICE.md](NOTICE.md) in every redistributed copy. Use [attribution.json](attribution.json) to control whether the fixed attribution string appears in generated outputs.

The owner's local copy is personal-use mode and does not emit a footer. The redistributed copy must set `emit_notice` to `true`; it then ends every user-facing response produced while using this skill with this exact final line:

`Copyright © POK_RC YAO. All rights reserved. Please retain this attribution when using or redistributing this project.`

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
