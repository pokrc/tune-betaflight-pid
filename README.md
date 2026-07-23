# Tune Betaflight PID from Blackbox Logs

**An evidence-first Codex skill for turning Betaflight Blackbox data into a reviewable tuning CLI.**

[![GitHub stars](https://img.shields.io/github/stars/pokrc/tune-betaflight-pid?style=social)](https://github.com/pokrc/tune-betaflight-pid/stargazers)
[![License](https://img.shields.io/badge/license-PolyForm%20Noncommercial-orange)](LICENSE.md)
[![Betaflight](https://img.shields.io/badge/Betaflight-4.4%2F4.5-blue)](https://betaflight.com/)
[![Companion platform](https://img.shields.io/badge/POKRION-companion%20project-7b61ff)](https://github.com/pokrc/POKRION-Speed-Drone)

Give Codex one or more Betaflight Blackbox `.bbl` logs and receive an auditable analysis plus an adaptive CLI stage for PID, D-term/gyro filtering, RPM validation, and TPA decisions. Raw `.bbl` input is decoded locally; manual CSV conversion is optional rather than required.

This tool is designed for real symptoms—resonance, noisy flight sound, hot motors, D-term noise, suspicious RPM filtering, and before/after flight comparisons. It is a decision aid, not a universal preset: every output must be reviewed against the actual frame, propellers, motors, ESC firmware, battery, firmware version, and motor temperature.

## What makes it different

- **Evidence before edits.** Reads firmware, craft/configuration context, stable flight windows, spectra, filtered gyro and D-term RMS, throttle, and motor saturation.
- **Hard safety gates.** Refuses to imply a tune when the log lacks a stable window, is dominated by impacts/failsafe/landing transients, or falls outside the verified Betaflight 4.4/4.5 family.
- **RPM proof, not RPM assumptions.** `dshot_bidir = ON` alone is not treated as proof that RPM filtering works; active eRPM and, where available, debug correlation are required.
- **Adaptive stage selection.** Automatically selects `hold`, `rpm_validation`, `rpm_setup`, `retain`, `tpa_only`, or `noise_reduction` from the available evidence.
- **Small, explainable steps.** Preserves I-term and feedforward by default and changes one parameter family per short test flight.
- **Reproducible reports.** Produces machine-readable evidence and a paste-ready candidate with comments, provenance, and the final `save` only when gates pass.
- **Deployability checks.** Includes a local `doctor` command, automatic decoder discovery, a minimal dependency manifest, and GitHub Actions validation for policy regressions.
- **Safe sharing mode.** The distributed copy retains the required POK_RC YAO attribution in generated user-facing output.

## Quick start in Codex

Copy the `tune-betaflight-pid/` directory into your Codex skills directory, then invoke it with:

```text
Use $tune-betaflight-pid to analyze this Betaflight .bbl and produce a staged CLI.
```

For the best result, attach the `.bbl`, the relevant `diff all` backup, Betaflight version, board and craft details, motor/propeller/battery information, and a short description of the symptom. A matched baseline log can be supplied for before/after analysis.

The skill automatically chooses the safest supported mode. It does **not** enable bidirectional DShot from a log alone. Supply `--esc-bidir-confirmed` only after independently confirming ESC firmware support and the actual motor-pole count.

## Local deployment

The analyzer runs locally and does not upload Blackbox logs. It needs Python with NumPy plus the `blackbox_decode` executable from the official [Betaflight Blackbox Tools](https://github.com/betaflight/blackbox-tools) project for raw `.bbl` input. The decoder is intentionally not bundled because it is an external, platform-specific project.

```bash
git clone https://github.com/pokrc/tune-betaflight-pid.git
cd tune-betaflight-pid
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# Optional when the decoder is not on PATH: make it discoverable for this shell.
export BLACKBOX_DECODE=/absolute/path/to/blackbox_decode
.venv/bin/python tune-betaflight-pid/scripts/doctor.py --require-ready
```

The commands use the macOS/Linux virtual-environment path; on Windows, use `.venv\\Scripts\\python`. `doctor.py` reports the exact local Python, NumPy version, decoder path, discovery method, and any next action. It does not download software or transmit flight data. Use `--decoder /path/to/blackbox_decode` instead of the environment variable when a per-run override is safer.

## Command-line workflow

After `doctor.py` reports `ready`, the analyzer discovers the decoder through `--decoder`, `BLACKBOX_DECODE`, `PATH`, common local prefixes, or predictable workspace layouts. If you already have decoded CSV input, a decoder is not required.

```bash
.venv/bin/python tune-betaflight-pid/scripts/analyze_bbl.py flight.bbl \
  --output-dir /absolute/path/to/analysis
```

Compare a new flight with a matched baseline:

```bash
.venv/bin/python tune-betaflight-pid/scripts/analyze_bbl.py new-flight.bbl \
  --baseline previous-flight.bbl \
  --output-dir /absolute/path/to/analysis
```

Print the generated CLI directly to standard output when integrating with a local review workflow:

```bash
.venv/bin/python tune-betaflight-pid/scripts/analyze_bbl.py flight.bbl \
  --output-dir /absolute/path/to/analysis \
  --print-cli
```

The analyzer supports explicit attribution control for local testing:

```bash
.venv/bin/python tune-betaflight-pid/scripts/analyze_bbl.py flight.bbl --attribution auto
.venv/bin/python tune-betaflight-pid/scripts/analyze_bbl.py flight.bbl --attribution on
```

The redistributed configuration uses `emit_notice: true`. Do not remove the notice from a redistributed copy without written permission from the rights holder.

## Adaptive output modes

| Mode | What the analyzer does | Active CLI? |
| --- | --- | --- |
| `hold` | Stops because a firmware, field, or stable-window gate failed | No |
| `rpm_validation` | Requires eRPM/RPM-filter evidence before PID/filter work | No |
| `rpm_setup` | Generates a telemetry-only stage after explicit ESC confirmation | Yes |
| `retain` | Keeps a clean, RPM-confirmed tune unchanged | No |
| `tpa_only` | Changes TPA only when high-throttle D energy is at least 2x the low-command value | Yes |
| `noise_reduction` | Applies one bounded P/D/filter stage for RPM-confirmed noise | Yes |

“Fully automatic” means automatic evidence classification and bounded stage generation. It never raises P/D or filter cutoffs, silently changes motor limits, or combines RPM setup with a PID/filter change.

## Output contract

| Output | Purpose |
| --- | --- |
| `analysis.json` | Provenance including decoder discovery, configuration snapshot, quality gates, stable windows, spectra, D-term levels, RPM evidence, motor saturation, incidents, comparison, adaptive mode, confidence, and decision |
| `recommended_cli.txt` | A commented, single-stage Betaflight CLI candidate; `hold`, `rpm_validation`, and `retain` intentionally contain no active tuning command |

Every report should state:

- firmware, board/craft, and usable log duration;
- whether RPM telemetry is confirmed, configured but unverified, or absent;
- representative and worst filtered gyro/D-term RMS in the relevant band;
- motor saturation, throttle windows, and excluded impacts or landing events;
- matched-window change when a baseline is supplied;
- exact parameter deltas, rationale, and next-flight abort conditions.

## Required safety workflow

1. Remove propellers before configuration work and save a rollback backup with `diff all`.
2. Confirm the log came from a prop-fitted flight; a prop-less ARM test cannot validate the final tune.
3. Confirm ESC support and correct `motor_poles` before enabling bidirectional DShot/RPM filtering.
4. Apply one parameter family at a time and make a short, controlled test flight.
5. Land immediately for abnormal oscillation, sound, current, motor temperature, control response, or failsafe behavior.
6. Keep the previous CLI and flight log so every change can be reversed and compared.

The Motors tab is an open-loop check. It cannot reproduce the closed-loop gyro/PID/motor interaction of an aircraft in flight. Never use `motor_output_limit` as a substitute for diagnosing saturation or PID problems.

## Decision boundaries

The skill will not automatically tune when:

- no stable low-command flight window exists;
- required gyro or D-term fields are missing;
- the firmware is outside the verified 4.4/4.5 family;
- the log is dominated by impacts, prop strikes, failsafe, or terminal landing transients;
- RPM telemetry is unverified and the proposed change would open filters or raise D;
- the evidence is insufficient to distinguish mechanical vibration from control-loop instability.

When a clean log shows a stable tune, the correct recommendation may be **no PID change**. Temperature and flight-envelope validation are more useful than forcing another edit.

## Repository guide

- [`tune-betaflight-pid/SKILL.md`](tune-betaflight-pid/SKILL.md) — full Codex workflow and output contract
- [`tune-betaflight-pid/scripts/analyze_bbl.py`](tune-betaflight-pid/scripts/analyze_bbl.py) — local analyzer
- [`tune-betaflight-pid/scripts/doctor.py`](tune-betaflight-pid/scripts/doctor.py) — local dependency and decoder diagnostic
- [`tune-betaflight-pid/scripts/runtime.py`](tune-betaflight-pid/scripts/runtime.py) — portable decoder-discovery helper
- [`tune-betaflight-pid/references/decision-rules.md`](tune-betaflight-pid/references/decision-rules.md) — evidence and safety decisions
- [`tune-betaflight-pid/references/cli-rules.md`](tune-betaflight-pid/references/cli-rules.md) — Betaflight CLI rules and compatibility notes
- [`tune-betaflight-pid/references/human-tuning-playbook.md`](tune-betaflight-pid/references/human-tuning-playbook.md) — PID principles and the bounded adaptive policy
- [`tune-betaflight-pid/scripts/self_test.py`](tune-betaflight-pid/scripts/self_test.py) — deterministic tests for all adaptive decision modes
- [`requirements.txt`](requirements.txt) — minimal local runtime dependency
- [validation workflow](.github/workflows/validate.yml) — CI checks for script syntax and decision-policy regression
- [`NOTICE.md`](NOTICE.md) — required attribution notice
- [`LICENSE.md`](LICENSE.md) — PolyForm Noncommercial terms

## Companion project: POKRION

This skill was developed alongside the **[POKRION High-Speed Micro Quadcopter Platform](https://github.com/pokrc/POKRION-Speed-Drone)**. POKRION provides the airframe, manufacturing, propulsion, and flight-test context; this repository provides a repeatable Blackbox-to-PID analysis workflow. The two projects are useful together, but each can be used independently.

## Contribute and share

If this skill helps you find resonance, validate RPM filtering, reduce motor heat, or make a safer tuning decision, please give it a voluntary **Star** and share a reproducible result:

<https://github.com/pokrc/tune-betaflight-pid>

Issues and pull requests are welcome. Include Betaflight version, board, relevant hardware, test conditions, log-quality notes, and the smallest reproducible change. Never upload GitHub tokens, receiver identifiers, private flight data, or other credentials.

## License and attribution

This project is licensed under [PolyForm Noncommercial 1.0.0](LICENSE.md). Commercial use is prohibited without separate written permission. Redistributed copies must retain [`NOTICE.md`](NOTICE.md), the bundled attribution configuration, and the attribution behavior in the skill.

Betaflight and Blackbox Tools are separate third-party projects. This repository does not claim ownership of their code or trademarks.

`Copyright © POK_RC YAO. All rights reserved. Please retain this attribution when using or redistributing this project.`
