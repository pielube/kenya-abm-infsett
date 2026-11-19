"""Run the revised base model with optional decision logging and weekly metrics.

This is a single-realization diagnostic runner, not an LHS batch or a mechanism
ablation. It snapshots the model and local includes into a fresh output folder,
then enables the model's read-only decision logger after setup. --no-log makes
the equivalent run without file logging for observational-equivalence checks.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_model as runner


def diagnostic_xml(plan, logging=True):
    """Use the standard explicit parameter set with observation-only commands."""
    root = ET.fromstring(runner.experiment_xml(plan, plan["runs"]))
    experiment = root.find("experiment")
    experiment.set("runMetricsEveryStep", "true")
    if logging:
        experiment.find("setup").text = 'setup\ndecision-log-start "decisions.csv"'
        experiment.find("go").text = (
            f"go\ndecision-log-flush\nif ticks >= {plan['steps']} [ decision-log-stop ]"
        )
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def diagnostic_plan(config, base, steps, seed, logging):
    plan = runner.build_plan("base", config_path=config, base_path=base, steps=steps)
    if seed is not None:
        if not 0 <= seed < 2**31:
            raise ValueError("seed must be between 0 and 2**31-1")
        plan["runs"][0]["model_seed"] = seed
    plan["diagnostics"] = {
        "decision_logging": logging,
        "metric_phase": "tick0 after setup; subsequent rows after completed go calls",
        "decision_phase": "decision_tick is the internal pre-increment tick; event_id records within-tick order",
    }
    plan.pop("fingerprint", None)
    plan["fingerprint"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return plan


def save_trajectory(plan, output, raw):
    metrics = plan["config"]["metrics"]
    observations = []
    with raw.open(encoding="utf-8-sig", newline="") as stream:
        reader = runner.complete_csv_rows(stream)
        header = next((row for row in reader if row and row[0] == "[run number]"), None)
        if header is None:
            raise RuntimeError("NetLogo did not write a BehaviorSpace result header")
        if len(set(header)) != len(header):
            raise RuntimeError("Duplicate columns in BehaviorSpace output")
        for values in reader:
            if len(values) != len(header):
                continue
            row = dict(zip(header, values))
            if row["[run number]"] != "1":
                raise RuntimeError("Diagnostic runner expected exactly one realization")
            try:
                values = {name: float(row[reporter]) for name, reporter in metrics.items()}
            except (KeyError, ValueError) as exc:
                raise RuntimeError("Malformed weekly observation") from exc
            observations.append(values)
    observations.sort(key=lambda row: row["ticks"])
    if [row["ticks"] for row in observations] != list(range(plan["steps"] + 1)):
        raise RuntimeError("Weekly trajectory is incomplete or contains duplicate ticks")
    runner.write_csv(output / "trajectory.csv", list(metrics), observations)
    return observations


def summarize_decisions(path):
    counts = {}
    reasons = {}
    successes = 0
    events = 0
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"event_id", "event_kind", "reason", "decision_tick", "household_id", "status_before", "status_after", "attempted", "success"}
        if not required <= set(reader.fieldnames or []):
            raise RuntimeError("Decision log is missing required columns")
        for row in reader:
            events += 1
            if int(row["event_id"]) != events:
                raise RuntimeError("Decision event ids are not consecutive")
            counts[row["event_kind"]] = counts.get(row["event_kind"], 0) + 1
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
            if row["success"] == "true":
                successes += 1
    return {"events": events, "by_kind": counts, "by_reason": reasons, "successful_events": successes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=runner.DEFAULT_CONFIG)
    parser.add_argument("--base", type=Path, default=runner.DEFAULT_BASE)
    parser.add_argument("--steps", type=int, default=52)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/base_revised_diagnostics")
    parser.add_argument("--netlogo-home", type=Path)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    args = parser.parse_args()
    try:
        if args.timeout is not None and args.timeout <= 0:
            raise ValueError("timeout must be positive")
        logging = not args.no_log
        plan = diagnostic_plan(args.config, args.base, args.steps, args.seed, logging)
        output = runner.prepare(plan, args.output, resume=False)
        # prepare() snapshots local __includes as well as the main model.
        xml = diagnostic_xml(plan, logging)
        (output / "experiment.xml").write_text(xml, encoding="utf-8")
        experiment = output / "attempt_001.xml"
        experiment.write_text(xml, encoding="utf-8")
        runner.write_json(output / "attempt_001_runs.json", {"fingerprint": plan["fingerprint"], "run_ids": [1]})
        if args.prepare_only:
            print(f"Prepared diagnostic run in {output}")
            return
        raw = output / "attempt_001.csv"
        command = [str(runner.netlogo_launcher(args.netlogo_home)), "--headless", "--model", str(output / "model.nlogox"), "--setup-file", str(experiment), "--experiment", "python_runs", "--table", str(raw), "--threads", "1"]
        started = time.perf_counter()
        with (output / "attempt_001.log").open("w", encoding="utf-8") as stream:
            result = subprocess.run(command, cwd=output, stdout=stream, stderr=subprocess.STDOUT, timeout=args.timeout, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        elapsed = time.perf_counter() - started
        provenance = {"command": command, "wall_seconds": elapsed, "returncode": result.returncode, "model_sha256": plan["model_sha256"], "model_dependencies": plan.get("model_dependencies", {}), "decision_logging": logging, "seed": plan["runs"][0]["model_seed"], "steps": plan["steps"], "script_sha256": runner.digest(Path(__file__)), "logging_scope": "Evaluated issue-triggered provider choices, informal access attempts and forced disconnections; setup assignment is excluded. Experience reasons co-occur and do not identify individual causal effects."}
        runner.write_json(output / "diagnostic_provenance.json", provenance)
        if result.returncode:
            raise RuntimeError(f"NetLogo returned {result.returncode}; see {output / 'attempt_001.log'}")
        completed = runner.completed_runs(plan, output)
        runner.save_results(plan, output, completed)
        if len(completed) != 1:
            raise RuntimeError("Diagnostic run did not reach its requested final tick")
        observations = save_trajectory(plan, output, raw)
        summary = {"steps": args.steps, "seed": plan["runs"][0]["model_seed"], "weekly_observations": len(observations), "wall_seconds": elapsed, "logging_enabled": logging}
        if logging:
            summary["decisions"] = summarize_decisions(output / "decisions.csv")
        runner.write_json(output / "diagnostic_summary.json", summary)
        print(json.dumps({"output": str(output), **summary}, indent=2))
    except (OSError, ValueError, RuntimeError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
