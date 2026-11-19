"""Collect controlled original/revised NetLogo diagnostics for comparison plots.

Private model copies add read-only output procedures and controlled fixtures;
the source models and retained baseline observations are not modified. These
are deterministic accounting checks, not independent stochastic replications.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
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
import run_model

MODELS = {
    "original": (ROOT / "results/base/runs/52_ticks/model.nlogox", ROOT / "experiments/original-base.json"),
    "revised": (ROOT / "models/kenya_informal_settlements.nlogox", ROOT / "experiments/base.json"),
}


PROCEDURES = r'''

to comparison-write [filename row]
  file-open filename
  file-print csv:to-row row
  file-close
end

to comparison-base-settings
  __BASE_SETTINGS__
end

to comparison-fixture [capacity formal-weekly direct-weekly hook-weekly]
  clear-all
  comparison-base-settings
  reset-ticks
  set informal-connection-capacity 13
  set a-switch-blackout 0
  set a-switch-demand 0
  set a-switch-debt 0
  set a-switch-safety 0
  set a-switch-safety-other 0
  set a-switch-satisfaction 0
  set blackouts-attitude "only-hurt-kplc"
  create-poles 1 [
    setxy 0 0
    set pole-capacity capacity
    set pole-usage 0
    set pole-overloaded false
  ]
  create-houses 3 [
    setxy who 0
    set income 100000
    set HH-budget income
    set desired-max-expense 100000
    set expense 0
    set demand 0
    set tariff 23
    set informal-flat-fee 200
    set installments-remaining 0
    set attitude-kplc true
    set attitude-ipd true
    set issues-this-tick false
    set switched-this-tick false
    set connection-status "i"
  ]
  ask houses [set nearby-houses other houses with [distance myself <= 3]]
  ask house 1 [set connection-status "f" set demand formal-weekly * 4]
  ask house 2 [set demand hook-weekly * 4]
  ask house 3 [set demand direct-weekly * 4]
  ask pole 0 [
    create-formal-connection-to house 1 [set overloaded false]
    create-informal-sd-to house 3 [set overloaded false]
  ]
  ask house 1 [create-informal-hookon-to house 2 [set overloaded false]]
end

to comparison-energy-case [case-name capacity formal-weekly direct-weekly hook-weekly duration]
  comparison-fixture capacity formal-weekly direct-weekly hook-weekly
  let common-request formal-weekly + min (list direct-weekly 13) + min (list hook-weekly 13)
  repeat duration [
    ; Refresh cash to hold electricity demand constant, and skip switching,
    ; enforcement, billing, negotiation and safety: only energy accounting runs.
    ask houses [set HH-budget income set expense 0 set issues-this-tick false]
    let usage-before [pole-usage] of pole 0
    blackouts
    let requested __REQUESTED_LOAD__
    let is-overloaded [pole-overloaded] of pole 0 = true
    per-week
    tick
    comparison-write "energy.csv" (list __MODEL_LABEL__ case-name ticks capacity
      formal-weekly direct-weekly hook-weekly common-request usage-before requested
      [pole-usage] of pole 0 is-overloaded)
  ]
end

to comparison-neighborhoods
  comparison-base-settings
  random-seed 42
  setup
  foreach [3 2] [radius ->
    let missing-houses count houses with [
      count (nearby-houses with [distance myself <= radius])
      < count (other houses with [distance myself <= radius])
    ]
    let cached-count mean [count nearby-houses with [distance myself <= radius]] of houses
    let actual-count mean [count other houses with [distance myself <= radius]] of houses
    comparison-write "neighborhoods.csv" (list __MODEL_LABEL__ radius count houses
      missing-houses cached-count actual-count
      count houses with [connection-status = "f"]
      mean [income] of houses mean [demand] of houses)
  ]
end

to comparison-probes
  comparison-write "energy.csv" (list "model" "case" "step" "capacity_kwh_week"
    "formal_request_kwh_week" "direct_request_kwh_week" "hook_request_kwh_week"
    "common_capped_request_kwh_week" "usage_before_check" "fresh_requested_load"
    "usage_after_consumption" "overloaded")
  comparison-write "neighborhoods.csv" (list "model" "radius" "households"
    "households_missing_neighbors" "mean_valid_cached_neighbors" "mean_actual_neighbors"
    "initial_formal_households" "mean_income" "mean_demand")
  comparison-energy-case "below_capacity" 20 10 0 0 12
  comparison-energy-case "above_capacity" 20 30 0 0 12
  comparison-energy-case "direct_cap" 100 0 20 0 1
  comparison-energy-case "hook_cap" 100 0 0 20 1
  comparison-neighborhoods
end
'''


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect_model(label, output):
    source, profile = MODELS[label]
    folder = output / label
    if folder.exists():
        raise FileExistsError(f"Probe execution needs a fresh directory: {folder}")
    folder.mkdir(parents=True)
    root = ET.parse(source).getroot()
    params = json.loads(profile.read_text(encoding="utf-8"))["parameters"]
    extra = PROCEDURES.replace("__BASE_SETTINGS__", "\n  ".join(f"set {name} {json.dumps(value)}" for name, value in params.items()))
    extra = extra.replace("__MODEL_LABEL__", json.dumps(label)).replace("__REQUESTED_LOAD__", "[pole-demand] of pole 0" if label == "revised" else '""')
    root.find("code").text += extra
    widgets = root.find("widgets")
    for widget in list(widgets):
        if widget.tag in {"plot", "monitor", "button"}:
            widgets.remove(widget)
    ET.ElementTree(root).write(folder / "probe_model.nlogox", encoding="utf-8", xml_declaration=True)
    dependencies = run_model.copy_model_dependencies(source, folder)
    experiment_root = ET.Element("experiments")
    experiment = ET.SubElement(experiment_root, "experiment", name="comparison_probes", repetitions="1", sequentialRunOrder="true", runMetricsEveryStep="false", timeLimit="1")
    ET.SubElement(experiment, "setup").text = "comparison-probes"
    ET.SubElement(experiment, "go").text = "tick"
    ET.SubElement(ET.SubElement(experiment, "metrics"), "metric").text = "ticks"
    ET.SubElement(ET.SubElement(experiment, "subExperiments"), "subExperiment")
    ET.ElementTree(experiment_root).write(folder / "experiment.xml", encoding="utf-8", xml_declaration=True)
    command = [str(run_model.netlogo_launcher()), "--headless", "--model", str(folder / "probe_model.nlogox"), "--setup-file", str(folder / "experiment.xml"), "--experiment", "comparison_probes", "--table", str(folder / "behaviorspace.csv"), "--threads", "1"]
    started = time.perf_counter()
    with (folder / "run.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=folder, stdout=log, stderr=subprocess.STDOUT, timeout=180, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    provenance = {"model": label, "source_model": source.relative_to(ROOT).as_posix(), "source_sha256": digest(source), "profile": profile.relative_to(ROOT).as_posix(), "profile_sha256": digest(profile), "probe_model_sha256": digest(folder / "probe_model.nlogox"), "included_sources": dependencies, "command": command, "wall_seconds": time.perf_counter() - started, "returncode": result.returncode}
    write_json(folder / "provenance.json", provenance)
    if result.returncode:
        raise RuntimeError(f"Probe engine failed for {label}; see {folder / 'run.log'}")
    return provenance


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def combine(output, filename):
    rows = [row for label in MODELS for row in read_csv(output / label / filename)]
    with (output / filename).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def validate(energy, neighborhoods):
    for label in MODELS:
        records = [row for row in energy if row["model"] == label]
        assert len(records) == 26
        below = [row for row in records if row["case"] == "below_capacity"]
        above = [row for row in records if row["case"] == "above_capacity"]
        direct = next(row for row in records if row["case"] == "direct_cap")
        hook = next(row for row in records if row["case"] == "hook_cap")
        assert float(direct["usage_after_consumption"]) == 13
        if label == "revised":
            assert all(row["overloaded"] == "false" and float(row["usage_after_consumption"]) == 10 for row in below)
            assert all(row["overloaded"] == "true" and float(row["usage_after_consumption"]) == 0 for row in above)
            assert float(hook["usage_after_consumption"]) == 13
        else:
            assert sum(row["overloaded"] == "true" for row in below) == 3
            assert [row["overloaded"] for row in above] == ["false", "true"] * 6
            assert float(hook["usage_after_consumption"]) == 20
    original = [row for row in neighborhoods if row["model"] == "original"]
    revised = [row for row in neighborhoods if row["model"] == "revised"]
    assert {int(row["radius"]): int(row["households_missing_neighbors"]) for row in original} == {3: 1829, 2: 1654}
    assert all(int(row["households_missing_neighbors"]) == 0 for row in revised)
    for a, b in zip(original, revised):
        for key in ["radius", "households", "mean_actual_neighbors", "initial_formal_households", "mean_income", "mean_demand"]:
            assert a[key] == b[key], (key, a[key], b[key])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/model_comparison/probes")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=2) as executor:
        provenance = list(executor.map(lambda label: collect_model(label, output), MODELS))
    energy = combine(output, "energy.csv")
    neighborhoods = combine(output, "neighborhoods.csv")
    validate(energy, neighborhoods)
    manifest = {"passed": True, "probes": provenance, "script_sha256": digest(Path(__file__)), "controlled_steps": 12, "seed_for_neighborhood_setup": 42, "energy_rows": len(energy), "neighborhood_rows": len(neighborhoods), "scope": "Controlled energy accounting fixtures; no full go, provider switching, billing, negotiation, safety or enforcement. Household cash is refreshed before each week to hold demand fixed. The initial-state neighborhood test uses each model's actual setup and its base profile.", "phase": "Each energy row follows blackouts then per-week, then tick. Original usage_before_check is the accumulated usage tested for outage; revised fresh_requested_load is the current-week load tested for outage. Original usage_after_consumption remains an accumulator, not measured weekly delivered energy. Revised usage_after_consumption is weekly delivered energy."}
    write_json(output / "validation.json", manifest)
    print(json.dumps({"output": str(output), "validation": "passed", "energy_rows": len(energy), "neighborhood_rows": len(neighborhoods)}, indent=2))


if __name__ == "__main__":
    main()
