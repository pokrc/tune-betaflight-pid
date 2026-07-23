"""Deterministic decision-mode tests for the adaptive Blackbox policy."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_analyzer():
    path = Path(__file__).with_name("analyze_bbl.py")
    spec = importlib.util.spec_from_file_location("adaptive_analyzer", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def headers() -> dict[str, str]:
    return {
        "Firmware revision": "Betaflight 4.5.2",
        "Craft name": "Synthetic test craft",
        "rollPID": "40,50,30",
        "pitchPID": "42,52,32",
        "yawPID": "40,50,0",
        "d_min": "20,22,0",
        "dshot_bidir": "1",
        "rpm_filter_harmonics": "3",
        "motor_pwm_protocol": "6",
        "motor_poles": "14",
        "dterm_lpf1_dyn_hz": "80,160",
        "gyro_lpf1_dyn_hz": "200,400",
        "dterm_lpf2_static_hz": "150",
        "gyro_lpf2_static_hz": "0",
        "tpa_rate": "40",
        "tpa_breakpoint": "1400",
    }


def result(gyro: float, dterm: float, rpm: str, high_dterm: float | None = None) -> dict:
    axis = lambda noise, d: {"worst_p90_filtered_40_400_rms_dps": noise, "worst_p90_d_rms": d}
    high = {"count": 0}
    if high_dterm is not None:
        high = {"count": 8, "axes": {"roll": axis(gyro, high_dterm), "pitch": axis(gyro, high_dterm)}}
    return {
        "stable_windows": {"count": 16, "axes": {"roll": axis(gyro, dterm), "pitch": axis(gyro, dterm)}},
        "high_throttle_windows": high,
        "rpm_telemetry": {"classification": rpm},
        "logs": [{"incidents": []}],
    }


def main() -> None:
    analyzer = load_analyzer()

    no_window = {
        "stable_windows": {"count": 0},
        "high_throttle_windows": {"count": 0},
        "rpm_telemetry": {"classification": "confirmed"},
        "logs": [],
    }
    cli, decision = analyzer.cli_candidate(headers(), no_window, False)
    assert decision["mode"] == "hold" and "\nsave\n" not in cli

    cli, decision = analyzer.cli_candidate(headers(), result(1, 3, "confirmed"), False)
    assert decision["mode"] == "retain" and "set p_roll" not in cli

    cli, decision = analyzer.cli_candidate(headers(), result(30, 100, "absent"), False)
    assert decision["mode"] == "rpm_validation" and "set d_roll" not in cli

    cli, decision = analyzer.cli_candidate(headers(), result(30, 100, "absent"), False, esc_bidir_confirmed=True)
    assert decision["mode"] == "rpm_validation" and "set dshot_bidir = ON" not in cli

    cli, decision = analyzer.cli_candidate(
        headers(), result(30, 100, "absent"), False,
        esc_bidir_confirmed=True, motor_poles_confirmed=14,
    )
    assert decision["mode"] == "rpm_setup"
    assert "set dshot_bidir = ON" in cli and "set motor_poles = 14" in cli
    assert "set d_roll" not in cli and "set debug_mode = RPM_FILTER" not in cli

    cli, decision = analyzer.cli_candidate(headers(), result(14, 45, "confirmed", high_dterm=110), False)
    assert decision["mode"] == "noise_reduction" and "set d_roll" in cli and "set tpa_rate = 65" in cli

    cli, decision = analyzer.cli_candidate(headers(), result(1, 3, "confirmed", high_dterm=8), False)
    assert decision["mode"] == "tpa_only" and "set tpa_rate = 65" in cli and "set d_roll" not in cli
    print("adaptive decision self-test: PASS")


if __name__ == "__main__":
    main()
