"""Export base-model observations without changing the model's random stream.

The private model copy adds observer-only globals and procedures. Every added
observation runs inside ``with-local-randomness``; the supplied setup/go code is
left intact. Endpoints are checked against the pre-existing seed-42 results.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_model


AGGREGATE_FIELDS = [
    "tick", "households", "poles", "formal_households", "informal_households",
    "unconnected_households", "service_drop_households", "hookon_households",
    "trust_kplc_pct", "trust_ipd_pct", "mean_debt", "mean_switchcount",
    "overloaded_poles", "overloaded_households", "issues_households",
    "overspending_households", "formal_overspending", "informal_overspending",
    "formal_positive_kplc", "formal_positive_ipd", "informal_positive_kplc",
    "informal_positive_ipd", "like_both", "like_kplc_only", "like_ipd_only",
    "like_neither", "informal_cheaper_households", "formal_installments_due",
    "mean_informal_fee", "mean_spend_ratio", "mean_installments_remaining",
    "cumulative_nonpayment_disconnects_kplc", "cumulative_nonpayment_disconnects_ipd",
    "cumulative_negotiations", "mean_pole_usage", "max_pole_usage",
    "total_pole_usage", "formal_unpaid_installments", "informal_missed_payments",
    "blackout_phase_formal_exposed", "blackout_phase_informal_exposed",
    "blackout_phase_total_exposed",
]
HOUSEHOLD_FIELDS = [
    "tick", "who", "x", "y", "status", "access_type", "income", "demand",
    "tariff", "informal_fee", "desired_expense", "expense", "budget",
    "spend_ratio", "debt_index", "installments_remaining", "unpaid_installments",
    "unpaid_informal_fees", "attitude_kplc", "attitude_ipd", "issues",
    "switch_counter", "weeks_continuous_informal", "cant_afford_counter",
    "formal_next_month_cost", "informal_next_month_cost", "source_id", "source_pole_id",
]
POLE_FIELDS = [
    "tick", "who", "x", "y", "usage", "capacity", "overloaded",
    "formal_connections", "direct_informal_connections", "hookon_connections",
]
LINK_FIELDS = ["tick", "type", "source_id", "target_id", "source_x", "source_y", "target_x", "target_y", "overloaded"]
TRANSITION_FIELDS = ["tick", "from_status", "to_status", "households"]
QUINTILE_FIELDS = [
    "tick", "income_quintile", "households", "mean_income", "median_income",
    "formal_households", "informal_households", "unconnected_households",
    "positive_kplc", "positive_ipd", "mean_debt", "mean_spend_ratio",
    "overspending_households", "formal_installments_due", "blackout_phase_exposed",
]
SNAPSHOTS = [0, 4, 12, 24, 52, 104, 220, 440, 740, 1100, 1480]


def netlogo_list(values):
    return "(list " + " ".join(json.dumps(value) for value in values) + ")"


OBSERVER_CODE = r'''

; Observer-only publication data export. Supplied setup/go procedures unchanged.
to publication-setup
  setup
  with-local-randomness [
    set publication-houses sort houses
    set publication-poles sort poles
    let income-order sort-by [[a b] -> [income] of a < [income] of b] publication-houses
    set publication-income-groups (map [ q -> sublist income-order (q * 400) ((q + 1) * 400) ] (range 5))
    set publication-outage-formal 0
    set publication-outage-informal 0
    set publication-outage-total 0
    set publication-outage-by-quintile n-values 5 [0]
    set publication-previous-statuses map [ h -> [connection-status] of h ] publication-houses
    publication-initialize-files
    publication-observe
  ]
end

to publication-go
  go
  with-local-randomness [
    publication-observe
    if ticks = 1480 [ file-close-all ]
  ]
end

to publication-write-row [ filename values ]
  file-open filename
  file-print csv:to-row values
end

to publication-initialize-files
  file-close-all
  foreach ["aggregate.csv" "households.csv" "poles.csv" "links.csv" "transitions.csv" "income_quintiles.csv"] [ filename ->
    if file-exists? filename [ file-delete filename ]
  ]
  publication-write-row "aggregate.csv" __AGGREGATE_HEADER__
  publication-write-row "households.csv" __HOUSEHOLD_HEADER__
  publication-write-row "poles.csv" __POLE_HEADER__
  publication-write-row "links.csv" __LINK_HEADER__
  publication-write-row "transitions.csv" __TRANSITION_HEADER__
  publication-write-row "income_quintiles.csv" __QUINTILE_HEADER__
end

to publication-capture-reliability
  with-local-randomness [
    let exposed houses with [any? my-links with [overloaded = true]]
    set publication-outage-formal count exposed with [connection-status = "f"]
    set publication-outage-informal count exposed with [connection-status = "i"]
    set publication-outage-total count exposed
    set publication-outage-by-quintile map [ group ->
      length filter [h -> [any? my-links with [overloaded = true]] of h] group
    ] publication-income-groups
  ]
end

to publication-observe
  let formals houses with [ connection-status = "f" ]
  let informals houses with [ connection-status = "i" ]
  publication-write-row "aggregate.csv" (list
    ticks count houses count poles count formals count informals
    count houses with [connection-status = "n"]
    count houses with [any? my-informal-sds]
    count houses with [any? my-in-informal-hookons]
    (100 * count houses with [attitude-kplc = true] / count houses)
    (100 * count houses with [attitude-ipd = true] / count houses)
    mean [debt] of houses mean [switchcount] of houses
    count poles with [pole-overloaded = true]
    count houses with [any? my-links with [overloaded = true]]
    count houses with [issues-this-tick = true]
    count houses with [spend-ratio > 1]
    count formals with [spend-ratio > 1]
    count informals with [spend-ratio > 1]
    count formals with [attitude-kplc = true]
    count formals with [attitude-ipd = true]
    count informals with [attitude-kplc = true]
    count informals with [attitude-ipd = true]
    count houses with [attitude-kplc = true and attitude-ipd = true]
    count houses with [attitude-kplc = true and attitude-ipd = false]
    count houses with [attitude-kplc = false and attitude-ipd = true]
    count houses with [attitude-kplc = false and attitude-ipd = false]
    count houses with [next-month-informal-cost < next-month-formal-cost]
    count formals with [installments-remaining > 0]
    mean [informal-flat-fee] of houses
    mean [spend-ratio] of houses mean [installments-remaining] of houses
    count-disconnect-kplc count-disconnect-ipd count-negotiate
    mean [pole-usage] of poles max [pole-usage] of poles sum [pole-usage] of poles
    count formals with [times-installment-not-paid > 0]
    count informals with [times-ipd-not-paid > 0]
    publication-outage-formal publication-outage-informal publication-outage-total
  )
  foreach publication-poles [ p -> ask p [
    let hookons sum [count my-informal-hookons] of formal-connection-neighbors
    publication-write-row "poles.csv" (list ticks who xcor ycor pole-usage pole-capacity
      (pole-overloaded = true) count my-formal-connections count my-informal-sds hookons)
  ] ]
  foreach (range 5) [ q ->
    let group turtle-set item q publication-income-groups
    publication-write-row "income_quintiles.csv" (list ticks (q + 1) count group
      mean [income] of group median [income] of group
      count group with [connection-status = "f"]
      count group with [connection-status = "i"]
      count group with [connection-status = "n"]
      count group with [attitude-kplc = true] count group with [attitude-ipd = true]
      mean [debt] of group mean [spend-ratio] of group
      count group with [spend-ratio > 1]
      count group with [connection-status = "f" and installments-remaining > 0]
      item q publication-outage-by-quintile)
  ]
  if ticks > 0 [
    let new-statuses map [ h -> [connection-status] of h ] publication-houses
    foreach ["f" "i" "n"] [ old ->
      foreach ["f" "i" "n"] [ new ->
        let indicators (map [ [a b] -> ifelse-value (a = old and b = new) [1] [0] ] publication-previous-statuses new-statuses)
        publication-write-row "transitions.csv" (list ticks old new sum indicators)
      ]
    ]
    set publication-previous-statuses new-statuses
  ]
  if member? ticks __SNAPSHOTS__ [
    foreach publication-houses [ h -> ask h [
      let access-type "unconnected"
      let source-id -1
      let source-pole-id -1
      if any? my-formal-connections [
        set access-type "formal"
        set source-id [who] of first sort in-formal-connection-neighbors
        set source-pole-id source-id
      ]
      if any? my-informal-sds [
        set access-type "service_drop"
        set source-id [who] of first sort in-informal-sd-neighbors
        set source-pole-id source-id
      ]
      if any? my-in-informal-hookons [
        set access-type "hookon"
        let source-house first sort in-informal-hookon-neighbors
        set source-id [who] of source-house
        if any? [in-formal-connection-neighbors] of source-house [
          set source-pole-id [who] of first sort [in-formal-connection-neighbors] of source-house
        ]
      ]
      publication-write-row "households.csv" (list ticks who xcor ycor connection-status access-type
        income demand tariff informal-flat-fee desired-max-expense expense HH-budget spend-ratio debt
        installments-remaining times-installment-not-paid times-ipd-not-paid
        attitude-kplc attitude-ipd (issues-this-tick = true) switchcount weeks-continuous-informal cant-afford
        next-month-formal-cost next-month-informal-cost source-id source-pole-id)
    ] ]
  ]
  if member? ticks [0 52 1480] [
    foreach sort links [ edge-agent -> ask edge-agent [
      let kind "pole"
      let is-overloaded false
      if breed = formal-connections [set kind "formal" set is-overloaded overloaded = true]
      if breed = informal-sds [set kind "service_drop" set is-overloaded overloaded = true]
      if breed = informal-hookons [set kind "hookon" set is-overloaded overloaded = true]
      publication-write-row "links.csv" (list ticks kind [who] of end1 [who] of end2
        [xcor] of end1 [ycor] of end1 [xcor] of end2 [ycor] of end2 is-overloaded)
    ] ]
  ]
end
'''


def observer_code():
    code = OBSERVER_CODE
    for placeholder, values in {
        "__AGGREGATE_HEADER__": AGGREGATE_FIELDS,
        "__HOUSEHOLD_HEADER__": HOUSEHOLD_FIELDS,
        "__POLE_HEADER__": POLE_FIELDS,
        "__LINK_HEADER__": LINK_FIELDS,
        "__TRANSITION_HEADER__": TRANSITION_FIELDS,
        "__QUINTILE_HEADER__": QUINTILE_FIELDS,
        "__SNAPSHOTS__": SNAPSHOTS,
    }.items():
        code = code.replace(placeholder, netlogo_list(values))
    return code


def validate_outputs(output):
    with (output / "aggregate.csv").open(newline="", encoding="utf-8") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 1481, f"Expected 1481 snapshots, got {len(records)}"
    by_tick = {int(row["tick"]): row for row in records}
    checks = []
    for ticks, folder in [(52, "base_run"), (1480, "base_full")]:
        with (ROOT / "outputs" / folder / "results.csv").open(newline="", encoding="utf-8") as stream:
            expected = next(csv.DictReader(stream))
        differences = {}
        for field in run_model.read_json(ROOT / "experiments/model.json")["metrics"]:
            actual = float(by_tick[ticks]["tick" if field == "ticks" else field])
            wanted = float(expected[field])
            if not math.isclose(actual, wanted, rel_tol=1e-12, abs_tol=1e-12):
                differences[field] = {"actual": actual, "expected": wanted}
        checks.append({"tick": ticks, "reference": f"outputs/{folder}/results.csv", "differences": differences, "passed": not differences})
    for row in records:
        assert sum(float(row[key]) for key in ["formal_households", "informal_households", "unconnected_households"]) == 2000
        assert sum(float(row[key]) for key in ["service_drop_households", "hookon_households"]) == float(row["informal_households"])
    (output / "validation.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    if not all(check["passed"] for check in checks):
        raise RuntimeError("Instrumented run differs from reference endpoints; see validation.json")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/base_publication/data")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "models/kenya_informal_settlements.nlogox"
    source_bytes = source.read_bytes()
    model_text = source_bytes.decode("utf-8")
    original_globals = "globals [ max-income count-disconnect-kplc count-disconnect-ipd count-negotiate ]"
    added_globals = original_globals[:-1] + "publication-houses publication-poles publication-previous-statuses publication-income-groups publication-outage-formal publication-outage-informal publication-outage-total publication-outage-by-quintile ]"
    assert model_text.count(original_globals) == 1
    assert model_text.count("]]></code>") == 1
    extra_code = observer_code()
    blackout_call = "  blackouts\n"
    assert model_text.count(blackout_call) == 1
    private_text = model_text.replace(original_globals, added_globals).replace("]]></code>", extra_code + "]]></code>")
    private_text = private_text.replace(blackout_call, blackout_call + "  publication-capture-reliability\n")
    (output / "observed_model.nlogox").write_text(private_text, encoding="utf-8", newline="")
    (output / "observer_procedures.nls").write_text(extra_code, encoding="utf-8")
    base = run_model.read_json(ROOT / "experiments/base.json")
    config = run_model.read_json(ROOT / "experiments/model.json")
    experiment = ET.Element("experiments")
    exp = ET.SubElement(experiment, "experiment", name="publication_observation", repetitions="1", sequentialRunOrder="true", runMetricsEveryStep="false", timeLimit="1480")
    ET.SubElement(exp, "setup").text = "publication-setup"
    ET.SubElement(exp, "go").text = "publication-go"
    metrics = ET.SubElement(exp, "metrics")
    ET.SubElement(metrics, "metric").text = "ticks"
    subexperiments = ET.SubElement(exp, "subExperiments")
    subexperiment = ET.SubElement(subexperiments, "subExperiment")
    for name, value in {**base["parameters"], "random-seed": base["seed"]}.items():
        values = ET.SubElement(subexperiment, "enumeratedValueSet", variable=name)
        ET.SubElement(values, "value", value=json.dumps(value))
    ET.indent(experiment, space="  ")
    ET.ElementTree(experiment).write(output / "experiment.xml", encoding="utf-8", xml_declaration=True)
    command = [str(run_model.netlogo_launcher()), "--headless", "--model", str(output / "observed_model.nlogox"), "--setup-file", str(output / "experiment.xml"), "--experiment", "publication_observation", "--table", str(output / "behaviorspace.csv"), "--threads", "1"]
    provenance = {
        "source_model": str(source.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "observed_model_sha256": run_model.digest(output / "observed_model.nlogox"),
        "observer_code_sha256": hashlib.sha256(extra_code.encode()).hexdigest(),
        "script_sha256": run_model.digest(Path(__file__)),
        "seed": base["seed"], "steps": 1480, "parameters": base["parameters"],
        "snapshot_ticks": SNAPSHOTS, "command": command,
        "phase": "Tick0 is after setup; tick t>0 is immediately after original go advances tick t-1 to t, before the next go. Monthly closing observations have t mod4=0. Enforcement processed at prior tick mod110=0 is visible at t=1,111,...",
        "random_stream": "All added reads, sorting, iteration, counters, and export commands occur inside with-local-randomness; original setup and go execute outside it. Observer globals do not occur in supplied dynamics.",
        "source_edits": ["Added observer-only globals to globals declaration", "Appended observer setup/go/export procedures", "Inserted publication-capture-reliability immediately after original blackouts call; the hook only reads household/link state inside with-local-randomness"],
        "transitions": "Adjacent end-of-tick statuses only; same-tick intermediate changes are not observed. Diagonal entries represent unchanged final status, not necessarily absence of intratick events.",
        "measurement": "Pole usage is accumulated by original model until overload handling resets it. End-of-tick overload flags came from the pre-consumption blackout check. Household cost fields are cumulative within the current four-tick month.",
        "definitions": {"households.csv": HOUSEHOLD_FIELDS, "poles.csv": POLE_FIELDS, "aggregate.csv": AGGREGATE_FIELDS, "links.csv": LINK_FIELDS, "transitions.csv": TRANSITION_FIELDS, "income_quintiles.csv": QUINTILE_FIELDS},
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    if args.prepare_only:
        print(f"Prepared observer model and experiment in {output}")
        return
    started = time.perf_counter()
    with (output / "run.log").open("w", encoding="utf-8") as log:
        result = subprocess.run(command, cwd=output, stdout=log, stderr=subprocess.STDOUT, check=False, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    provenance["observation_wall_seconds"] = time.perf_counter() - started
    provenance["returncode"] = result.returncode
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"NetLogo returned {result.returncode}; see {output / 'run.log'}")
    checks = validate_outputs(output)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == provenance["source_sha256"]
    print(json.dumps({"output": str(output), "observation_wall_seconds": provenance["observation_wall_seconds"], "endpoint_checks": checks}, indent=2))


if __name__ == "__main__":
    main()
