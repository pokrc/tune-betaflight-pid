# Betaflight Blackbox PID Decision Rules

## Evidence order

1. Verify log identity, firmware, sample rate, motor protocol, PID/filter headers, and field availability.
2. Separate closed-loop behavior from open-loop motor tests. Individual smooth motors do not rule out PID self-excitation during ARM/Airmode.
3. Verify eRPM before attributing a change to RPM filtering.
4. Select 1.024 s low-command windows at comparable throttle. Use them for spectra so stick movement is not mislabeled as vibration.
5. Inspect raw gyro, filtered gyro, D term, motor output, eRPM, voltage/current, and event timing together.
6. Exclude impacts and landing transients from steady-state metrics, but flag them for prop, bell, shaft, bearing, and fastener inspection.
7. Change the smallest justified parameter family and require a new BBL.

## Window definitions

- Stable low-command: median throttle 1080–1700, roll/pitch setpoint 95th percentile at most 100 deg/s, motors above idle, no terminal 0.35 s, no extreme impact sample.
- High-throttle low-command: median throttle 1500–2000 under the same command and impact gates.
- Compare logs only with similar throttle and command envelopes. Prefer the 90th-percentile clean window over a single absolute maximum.
- Analyze only below 45% of sample rate and never above Nyquist. A peak near Nyquist may be aliased.

## Interpretation

- A peak that moves with mechanical motor frequency or its harmonics is motor-synchronous. Address prop/motor condition and RPM filtering before raising PID.
- A peak that stays at nearly one frequency while motor speed changes suggests a structural mode, loose component, soft-mounted mass, or frame resonance.
- High raw gyro with low filtered gyro and low D term means filtering is doing useful work; do not automatically add more filtering.
- High filtered gyro plus high D term in low-command flight supports reducing D/D-min and adding filtering.
- High filtered gyro with motor outputs alternating around the mean after ARM supports closed-loop self-excitation; reduce P/D conservatively and inspect the gyro/frame mounting path.
- Motor heat requires corroboration: D-term energy, high-throttle behavior, saturation, mechanical drag, damaged props/motors, ESC timing, and measured post-flight temperatures. Current alone cannot localize the cause.

## Conservative automatic bands

Use these only on accepted stable windows:

| Classification | Worst roll/pitch filtered gyro 40–400 Hz RMS | Worst roll/pitch D RMS | Candidate action |
|---|---:|---:|---|
| clean | at most 3 deg/s | at most 8 | Keep PID/filter values |
| moderate | at most 8 deg/s | at most 25 | Reduce D about 10%; reduce P at most 5% |
| severe | above either moderate limit | above either moderate limit | Reduce D 20–30%, P 10%, D-min proportionally; strengthen filtering |

These bands are guardrails, not airframe-independent truth. Override the automatic candidate when sample rate, mode, maneuver content, aircraft scale, or logged units make them inappropriate.

## RPM gate

Classify RPM status as:

- **confirmed**: bidirectional DShot is configured, active eRPM is mostly nonzero, and the configured RPM filter has at least one harmonic. RPM_FILTER debug correlation above 0.95 is stronger confirmation when available.
- **configured but unverified**: headers request bidirectional DShot/RPM filtering but active eRPM is missing or mostly zero.
- **absent**: bidirectional DShot is off or no RPM fields exist.

When not confirmed, do not open gyro/D-term filters or raise D. Emit a stage-1 compatibility/telemetry CLI only if ESC support is known.

## Flight-test gates

After every CLI change:

1. Verify `dshot_telemetry_info` with props removed and no telemetry errors.
2. Fit balanced, undamaged props and perform a 10–20 s low-altitude hover/slow translation.
3. Abort immediately on audible oscillation, rapid motor heating, desync, visible blur, telemetry errors, or unexpected motor saturation.
4. Measure motor temperature immediately after landing; “touch warm” is not a calibrated temperature.
5. Save the new BBL and compare matched windows before changing another family.
