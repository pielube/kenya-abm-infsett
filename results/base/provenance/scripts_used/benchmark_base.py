"""Time fresh, sequential base runs without altering the NetLogo model.

The reported wall time includes the Python runner, JVM launch/compilation,
model setup, simulation, and result writing. It is not a pure go-loop timing.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/kenya_informal_settlements.nlogox"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_name():
    if os.name == "nt":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                           r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor()


def read_result(path):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 1:
        raise ValueError(f"Expected one completed result in {path}")
    return {key: float(value) for key, value in rows[0].items()}


def write_record(output, report):
    summaries = {}
    for horizon in sorted({row["ticks"] for row in report["runs"]}):
        times = [row["wall_seconds"] for row in report["runs"]
                 if row["ticks"] == horizon and row["returncode"] == 0]
        if times:
            summaries[str(horizon)] = {
                "n": len(times), "median_seconds": statistics.median(times),
                "min_seconds": min(times), "max_seconds": max(times),
                "all_seconds": times,
            }
    report["summary"] = summaries
    (output / "timing.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fields = ("ticks", "repetition", "wall_seconds", "returncode", "matches_saved_endpoint",
              "model_hash_unchanged", "output_directory")
    with (output / "timing.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report["runs"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "outputs/base_publication/benchmark")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--slow-full-seconds", type=float, default=60)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "timing.json").exists():
        parser.error("Timing results already exist; choose a fresh --output directory")
    model_hash = digest(MODEL)
    report = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "definition": "End-to-end wall time: fresh Python runner and JVM, setup, simulation, outputs",
        "execution": "Sequential; one NetLogo thread per fresh process; seed 42",
        "requested_repetitions": args.repetitions,
        "environment": {
            "os": platform.platform(), "cpu": cpu_name(), "logical_cpus": os.cpu_count(),
            "python_version": platform.python_version(), "python_executable": sys.executable,
            "netlogo_version": "7.0.3",
        },
        "model_sha256": model_hash,
        "runner_sha256": digest(ROOT / "run_model.py"),
        "base_config_sha256": digest(ROOT / "experiments/base.json"),
        "runs": [], "notes": [],
    }
    print("Starting isolated sequential NetLogo benchmark", flush=True)
    for ticks, reference in ((52, "base_run"), (1480, "base_full")):
        expected = read_result(ROOT / "outputs" / reference / "results.csv")
        for repetition in range(1, args.repetitions + 1):
            run_output = output / f"ticks_{ticks}_repeat_{repetition}"
            if run_output.exists():
                raise FileExistsError(f"Benchmark requires a fresh directory: {run_output}")
            command = [sys.executable, str(ROOT / "run_model.py"), "base", "--steps", str(ticks),
                       "--threads", "1", "--output", str(run_output)]
            started = time.perf_counter()
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            elapsed = time.perf_counter() - started
            (output / f"ticks_{ticks}_repeat_{repetition}.log").write_text(
                result.stdout + result.stderr, encoding="utf-8")
            actual = read_result(run_output / "results.csv") if result.returncode == 0 else {}
            differences = {key: {"expected": value, "actual": actual.get(key)}
                           for key, value in expected.items()
                           if key not in actual or not math.isclose(value, actual[key], rel_tol=1e-12,
                                                                   abs_tol=1e-12)}
            row = {
                "ticks": ticks, "repetition": repetition, "wall_seconds": elapsed,
                "returncode": result.returncode, "command": command,
                "output_directory": str(run_output.relative_to(ROOT)),
                "matches_saved_endpoint": not differences,
                "endpoint_differences": differences,
                "model_hash_unchanged": digest(MODEL) == model_hash,
            }
            report["runs"].append(row)
            write_record(output, report)
            print(json.dumps(row), flush=True)
            if result.returncode or differences or not row["model_hash_unchanged"]:
                raise RuntimeError("Benchmark validation failed; inspect timing.json and run logs")
            if ticks == 1480 and repetition == 1 and elapsed > args.slow_full_seconds:
                report["notes"].append(
                    f"Full-horizon run took {elapsed:.3f}s; further full-horizon repeats omitted "
                    f"under the {args.slow_full_seconds:g}s cutoff.")
                break
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_record(output, report)
    print(json.dumps(report["summary"], indent=2), flush=True)


if __name__ == "__main__":
    main()
