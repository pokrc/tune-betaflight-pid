#!/usr/bin/env python3
"""Decode Betaflight Blackbox logs and emit an analysis plus conservative CLI.

Requires NumPy and an external blackbox_decode executable for .bbl input.
CSV input produced by blackbox_decode is accepted for testing or reuse.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import numpy as np
except ImportError as exc:  # pragma: no cover - exercised only on missing dependency
    raise SystemExit("NumPy is required. Use a Python runtime with NumPy installed.") from exc


AXES = ("roll", "pitch", "yaw")
BANDS = ((40.0, 100.0), (100.0, 200.0), (200.0, 400.0))
DSHOT_PROTOCOLS = {5: "DSHOT150", 6: "DSHOT300", 7: "DSHOT600"}
COPYRIGHT_NOTICE = "Copyright © POK_RC YAO. All rights reserved. Please retain this attribution when using or redistributing this project."
SKILL_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class LogData:
    path: Path
    headers: dict[str, str]
    columns: dict[str, np.ndarray]
    sample_rate: float
    duration: float


def clean_name(name: str) -> str:
    return name.strip()


def base_column(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)\s*$", "", clean_name(name))


def parse_headers(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        for row in csv.reader(handle):
            if len(row) >= 2:
                result[row[0].strip()] = row[1].strip()
    return result


def header_path_for(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}.headers.csv")


def locate_decoder(explicit: str | None) -> Path | None:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        return path if path.is_file() else None
    found = shutil.which("blackbox_decode")
    return Path(found).resolve() if found else None


def attribution_enabled(override: str) -> bool:
    if override == "on":
        return True
    if override == "off":
        return False
    config_path = SKILL_ROOT / "attribution.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        return bool(config.get("emit_notice", False))
    except (OSError, ValueError, TypeError):
        return False


def decode_bbl(path: Path, decoder: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(decoder),
        "--unit-rotation", "deg/s",
        "--unit-acceleration", "g",
        "--unit-amperage", "A",
        "--unit-vbat", "V",
        "--save-headers",
        "--output-dir", str(out_dir),
        str(path),
    ]
    completed = subprocess.run(cmd, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"blackbox_decode failed for {path}:\n{completed.stdout}\n{completed.stderr}"
        )
    candidates = sorted(
        p for p in out_dir.glob(f"{path.stem}.*.csv")
        if not p.name.endswith(".headers.csv") and "gps" not in p.name.lower()
    )
    if not candidates:
        raise RuntimeError(f"Decoder produced no flight CSV for {path}")
    return candidates


def expand_inputs(paths: Iterable[str], decoder: Path | None, out_dir: Path) -> list[Path]:
    result: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        if path.suffix.lower() == ".bbl":
            if decoder is None:
                raise RuntimeError(
                    "No blackbox_decode executable found. Pass --decoder /absolute/path/to/blackbox_decode."
                )
            result.extend(decode_bbl(path, decoder, out_dir / path.stem))
        elif path.suffix.lower() == ".csv" and not path.name.endswith(".headers.csv"):
            result.append(path)
        else:
            raise ValueError(f"Unsupported input: {path}; expected .bbl or decoded .csv")
    return result


def choose_column(names: list[str], wanted: str) -> int | None:
    for index, name in enumerate(names):
        if base_column(name) == wanted:
            return index
    return None


def load_csv(path: Path) -> LogData:
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        reader = csv.reader(handle, skipinitialspace=True)
        try:
            names = [clean_name(x) for x in next(reader)]
        except StopIteration as exc:
            raise ValueError(f"Empty CSV: {path}") from exc

        wanted = ["time"]
        wanted += [f"axisD[{i}]" for i in range(2)]
        wanted += [f"rcCommand[{i}]" for i in range(4)]
        wanted += [f"setpoint[{i}]" for i in range(3)]
        wanted += [f"gyroADC[{i}]" for i in range(3)]
        wanted += [f"gyroUnfilt[{i}]" for i in range(3)]
        wanted += [f"motor[{i}]" for i in range(8)]
        wanted += [f"eRPM[{i}]" for i in range(8)]
        wanted += [f"debug[{i}]" for i in range(8)]
        wanted += ["amperageLatest", "vbatLatest"]
        wanted += [f"accSmooth[{i}]" for i in range(3)]

        indices = {key: choose_column(names, key) for key in wanted}
        indices = {key: value for key, value in indices.items() if value is not None}
        rows: dict[str, list[float]] = {key: [] for key in indices}
        for row in reader:
            if not row or len(row) < len(names):
                continue
            valid = True
            parsed: dict[str, float] = {}
            for key, index in indices.items():
                try:
                    parsed[key] = float(row[index].strip())
                except (ValueError, IndexError):
                    valid = False
                    break
            if valid:
                for key, value in parsed.items():
                    rows[key].append(value)

    columns = {key: np.asarray(values, dtype=float) for key, values in rows.items()}
    if "time" not in columns or len(columns["time"]) < 32:
        raise ValueError(f"No usable time series in {path}")
    time = columns["time"]
    if np.nanmedian(time) > 10000:
        time = (time - time[0]) / 1e6
    else:
        time = time - time[0]
    columns["time"] = time
    dt = np.diff(time)
    valid_dt = dt[(dt > 0) & (dt < 0.1)]
    if not len(valid_dt):
        raise ValueError(f"Cannot infer sample rate from {path}")
    fs = float(1.0 / np.median(valid_dt))
    return LogData(
        path=path,
        headers=parse_headers(header_path_for(path)),
        columns=columns,
        sample_rate=fs,
        duration=float(time[-1]),
    )


def welch_psd(values: np.ndarray, fs: float, max_n: int = 1024) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < 32:
        return np.array([]), np.array([])
    n = min(max_n, 2 ** int(math.floor(math.log2(len(values)))))
    n = max(32, n)
    step = max(1, n // 2)
    starts = list(range(0, len(values) - n + 1, step)) or [0]
    if len(values) - n not in starts:
        starts.append(len(values) - n)
    window = np.hanning(n)
    scale = fs * float(np.sum(window * window))
    psd = None
    for start in starts:
        segment = values[start:start + n]
        segment = segment - float(np.mean(segment))
        power = np.abs(np.fft.rfft(segment * window)) ** 2 / scale
        if len(power) > 2:
            power[1:-1] *= 2.0
        psd = power if psd is None else psd + power
    assert psd is not None
    return np.fft.rfftfreq(n, 1.0 / fs), psd / len(starts)


def band_rms(freq: np.ndarray, psd: np.ndarray, low: float, high: float) -> float:
    mask = (freq >= low) & (freq < high)
    if np.count_nonzero(mask) < 2:
        return float("nan")
    return float(math.sqrt(max(float(np.trapezoid(psd[mask], freq[mask])), 0.0)))


def top_peaks(freq: np.ndarray, psd: np.ndarray, low: float, high: float, count: int = 5) -> list[dict]:
    if len(freq) < 3:
        return []
    ids = np.where((freq >= low) & (freq <= high))[0]
    candidates = [i for i in ids[1:-1] if psd[i] > psd[i - 1] and psd[i] >= psd[i + 1]]
    candidates.sort(key=lambda i: psd[i], reverse=True)
    selected: list[int] = []
    for index in candidates:
        if all(abs(freq[index] - freq[other]) >= 7.0 for other in selected):
            selected.append(index)
        if len(selected) == count:
            break
    return [
        {"frequency_hz": round(float(freq[i]), 2), "asd": round(float(math.sqrt(psd[i])), 4)}
        for i in selected
    ]


def parse_pair(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        parts = [int(float(x.strip())) for x in value.split(",")]
    except ValueError:
        return None
    return (parts[0], parts[1]) if len(parts) >= 2 else None


def parse_triplet(value: str | None) -> list[int] | None:
    if not value:
        return None
    try:
        parts = [int(float(x.strip())) for x in value.split(",")]
    except ValueError:
        return None
    return parts[:3] if len(parts) >= 3 else None


def int_header(headers: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(headers.get(key, str(default))))
    except ValueError:
        return default


def motor_columns(log: LogData) -> list[str]:
    return [f"motor[{i}]" for i in range(8) if f"motor[{i}]" in log.columns]


def normalized_motor_mean(log: LogData) -> np.ndarray:
    cols = motor_columns(log)
    if not cols:
        return np.zeros_like(log.columns["time"])
    limits = parse_pair(log.headers.get("motorOutput")) or (1000, 2000)
    values = np.column_stack([log.columns[key] for key in cols])
    return np.clip((values.mean(axis=1) - limits[0]) / max(limits[1] - limits[0], 1), 0, 1)


def window_metric(log: LogData, start: int, stop: int) -> dict:
    fs = log.sample_rate
    result: dict = {
        "log": log.path.name,
        "time_s": [round(float(log.columns["time"][start]), 3), round(float(log.columns["time"][stop - 1]), 3)],
        "throttle_median": round(float(np.median(log.columns["rcCommand[3]"][start:stop])), 1),
        "setpoint_abs_p95_dps": [],
        "axes": {},
    }
    for axis, name in enumerate(AXES):
        setpoint_key = f"setpoint[{axis}]"
        if setpoint_key in log.columns:
            result["setpoint_abs_p95_dps"].append(
                round(float(np.percentile(np.abs(log.columns[setpoint_key][start:stop]), 95)), 2)
            )
        filt = log.columns[f"gyroADC[{axis}]"][start:stop]
        raw = log.columns.get(f"gyroUnfilt[{axis}]", log.columns[f"gyroADC[{axis}]"])[start:stop]
        freq, raw_psd = welch_psd(raw, fs)
        _, filt_psd = welch_psd(filt, fs)
        upper = min(400.0, fs * 0.45)
        raw_rms = band_rms(freq, raw_psd, 40.0, upper)
        filt_rms = band_rms(freq, filt_psd, 40.0, upper)
        result["axes"][name] = {
            "raw_40_400_rms_dps": round(raw_rms, 3),
            "filtered_40_400_rms_dps": round(filt_rms, 3),
            "raw_bands_rms_dps": [
                round(band_rms(freq, raw_psd, low, min(high, upper)), 3)
                if low < upper else None for low, high in BANDS
            ],
            "top_raw_peaks": top_peaks(freq, raw_psd, 40.0, upper),
        }
        d_key = f"axisD[{axis}]"
        if d_key in log.columns:
            result["axes"][name]["d_rms"] = round(float(np.std(log.columns[d_key][start:stop])), 3)
    return result


def acceptable_window(log: LogData, start: int, stop: int, high_throttle: bool) -> bool:
    cols = log.columns
    throttle = cols["rcCommand[3]"][start:stop]
    median_throttle = float(np.median(throttle))
    lo, hi = ((1500, 2000) if high_throttle else (1080, 1700))
    if not (lo <= median_throttle <= hi):
        return False
    if float(np.mean(normalized_motor_mean(log)[start:stop])) < 0.035:
        return False
    for axis in (0, 1):
        if float(np.percentile(np.abs(cols[f"setpoint[{axis}]"][start:stop]), 95)) > 100:
            return False
        if float(np.max(np.abs(cols[f"gyroADC[{axis}]"][start:stop]))) > 1500:
            return False
    acc_keys = [f"accSmooth[{i}]" for i in range(3)]
    if all(key in cols for key in acc_keys):
        acc = np.column_stack([cols[key][start:stop] for key in acc_keys])
        # Decoded CSVs may contain g or legacy raw accelerometer counts.
        if float(np.nanmedian(np.linalg.norm(acc, axis=1))) > 20.0:
            acc = acc / max(int_header(log.headers, "acc_1G", 2048), 1)
        if float(np.percentile(np.linalg.norm(acc, axis=1), 99.9)) > 10.0:
            return False
    return True


def collect_windows(log: LogData, high_throttle: bool = False) -> list[dict]:
    required = ["rcCommand[3]"] + [f"setpoint[{i}]" for i in range(2)] + [f"gyroADC[{i}]" for i in range(3)]
    if any(key not in log.columns for key in required):
        return []
    n = max(256, int(round(log.sample_rate * 1.024)))
    step = max(64, n // 4)
    final_time = log.duration - 0.35
    result = []
    for start in range(0, len(log.columns["time"]) - n + 1, step):
        stop = start + n
        if log.columns["time"][stop - 1] >= final_time:
            continue
        if acceptable_window(log, start, stop, high_throttle):
            result.append(window_metric(log, start, stop))
    return result


def percentile_metric(windows: list[dict], axis: str, key: str, percentile: float) -> float | None:
    values = [w["axes"][axis].get(key) for w in windows]
    values = [float(x) for x in values if x is not None and math.isfinite(float(x))]
    return round(float(np.percentile(values, percentile)), 3) if values else None


def summarize_windows(windows: list[dict]) -> dict:
    if not windows:
        return {"count": 0}
    summary: dict = {"count": len(windows), "axes": {}}
    for axis in AXES:
        summary["axes"][axis] = {
            "representative_p50_filtered_40_400_rms_dps": percentile_metric(windows, axis, "filtered_40_400_rms_dps", 50),
            "worst_p90_filtered_40_400_rms_dps": percentile_metric(windows, axis, "filtered_40_400_rms_dps", 90),
            "worst_p90_d_rms": percentile_metric(windows, axis, "d_rms", 90),
        }
    ranked = sorted(
        windows,
        key=lambda w: max(w["axes"][a]["filtered_40_400_rms_dps"] for a in ("roll", "pitch")),
        reverse=True,
    )
    summary["worst_examples"] = ranked[:3]
    return summary


def active_mask(log: LogData) -> np.ndarray:
    throttle = log.columns.get("rcCommand[3]", np.zeros_like(log.columns["time"]))
    return (throttle > 1030) & (normalized_motor_mean(log) > 0.03)


def rpm_status(log: LogData) -> dict:
    headers = log.headers
    mask = active_mask(log)
    erpm_keys = [f"eRPM[{i}]" for i in range(8) if f"eRPM[{i}]" in log.columns]
    bidir = int_header(headers, "dshot_bidir") == 1
    harmonics = int_header(headers, "rpm_filter_harmonics")
    status: dict = {
        "configured_bidir": bidir,
        "rpm_filter_harmonics": harmonics,
        "erpm_channels": len(erpm_keys),
        "active_samples": int(np.count_nonzero(mask)),
        "active_erpm_nonzero_fraction": 0.0,
        "debug_erpm_correlation": None,
        "classification": "absent",
    }
    if erpm_keys and np.count_nonzero(mask):
        erpm = np.column_stack([log.columns[key][mask] for key in erpm_keys])
        status["active_erpm_nonzero_fraction"] = round(float(np.mean(erpm > 0)), 5)
        poles = int_header(headers, "motor_poles", 14)
        mechanical_hz = erpm * 100.0 / max((poles / 2.0) * 60.0, 1.0)
        debug_keys = [f"debug[{i}]" for i in range(min(len(erpm_keys), 4)) if f"debug[{i}]" in log.columns]
        if len(debug_keys) == min(len(erpm_keys), 4) and mechanical_hz.size:
            debug = np.column_stack([log.columns[key][mask] for key in debug_keys])
            target = mechanical_hz[:, :len(debug_keys)]
            if np.std(debug) > 0 and np.std(target) > 0:
                correlation = float(np.corrcoef(debug.ravel(), target.ravel())[0, 1])
                if correlation > 0.5:
                    status["debug_erpm_correlation"] = round(correlation, 6)
    nonzero = status["active_erpm_nonzero_fraction"]
    if bidir and harmonics > 0 and nonzero >= 0.75:
        status["classification"] = "confirmed"
    elif bidir:
        status["classification"] = "configured_but_unverified"
    return status


def motor_saturation(log: LogData) -> dict:
    keys = motor_columns(log)
    if not keys:
        return {"available": False}
    values = np.column_stack([log.columns[key] for key in keys])
    limits = parse_pair(log.headers.get("motorOutput")) or (1000, 2000)
    return {
        "available": True,
        "channels": len(keys),
        "any_at_min_fraction": round(float(np.mean(np.min(values, axis=1) <= limits[0] + 2)), 6),
        "any_at_max_fraction": round(float(np.mean(np.max(values, axis=1) >= limits[1] - 2)), 6),
        "p99": round(float(np.percentile(values, 99)), 2),
        "output_limits": list(limits),
    }


def detect_incidents(log: LogData) -> list[dict]:
    incidents: list[dict] = []
    time = log.columns["time"]
    terminal = time >= max(log.duration - 0.35, 0)
    gyro_keys = [f"gyroADC[{i}]" for i in range(3) if f"gyroADC[{i}]" in log.columns]
    if gyro_keys:
        gyro = np.max(np.abs(np.column_stack([log.columns[k] for k in gyro_keys])), axis=1)
        mask = terminal & (gyro > 1000)
        if np.any(mask):
            incidents.append({
                "type": "terminal_impact_or_prop_strike_candidate",
                "time_s": round(float(time[np.argmax(mask)]), 3),
                "peak_filtered_gyro_dps": round(float(np.max(gyro[mask])), 1),
                "excluded_from_steady_analysis": True,
            })
    current = log.columns.get("amperageLatest")
    if current is not None and len(current):
        active = current[active_mask(log)]
        if len(active) > 20:
            threshold = max(float(np.percentile(active, 99.5) * 1.8), float(np.median(active) + 8 * np.std(active)))
            mask = terminal & (current > threshold)
            if np.any(mask):
                incidents.append({
                    "type": "terminal_current_spike_candidate",
                    "time_s": round(float(time[np.argmax(mask)]), 3),
                    "peak_current_a": round(float(np.max(current[mask])), 2),
                    "excluded_from_steady_analysis": True,
                })
    return incidents


def aggregate(logs: list[LogData]) -> dict:
    stable = [window for log in logs for window in collect_windows(log, False)]
    high = [window for log in logs for window in collect_windows(log, True)]
    rpm = [rpm_status(log) for log in logs]
    classification = "confirmed" if any(x["classification"] == "confirmed" for x in rpm) else (
        "configured_but_unverified" if any(x["classification"] == "configured_but_unverified" for x in rpm) else "absent"
    )
    return {
        "logs": [
            {
                "file": log.path.name,
                "duration_s": round(log.duration, 3),
                "sample_rate_hz": round(log.sample_rate, 2),
                "motor_saturation": motor_saturation(log),
                "incidents": detect_incidents(log),
            } for log in logs
        ],
        "stable_windows": summarize_windows(stable),
        "high_throttle_windows": summarize_windows(high),
        "rpm_telemetry": {"classification": classification, "logs": rpm},
    }


def value_from_summary(summary: dict, axis: str, key: str) -> float | None:
    return summary.get("axes", {}).get(axis, {}).get(key)


def classify(summary: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if summary.get("count", 0) == 0:
        return "insufficient_data", ["No accepted stable low-command window"]
    noise_values = [value_from_summary(summary, axis, "worst_p90_filtered_40_400_rms_dps") for axis in ("roll", "pitch")]
    d_values = [value_from_summary(summary, axis, "worst_p90_d_rms") for axis in ("roll", "pitch")]
    if any(value is None for value in noise_values + d_values):
        return "insufficient_data", ["Required filtered gyro or D-term fields are missing"]
    noise = max(float(x) for x in noise_values if x is not None)
    dterm = max(float(x) for x in d_values if x is not None)
    reasons.extend([f"worst roll/pitch filtered gyro RMS={noise:.3f} deg/s", f"worst roll/pitch D RMS={dterm:.3f}"])
    if noise <= 3.0 and dterm <= 8.0:
        return "clean", reasons
    if noise <= 8.0 and dterm <= 25.0:
        return "moderate", reasons
    return "severe", reasons


def firmware_supported(headers: dict[str, str]) -> bool:
    revision = headers.get("Firmware revision", "")
    match = re.search(r"Betaflight\s+(\d+)\.(\d+)", revision)
    return bool(match and int(match.group(1)) == 4 and int(match.group(2)) in (4, 5))


def scaled(value: int, factor: float, minimum: int = 0) -> int:
    return max(minimum, int(round(value * factor)))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def summary_max(summary: dict, key: str) -> float | None:
    values = [value_from_summary(summary, axis, key) for axis in ("roll", "pitch")]
    values = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return max(values) if values else None


def high_throttle_d_ratio(result: dict) -> float | None:
    low = summary_max(result.get("stable_windows", {}), "worst_p90_d_rms")
    high = summary_max(result.get("high_throttle_windows", {}), "worst_p90_d_rms")
    if low is None or high is None or low <= 0:
        return None
    return round(high / low, 3)


def baseline_trend(current: dict, baseline: dict | None) -> dict:
    """Summarize matched low-command risk without treating unlike flights as ground truth."""
    if baseline is None:
        return {"available": False, "classification": "no_baseline"}
    current_noise = summary_max(current.get("stable_windows", {}), "worst_p90_filtered_40_400_rms_dps")
    current_dterm = summary_max(current.get("stable_windows", {}), "worst_p90_d_rms")
    baseline_noise = summary_max(baseline.get("stable_windows", {}), "worst_p90_filtered_40_400_rms_dps")
    baseline_dterm = summary_max(baseline.get("stable_windows", {}), "worst_p90_d_rms")
    if None in (current_noise, current_dterm, baseline_noise, baseline_dterm) or baseline_noise <= 0 or baseline_dterm <= 0:
        return {"available": False, "classification": "insufficient_matched_metrics"}
    noise_ratio = current_noise / baseline_noise
    dterm_ratio = current_dterm / baseline_dterm
    worst_ratio = max(noise_ratio, dterm_ratio)
    if worst_ratio >= 1.25:
        classification = "regressed"
    elif worst_ratio <= 0.85:
        classification = "improved"
    else:
        classification = "similar"
    return {
        "available": True,
        "classification": classification,
        "noise_ratio": round(noise_ratio, 3),
        "dterm_ratio": round(dterm_ratio, 3),
        "comparison_scope": "p90 accepted low-command windows; confirm matched throttle and maneuver envelope",
    }


def adaptive_factors(severity: str, noise: float, dterm: float, trend: dict) -> tuple[float, float, list[str]]:
    """Encode bounded human-tuning reductions; never use this to raise P or D automatically."""
    reasons: list[str] = []
    if severity == "moderate":
        risk = clamp(max(noise / 8.0, dterm / 25.0), 0.0, 1.0)
        p_factor = clamp(0.985 - 0.035 * risk, 0.95, 0.975)
        d_factor = clamp(0.96 - 0.06 * risk, 0.90, 0.94)
        reasons.append("Moderate low-command noise: use a bounded proportional D reduction and a smaller P reduction.")
    elif severity == "severe":
        risk = clamp(max(noise / 8.0, dterm / 25.0), 1.0, 2.5)
        excess = risk - 1.0
        p_factor = clamp(0.92 - 0.03 * excess, 0.87, 0.92)
        d_factor = clamp(0.84 - 0.06 * excess, 0.74, 0.84)
        reasons.append("Severe low-command noise: reduce D first, with a bounded P reduction, then validate mechanically and with a new log.")
    else:
        return 1.0, 1.0, reasons
    if trend.get("classification") == "regressed":
        p_factor = clamp(p_factor - 0.01, 0.85, 1.0)
        d_factor = clamp(d_factor - 0.02, 0.70, 1.0)
        reasons.append("Matched baseline shows a material regression; apply the conservative end of the bounded reduction range.")
    return round(p_factor, 3), round(d_factor, 3), reasons


def evidence_confidence(result: dict, rpm_class: str) -> tuple[str, list[str]]:
    stable_count = int(result.get("stable_windows", {}).get("count", 0))
    incidents = sum(len(log.get("incidents", [])) for log in result.get("logs", []))
    reasons = [f"accepted stable windows={stable_count}", f"RPM telemetry={rpm_class}", f"excluded incidents={incidents}"]
    if stable_count >= 12 and rpm_class == "confirmed" and incidents == 0:
        return "high", reasons
    if stable_count >= 4 and rpm_class == "confirmed":
        return "medium", reasons
    return "low", reasons


def cli_candidate(
    headers: dict[str, str],
    result: dict,
    emit_notice: bool,
    baseline: dict | None = None,
    esc_bidir_confirmed: bool = False,
) -> tuple[str, dict]:
    severity, reasons = classify(result["stable_windows"])
    supported = firmware_supported(headers)
    rpm_class = result["rpm_telemetry"]["classification"]
    roll = parse_triplet(headers.get("rollPID"))
    pitch = parse_triplet(headers.get("pitchPID"))
    yaw = parse_triplet(headers.get("yawPID"))
    dmin = parse_triplet(headers.get("d_min"))
    pid_headers_present = all(x is not None for x in (roll, pitch, yaw, dmin))
    hardware_protocol = int_header(headers, "motor_pwm_protocol", -1)
    high_d_ratio = high_throttle_d_ratio(result)
    trend = baseline_trend(result, baseline)
    confidence, confidence_reasons = evidence_confidence(result, rpm_class)
    noise = summary_max(result["stable_windows"], "worst_p90_filtered_40_400_rms_dps") or 0.0
    dterm = summary_max(result["stable_windows"], "worst_p90_d_rms") or 0.0
    hard_gate = not supported or severity == "insufficient_data" or not pid_headers_present
    if hard_gate:
        mode = "hold"
    elif rpm_class != "confirmed":
        mode = "rpm_setup" if esc_bidir_confirmed and hardware_protocol in DSHOT_PROTOCOLS else "rpm_validation"
    elif severity == "clean":
        mode = "tpa_only" if high_d_ratio is not None and high_d_ratio >= 2.0 else "retain"
    else:
        mode = "noise_reduction"
    active_cli = mode in {"rpm_setup", "tpa_only", "noise_reduction"}
    decision: dict = {
        "classification": severity,
        "mode": mode,
        "firmware_supported": supported,
        "automatic_cli_applicable": active_cli,
        "active_cli_emitted": active_cli,
        "rpm_telemetry": rpm_class,
        "requires_esc_bidirectional_dshot_confirmation": mode in {"rpm_validation", "rpm_setup"},
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "baseline_trend": trend,
        "high_throttle_d_ratio": high_d_ratio,
        "requires_new_bbl": mode != "hold",
        "reasons": reasons,
        "pid_factor": {"p": 1.0, "i": 1.0, "d": 1.0},
        "changed_parameters": [],
    }

    lines = [
        "# Betaflight PID candidate generated from Blackbox evidence",
        f"# Firmware: {headers.get('Firmware revision', 'unknown')}",
        f"# Craft: {headers.get('Craft name', 'unknown')}",
        f"# Classification: {severity}; RPM telemetry: {rpm_class}",
        "# BACK UP FIRST: run 'diff all' and save the output.",
        "# Remove props while applying configuration; use known-good props for flight validation.",
    ]
    if mode == "hold":
        lines += [
            "# STOP: automatic PID changes were withheld because a hard evidence/version gate failed.",
            "# Capture a normal prop-on flight with gyro, D-term, motor, setpoint, and eRPM fields, then rerun.",
            "# No active tuning commands follow.",
        ]
        if emit_notice:
            lines.append(f"# {COPYRIGHT_NOTICE}")
        return "\n".join(lines) + "\n", decision

    if mode == "rpm_validation":
        lines += [
            "# STAGE 1 ONLY: PID and filter changes are withheld until RPM telemetry is confirmed.",
            "# Confirm ESC bidirectional-DShot support and the actual rotor magnet count, then rerun with --esc-bidir-confirmed.",
            "# If bidirectional DShot is already configured, log a short prop-on flight with eRPM and RPM_FILTER debug fields.",
            "# No active tuning commands follow.",
        ]
        if emit_notice:
            lines.append(f"# {COPYRIGHT_NOTICE}")
        return "\n".join(lines) + "\n", decision

    if mode == "rpm_setup":
        lines += [
            "# STAGE 1: ESC compatibility was explicitly confirmed by the operator.",
            "# This stage only enables/verifies RPM telemetry; it does not change PID or filters.",
            f"set motor_pwm_protocol = {DSHOT_PROTOCOLS[hardware_protocol]}",
            "set dshot_bidir = ON",
            f"set motor_poles = {int_header(headers, 'motor_poles', 14)}",
            "set rpm_filter_harmonics = 3",
            "set debug_mode = RPM_FILTER",
            "# Reboot, check dshot_telemetry_info with props removed, then record a prop-on BBL before further tuning.",
            "save",
        ]
        for name, old, new in (
            ("dshot_bidir", int_header(headers, "dshot_bidir"), 1),
            ("rpm_filter_harmonics", int_header(headers, "rpm_filter_harmonics"), 3),
        ):
            if old != new:
                decision["changed_parameters"].append({"name": name, "old": old, "new": new})
        if emit_notice:
            lines.append(f"# {COPYRIGHT_NOTICE}")
        return "\n".join(lines) + "\n", decision

    if mode == "retain":
        lines += [
            "# RETAIN: accepted low-command windows are in the clean band and RPM telemetry is confirmed.",
            "# No PID, filter, TPA, or motor setting change is justified by this log.",
            "# Keep the current tune; validate motor temperature and the intended flight envelope before another change.",
            "# No active CLI commands follow.",
        ]
        if emit_notice:
            lines.append(f"# {COPYRIGHT_NOTICE}")
        return "\n".join(lines) + "\n", decision

    assert roll is not None and pitch is not None and yaw is not None and dmin is not None
    p_factor = d_factor = 1.0
    adaptive_reasons: list[str] = []
    if mode == "noise_reduction":
        p_factor, d_factor, adaptive_reasons = adaptive_factors(severity, noise, dterm, trend)
    decision["pid_factor"] = {"p": p_factor, "i": 1.0, "d": d_factor}
    decision["reasons"].extend(adaptive_reasons)

    tuned_roll = [scaled(roll[0], p_factor, 1), roll[1], scaled(roll[2], d_factor)]
    tuned_pitch = [scaled(pitch[0], p_factor, 1), pitch[1], scaled(pitch[2], d_factor)]
    tuned_dmin = [scaled(dmin[0], d_factor), scaled(dmin[1], d_factor), dmin[2]]
    if mode == "noise_reduction":
        lines += [
            "",
            "# RPM telemetry is confirmed. Apply one evidence-based noise-reduction stage, then collect a new BBL.",
            "# Use direct values; do not run 'simplified_tuning apply' after this block.",
            "set simplified_pids_mode = OFF",
            "set simplified_dterm_filter = OFF",
            "set simplified_gyro_filter = OFF",
            f"set p_roll = {tuned_roll[0]}",
            f"set i_roll = {tuned_roll[1]}",
            f"set d_roll = {tuned_roll[2]}",
            f"set p_pitch = {tuned_pitch[0]}",
            f"set i_pitch = {tuned_pitch[1]}",
            f"set d_pitch = {tuned_pitch[2]}",
            f"set p_yaw = {yaw[0]}",
            f"set i_yaw = {yaw[1]}",
            f"set d_yaw = {yaw[2]}",
            f"set d_min_roll = {tuned_dmin[0]}",
            f"set d_min_pitch = {tuned_dmin[1]}",
        ]
        for key, old, new in (
            ("p_roll", roll[0], tuned_roll[0]), ("d_roll", roll[2], tuned_roll[2]),
            ("p_pitch", pitch[0], tuned_pitch[0]), ("d_pitch", pitch[2], tuned_pitch[2]),
            ("d_min_roll", dmin[0], tuned_dmin[0]), ("d_min_pitch", dmin[1], tuned_dmin[1]),
        ):
            if old != new:
                decision["changed_parameters"].append({"name": key, "old": old, "new": new})

    if mode == "noise_reduction" and severity == "severe":
        filter_factor = 0.80
        dterm_dyn = parse_pair(headers.get("dterm_lpf1_dyn_hz"))
        gyro_dyn = parse_pair(headers.get("gyro_lpf1_dyn_hz"))
        dterm2 = int_header(headers, "dterm_lpf2_static_hz")
        gyro2 = int_header(headers, "gyro_lpf2_static_hz")
        lines.append("")
        lines.append("# Severe low-command noise: strengthen filters; lower Hz means more filtering.")
        if dterm_dyn:
            new_pair = (max(40, scaled(dterm_dyn[0], filter_factor)), max(80, scaled(dterm_dyn[1], filter_factor)))
            lines += [f"set dterm_lpf1_dyn_min_hz = {new_pair[0]}", f"set dterm_lpf1_dyn_max_hz = {new_pair[1]}"]
        if dterm2:
            lines.append(f"set dterm_lpf2_static_hz = {max(80, scaled(dterm2, filter_factor))}")
        if gyro_dyn:
            new_pair = (max(150, scaled(gyro_dyn[0], 0.85)), max(300, scaled(gyro_dyn[1], 0.85)))
            lines += [f"set gyro_lpf1_dyn_min_hz = {new_pair[0]}", f"set gyro_lpf1_dyn_max_hz = {new_pair[1]}"]
        if gyro2:
            lines.append(f"set gyro_lpf2_static_hz = {max(300, scaled(gyro2, 0.85))}")

    if mode in {"noise_reduction", "tpa_only"} and high_d_ratio is not None and high_d_ratio >= 2.0:
        old_rate = int_header(headers, "tpa_rate", 0)
        old_bp = int_header(headers, "tpa_breakpoint", 1350)
        new_rate, new_bp = max(old_rate, 65), min(old_bp, 1350)
        lines += [
            "",
            f"# High-throttle D energy is {high_d_ratio:.2f}x the low-command value.",
            f"set tpa_rate = {new_rate}",
            f"set tpa_breakpoint = {new_bp}",
        ]
        if old_rate != new_rate:
            decision["changed_parameters"].append({"name": "tpa_rate", "old": old_rate, "new": new_rate})
        if old_bp != new_bp:
            decision["changed_parameters"].append({"name": "tpa_breakpoint", "old": old_bp, "new": new_bp})

    lines += [
        "",
        "# Leave I, feedforward, motor_output_limit, dynamic idle, and thrust_linear unchanged.",
        "# After reboot, make one short prop-on test and save a new BBL before the next parameter family.",
        "save",
    ]
    if emit_notice:
        lines.append(f"# {COPYRIGHT_NOTICE}")
    return "\n".join(lines) + "\n", decision


def comparison(current: dict, baseline: dict | None) -> dict | None:
    if baseline is None:
        return None
    result: dict = {"method": "p90 accepted stable low-command windows", "axes": {}}
    for axis in ("roll", "pitch"):
        current_gyro = value_from_summary(current["stable_windows"], axis, "worst_p90_filtered_40_400_rms_dps")
        old_gyro = value_from_summary(baseline["stable_windows"], axis, "worst_p90_filtered_40_400_rms_dps")
        current_d = value_from_summary(current["stable_windows"], axis, "worst_p90_d_rms")
        old_d = value_from_summary(baseline["stable_windows"], axis, "worst_p90_d_rms")
        axis_result = {"current_filtered_gyro_rms": current_gyro, "baseline_filtered_gyro_rms": old_gyro,
                       "current_d_rms": current_d, "baseline_d_rms": old_d}
        if current_gyro is not None and old_gyro:
            axis_result["filtered_gyro_change_percent"] = round(100 * (current_gyro / old_gyro - 1), 2)
        if current_d is not None and old_d:
            axis_result["d_rms_change_percent"] = round(100 * (current_d / old_d - 1), 2)
        result["axes"][axis] = axis_result
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="New .bbl files or decoded flight .csv files")
    parser.add_argument("--baseline", action="append", default=[], help="Optional baseline .bbl/.csv; repeat for several")
    parser.add_argument("--decoder", help="Path to blackbox_decode")
    parser.add_argument("--output-dir", required=True, help="Directory for decoded files and results")
    parser.add_argument("--attribution", choices=("auto", "on", "off"), default="auto",
                        help="Output attribution: auto reads attribution.json; on/off overrides it")
    parser.add_argument("--esc-bidir-confirmed", action="store_true",
                        help="Operator confirms ESC firmware supports bidirectional DShot; permits telemetry-only stage 1 when eRPM is unverified")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    decoder = locate_decoder(args.decoder)
    new_csvs = expand_inputs(args.inputs, decoder, output_dir / "decoded_new")
    baseline_csvs = expand_inputs(args.baseline, decoder, output_dir / "decoded_baseline") if args.baseline else []
    new_logs = [load_csv(path) for path in new_csvs]
    baseline_logs = [load_csv(path) for path in baseline_csvs]
    current = aggregate(new_logs)
    baseline = aggregate(baseline_logs) if baseline_logs else None
    headers = new_logs[0].headers
    emit_notice = attribution_enabled(args.attribution)
    cli, decision = cli_candidate(headers, current, emit_notice, baseline, args.esc_bidir_confirmed)
    payload = {
        "schema_version": 2,
        "inputs": [str(Path(x).expanduser().resolve()) for x in args.inputs],
        "baseline_inputs": [str(Path(x).expanduser().resolve()) for x in args.baseline],
        "configuration": {
            "firmware": headers.get("Firmware revision"),
            "board": headers.get("Board information"),
            "craft": headers.get("Craft name"),
            "motor_protocol_enum": int_header(headers, "motor_pwm_protocol", -1),
            "dshot_bidir": int_header(headers, "dshot_bidir"),
            "motor_poles": int_header(headers, "motor_poles", 0),
            "roll_pid": parse_triplet(headers.get("rollPID")),
            "pitch_pid": parse_triplet(headers.get("pitchPID")),
            "yaw_pid": parse_triplet(headers.get("yawPID")),
            "d_min": parse_triplet(headers.get("d_min")),
            "esc_bidir_confirmed_by_operator": args.esc_bidir_confirmed,
        },
        "quality": {
            "firmware_supported_for_automatic_cli": firmware_supported(headers),
            "accepted_stable_window_count": current["stable_windows"].get("count", 0),
            "required_fields_present": all(
                key in new_logs[0].columns for key in
                ["gyroADC[0]", "gyroADC[1]", "axisD[0]", "axisD[1]", "setpoint[0]", "setpoint[1]"]
            ),
        },
        **current,
        "comparison": comparison(current, baseline),
        "decision": decision,
    }
    if emit_notice:
        payload["copyright_notice"] = COPYRIGHT_NOTICE
    analysis_path = output_dir / "analysis.json"
    cli_path = output_dir / "recommended_cli.txt"
    analysis_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cli_path.write_text(cli, encoding="utf-8")
    summary = {
        "analysis": str(analysis_path),
        "cli": str(cli_path),
        "classification": decision["classification"],
        "automatic_cli_applicable": decision["automatic_cli_applicable"],
        "rpm_telemetry": decision["rpm_telemetry"],
    }
    if emit_notice:
        summary["copyright_notice"] = COPYRIGHT_NOTICE
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
