"""Run a baseline or saved LHS inputs through NetLogo's headless BehaviorSpace."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "experiments/model.json"
DEFAULT_BASE = ROOT / "experiments/base.json"
IDS = ("run_id", "sample_id", "replicate", "model_seed")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def positive_integer(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive whole number")
    return value


def model_defaults(path):
    """Read input values saved in the model interface, without running its code."""
    root = ET.parse(path).getroot()
    values, choices = {}, {}
    for widget in root.find("widgets"):
        name = widget.get("variable")
        if widget.tag == "slider":
            value = float(widget.attrib["default"])
            values[name] = int(value) if value.is_integer() else value
        elif widget.tag == "chooser":
            choices[name] = [choice.attrib["value"] for choice in widget]
            values[name] = choices[name][int(widget.attrib["current"])]
        elif name:
            raise ValueError(f"Unsupported model input widget: {widget.tag} ({name})")
    if not values:
        raise ValueError("No model inputs found")
    return root.attrib["version"], values, choices


def resolve_parameters(overrides, defaults, choices, config):
    """Translate the original table's names and labels to the model's inputs."""
    resolved, seen = dict(defaults), set()
    for original, value in overrides.items():
        name = config["aliases"].get(original, original)
        if name not in defaults or name in seen:
            raise ValueError(f"Unknown or duplicate model parameter: {original}")
        seen.add(name)
        if name in choices:
            value = config["category_values"].get(name, {}).get(value, value)
            if value not in choices[name]:
                raise ValueError(f"Invalid category for {name}: {value!r}")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"{name} must be a finite number")
        resolved[name] = value
    for name in ("n-households", "n-poles", "enforcement-freq"):
        value = resolved[name]
        if not float(value).is_integer() or value < 1:
            raise ValueError(f"{name} must be a positive whole number")
    count = resolved["enforcement-number"]
    if not float(count).is_integer() or not 0 <= count <= resolved["n-poles"]:
        raise ValueError("enforcement-number must be a whole number between 0 and n-poles")
    if resolved["min-informal-fee"] > resolved["max-informal-fee"]:
        raise ValueError("min-informal-fee cannot exceed max-informal-fee")
    return resolved


def read_runs(path):
    """Read runs.csv using its accompanying saved parameter table for types."""
    path = Path(path)
    specification = path.with_name("parameters.csv")
    with specification.open(newline="", encoding="utf-8-sig") as stream:
        definitions = [row for row in csv.DictReader(stream) if row["kind"] != "excluded"]
    names = [p["var"] for p in definitions]
    rows, seen = [], set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        expected = {*IDS, *names}
        if len(reader.fieldnames or []) != len(expected) or set(reader.fieldnames or []) != expected:
            raise ValueError("Run columns must match the saved parameter table plus run IDs and model_seed")
        for raw in reader:
            row = {key: int(raw[key]) for key in IDS}
            for key in IDS[:3]:
                positive_integer(row[key], key)
            if row["run_id"] in seen or not 0 <= row["model_seed"] < 2**31:
                raise ValueError("Run IDs must be unique and model seeds must be between 0 and 2**31-1")
            seen.add(row["run_id"])
            inputs = {}
            for p in definitions:
                text = raw[p["var"]]
                if p["kind"] == "integer":
                    value = int(text)
                elif p["kind"] == "continuous":
                    value = float(text)
                elif p["kind"] == "categorical":
                    value = text
                    if value not in p["categories"].split("|"):
                        raise ValueError(f"Invalid category for {p['var']}: {value!r}")
                else:
                    raise ValueError(f"Unknown parameter kind: {p['kind']}")
                if p["kind"] != "categorical":
                    if not math.isfinite(value) or not float(p["lower"]) <= value <= float(p["upper"]):
                        raise ValueError(f"{p['var']} is outside its saved range")
                inputs[p["var"]] = value
            rows.append({**row, "parameters": inputs})
    if not rows:
        raise ValueError("The run manifest is empty")
    return rows, specification


def build_plan(mode, config_path=DEFAULT_CONFIG, base_path=DEFAULT_BASE,
               runs_path=None, steps=None, limit=None):
    config = read_json(config_path)
    model = (ROOT / config["model"]).resolve()
    version, defaults, choices = model_defaults(model)
    if version != f"NetLogo {config['netlogo_version']}":
        raise ValueError("The model version differs from experiments/model.json")
    metrics = config["metrics"]
    if metrics.get("ticks") != "ticks" or len(set(metrics.values())) != len(metrics):
        raise ValueError("Metrics need a ticks reporter and unique NetLogo expressions")
    if set(metrics) & set(IDS):
        raise ValueError("Metric names cannot use run ID column names")
    if mode == "base":
        base = read_json(base_path)
        steps = base["steps"] if steps is None else steps
        rows = [{"run_id": 1, "sample_id": 1, "replicate": 1,
                 "model_seed": base["seed"], "parameters": base["parameters"]}]
        sources = {"base": digest(base_path)}
    elif mode == "batch":
        rows, specification = read_runs(runs_path)
        if limit is not None:
            positive_integer(limit, "limit")
            rows = rows[:limit]
        steps = config["max_steps"] if steps is None else steps
        sources = {"runs": digest(runs_path), "parameters": digest(specification)}
    else:
        raise ValueError(f"Unknown run mode: {mode}")
    positive_integer(steps, "steps")
    if steps > config["max_steps"]:
        raise ValueError(f"steps cannot exceed the model's stop at {config['max_steps']} ticks")
    for row in rows:
        seed = row["model_seed"]
        if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
            raise ValueError("model_seed must be a whole number between 0 and 2**31-1")
        row["parameters"] = resolve_parameters(row["parameters"], defaults, choices, config)
    plan = {"mode": mode, "model_path": str(model), "model_version": version,
            "runner_sha256": digest(__file__),
            "model_sha256": digest(model), "config": config, "sources": sources,
            "steps": steps, "runs": rows}
    plan["fingerprint"] = hashlib.sha256(
        json.dumps(plan, sort_keys=True, allow_nan=False).encode("utf-8")
    ).hexdigest()
    return plan


def experiment_xml(plan, runs):
    """One subexperiment per row; never take a Cartesian product of LHS columns."""
    root = ET.Element("experiments")
    experiment = ET.SubElement(root, "experiment", name="python_runs", repetitions="1",
                               sequentialRunOrder="true", runMetricsEveryStep="false",
                               timeLimit=str(plan["steps"]))
    ET.SubElement(experiment, "setup").text = "setup"
    ET.SubElement(experiment, "go").text = "go"
    metrics = ET.SubElement(experiment, "metrics")
    for reporter in plan["config"]["metrics"].values():
        ET.SubElement(metrics, "metric").text = reporter
    subexperiments = ET.SubElement(experiment, "subExperiments")
    for row in runs:
        sub = ET.SubElement(subexperiments, "subExperiment")
        for name, value in {**row["parameters"], "random-seed": row["model_seed"]}.items():
            values = ET.SubElement(sub, "enumeratedValueSet", variable=name)
            literal = json.dumps(value, ensure_ascii=False, allow_nan=False)
            ET.SubElement(values, "value", value=literal)
    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def write_csv(path, fields, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare(plan, output, resume=False):
    output = Path(output).resolve()
    if output.exists():
        if not resume:
            raise FileExistsError(f"Output folder exists: {output}. Use --resume or a new folder.")
        if read_json(output / "plan.json")["fingerprint"] != plan["fingerprint"]:
            raise ValueError("Cannot resume: model, settings, or inputs changed. Use a new output folder.")
        if digest(output / "model.nlogox") != plan["model_sha256"]:
            raise ValueError("The saved model snapshot changed; use a new output folder")
    else:
        output.mkdir(parents=True)
        shutil.copyfile(plan["model_path"], output / "model.nlogox")
        if digest(output / "model.nlogox") != plan["model_sha256"]:
            raise ValueError("The source model changed while preparing the experiment")
        write_json(output / "plan.json", plan)
        fields = [*IDS, *plan["runs"][0]["parameters"]]
        write_csv(output / "inputs.csv", fields,
                  ({**{key: row[key] for key in IDS}, **row["parameters"]} for row in plan["runs"]))
        (output / "experiment.xml").write_text(experiment_xml(plan, plan["runs"]), encoding="utf-8")
    return output


def complete_csv_rows(stream):
    """Stop at a truncated CSV record, keeping earlier complete records usable."""
    reader = csv.reader(stream, strict=True)
    while True:
        try:
            yield next(reader)
        except (StopIteration, csv.Error):
            return


def completed_runs(plan, output):
    """Accept only complete final records; interrupted attempts stay available."""
    completed = {}
    by_id = {row["run_id"]: row for row in plan["runs"]}
    for mapping in sorted(Path(output).glob("attempt_*_runs.json")):
        attempt = read_json(mapping)
        if attempt["fingerprint"] != plan["fingerprint"]:
            raise ValueError(f"Attempt belongs to a different experiment: {mapping}")
        if (len(set(attempt["run_ids"])) != len(attempt["run_ids"])
                or not set(attempt["run_ids"]) <= set(by_id)):
            raise ValueError(f"Invalid run IDs in {mapping}")
        raw_path = mapping.with_name(mapping.name.replace("_runs.json", ".csv"))
        if not raw_path.exists():
            continue
        with raw_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = complete_csv_rows(stream)
            first = next(reader, [])
            if (first and first[0].startswith("BehaviorSpace results")
                    and f"({plan['model_version']})" not in first[0]):
                raise ValueError(f"NetLogo runtime version differs from {plan['model_version']}")
            header = next((r for r in reader if r and r[0] == "[run number]"), None)
            if header is None:
                continue
            required = {*plan["config"]["metrics"].values(), *plan["runs"][0]["parameters"], "random-seed"}
            if not required <= set(header) or len(header) != len(set(header)):
                raise ValueError(f"Missing or duplicate input/result columns in {raw_path}")
            seen = set()
            for values in reader:
                if len(values) != len(header):
                    continue  # A process can be interrupted halfway through writing a record.
                raw = dict(zip(header, values))
                try:
                    number = int(raw["[run number]"])
                    metrics = {name: float(raw[reporter])
                               for name, reporter in plan["config"]["metrics"].items()}
                except ValueError:
                    continue
                if metrics["ticks"] != plan["steps"] or not all(map(math.isfinite, metrics.values())):
                    continue
                if not 1 <= number <= len(attempt["run_ids"]) or number in seen:
                    raise ValueError(f"Invalid or duplicate completed run number in {raw_path}")
                seen.add(number)
                run_id = attempt["run_ids"][number - 1]
                expected = {**by_id[run_id]["parameters"], "random-seed": by_id[run_id]["model_seed"]}
                for name, value in expected.items():
                    matches = raw[name] == value if isinstance(value, str) else math.isclose(
                        float(raw[name]), value, rel_tol=1e-12, abs_tol=1e-12)
                    if not matches:
                        raise ValueError(f"Recorded {name} differs from the plan for run {run_id}")
                if run_id in completed and completed[run_id] != metrics:
                    raise ValueError(f"Conflicting results for run {run_id}")
                completed[run_id] = metrics
    return completed


def save_results(plan, output, completed):
    fields = [*IDS, *plan["config"]["metrics"]]
    write_csv(Path(output) / "results.csv", fields,
              ({**{key: row[key] for key in IDS}, **completed[row["run_id"]]}
               for row in plan["runs"] if row["run_id"] in completed))


def netlogo_launcher(home=None):
    homes = [Path(home)] if home else [
        Path(os.environ["NETLOGO_HOME"]) if os.environ.get("NETLOGO_HOME") else ROOT / ".tools/NetLogo 7.0.3",
        Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "NetLogo 7.0.3",
    ]
    for folder in homes:
        for name in ("NetLogo_Console.exe", "NetLogo_Console"):
            launcher = folder / name
            if launcher.is_file():
                return launcher.resolve()
    raise FileNotFoundError("NetLogo 7.0.3 not found. Set NETLOGO_HOME or pass --netlogo-home. "
                            "Use --prepare-only to prepare inputs without NetLogo.")


def execute(plan, output, launcher, threads=1, timeout=None):
    positive_integer(threads, "threads")
    completed = completed_runs(plan, output)
    pending = [r for r in plan["runs"] if r["run_id"] not in completed]
    if not pending:
        save_results(plan, output, completed)
        return len(completed)
    attempt_id = max((int(p.name.split("_")[1]) for p in output.glob("attempt_*_runs.json")), default=0) + 1
    stem = output / f"attempt_{attempt_id:03d}"
    xml_path, raw_path = stem.with_suffix(".xml"), stem.with_suffix(".csv")
    xml_path.write_text(experiment_xml(plan, pending), encoding="utf-8")
    write_json(stem.with_name(stem.name + "_runs.json"),
               {"fingerprint": plan["fingerprint"], "run_ids": [r["run_id"] for r in pending]})
    command = [str(launcher), "--headless", "--model", str(output / "model.nlogox"),
               "--setup-file", str(xml_path), "--experiment", "python_runs",
               "--table", str(raw_path), "--threads", str(threads)]
    print(f"Running {len(pending)} pending runs ({len(completed)} already complete); log: {stem}.log", flush=True)
    error = None
    with stem.with_suffix(".log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    cwd=output, timeout=timeout, check=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result.returncode:
                error = f"NetLogo exited with code {result.returncode}"
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            error = type(exc).__name__
    completed = completed_runs(plan, output)
    save_results(plan, output, completed)
    if error or len(completed) != len(plan["runs"]):
        raise RuntimeError(f"{error or 'Some runs did not reach the requested tick'}. "
                           f"Completed {len(completed)}/{len(plan['runs'])}. See {stem}.log; "
                           "rerun with --resume to retry unfinished runs.")
    return len(completed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    for mode in ("base", "batch"):
        sub = commands.add_parser(mode)
        sub.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
        sub.add_argument("--output", type=Path, default=ROOT / f"outputs/{mode}_run")
        sub.add_argument("--steps", type=int)
        sub.add_argument("--netlogo-home", type=Path)
        sub.add_argument("--threads", type=int, default=1)
        sub.add_argument("--timeout", type=float)
        sub.add_argument("--prepare-only", action="store_true")
        sub.add_argument("--resume", action="store_true")
        if mode == "base":
            sub.add_argument("--base", type=Path, default=DEFAULT_BASE)
        else:
            sub.add_argument("--runs", type=Path, default=ROOT / "outputs/lhs_256/runs.csv")
            sub.add_argument("--limit", type=int)
    args = parser.parse_args()
    try:
        positive_integer(args.threads, "threads")
        if args.timeout is not None and (not math.isfinite(args.timeout) or args.timeout <= 0):
            raise ValueError("timeout must be a positive number of seconds")
        plan = build_plan(args.mode, args.config, getattr(args, "base", DEFAULT_BASE),
                          getattr(args, "runs", None), args.steps, getattr(args, "limit", None))
        launcher = None if args.prepare_only else netlogo_launcher(args.netlogo_home)
        output = prepare(plan, args.output, args.resume)
        if args.prepare_only:
            print(f"Prepared {len(plan['runs'])} runs of {plan['steps']} ticks in {output}")
        else:
            count = execute(plan, output, launcher, args.threads, args.timeout)
            print(f"Completed {count} runs. Results: {output / 'results.csv'}")
    except (OSError, ValueError, RuntimeError, KeyError, ET.ParseError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
