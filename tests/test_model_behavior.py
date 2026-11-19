"""Behavioral contracts executed by the real NetLogo engine when available.

All fixtures share one fresh engine launch. They operate on a private model copy
and never change the supplied model or the archived baseline results.
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import run_model


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/kenya_informal_settlements.nlogox"


CONTRACT_PROCEDURES = r'''

to validation-record [case-name passed details]
  file-open __RESULTS_FILE__
  file-print csv:to-row (list case-name passed details)
  file-close
end

to validation-run-contracts
  validation-choice-contracts
  validation-experience-contracts
  validation-base-settings
  random-seed 42
  setup
  let radius max (list hookon-limit r1 r2)
  let incorrect count houses with [
    nearby-houses != (other houses with [distance myself <= radius])
  ]
  validation-record "neighborhoods_exact" (incorrect = 0) incorrect
  validation-logging-contracts
  validation-forced-contracts
end

to validation-base-settings
  __BASE_SETTINGS__
end

to validation-choice-contracts
  set choice-switching-inertia 2.2
  set choice-cost-sensitivity 1
  set choice-attitude-weight 1
  let price-monotone true
  let bounded true
  foreach [false true] [current-positive ->
    foreach [false true] [alternative-positive ->
      let previous -1
      foreach [1000 750 500 250 0] [alternative-cost ->
        let chance provider-switch-probability 500 alternative-cost current-positive alternative-positive 100
        if chance <= previous [set price-monotone false]
        if chance < 0 or chance > 100 [set bounded false]
        set previous chance
      ]
    ]
  ]
  validation-record "choice_price_monotone" price-monotone "All four attitude combinations"
  validation-record "choice_probability_bounds" bounded "All regular price/attitude combinations"

  let attitudes-monotone true
  foreach [0 500 1000] [alternative-cost ->
    foreach [false true] [current-positive ->
      if (provider-switch-probability 500 alternative-cost current-positive true 100)
        <= (provider-switch-probability 500 alternative-cost current-positive false 100)
        [set attitudes-monotone false]
    ]
    foreach [false true] [alternative-positive ->
      if (provider-switch-probability 500 alternative-cost true alternative-positive 100)
        >= (provider-switch-probability 500 alternative-cost false alternative-positive 100)
        [set attitudes-monotone false]
    ]
  ]
  validation-record "choice_attitudes_monotone" attitudes-monotone "Current approval discourages leaving; alternative approval encourages it"

  let tie-positive provider-switch-probability 500 500 true true 100
  let tie-negative provider-switch-probability 500 500 false false 100
  validation-record "choice_equal_attitudes_equal_probability" (abs (tie-positive - tie-negative) < 1.0E-12) (list tie-positive tie-negative)
  let small-saving provider-switch-probability 500 490 false false 100
  let large-saving provider-switch-probability 500 400 false false 100
  validation-record "choice_uses_cost_magnitude" (large-saving > small-saving) (list small-saving large-saving)
  let low-budget provider-switch-probability 500 400 false false 50
  let high-budget provider-switch-probability 500 400 false false 500
  validation-record "choice_cost_relative_to_budget" (low-budget > high-budget) (list low-budget high-budget)

  let extreme-low provider-switch-probability 0 1.0E300 false true 0
  let extreme-high provider-switch-probability 1.0E300 0 true false 0
  validation-record "choice_extreme_inputs_finite" (extreme-low >= 0 and extreme-low <= 100 and extreme-high >= 0 and extreme-high <= 100) (list extreme-low extreme-high)
  set choice-cost-sensitivity 0
  set choice-attitude-weight 0
  let insensitive-a provider-switch-probability 0 1000 false true 100
  let insensitive-b provider-switch-probability 1000 0 true false 100
  validation-record "choice_zero_sensitivities" (abs (insensitive-a - insensitive-b) < 1.0E-12) (list insensitive-a insensitive-b)
end

to validation-small-network
  clear-all
  validation-base-settings
  reset-ticks
  set informal-connection-capacity 13
  set formal-connect-fee 625
  set min-informal-fee 200
  set max-informal-fee 500
  set blackouts-attitude "only-hurt-kplc"
  set a-switch-blackout 0
  set a-switch-demand 0
  set a-switch-debt 0
  set a-switch-satisfaction 0
  set a-switch-safety 0
  set a-switch-safety-other 0
  set incidents-multiplier 0
  set enforcement-number 0
  set enforcement-freq 110
  set choice-switching-inertia 1000
  set choice-cost-sensitivity 0
  set choice-attitude-weight 0
  create-poles 1 [
    setxy 0 0
    set pole-capacity 100
    set pole-demand 0
    set pole-usage 0
    set pole-overloaded false
  ]
  create-houses 3 [
    setxy who 0
    set income 100000
    set HH-budget income
    set demand 80
    set tariff 23
    set desired-max-expense 100000
    set informal-flat-fee 200
    set installments-remaining 0
    set connection-status "i"
    set attitude-kplc true
    set attitude-ipd true
    set issues-this-tick false
    set switched-this-tick false
    decision-log-reset-issues
  ]
  ask houses [set nearby-houses other houses with [distance myself <= max (list hookon-limit r1 r2)]]
  ask house 1 [set connection-status "f" set demand 16]
  ask pole 0 [
    create-formal-connection-to house 1 [set overloaded false]
    create-informal-sd-to house 3 [set overloaded false]
  ]
  ask house 1 [create-informal-hookon-to house 2 [set overloaded false]]
end

to validation-experience-contracts
  validation-small-network
  blackouts
  per-week
  let first-load [pole-demand] of pole 0
  let first-delivered [pole-usage] of pole 0
  validation-record "informal_cap_both_link_types" (first-load = 30 and first-delivered = 30) (list first-load first-delivered)
  repeat 3 [blackouts per-week]
  validation-record "weekly_load_does_not_accumulate" ([pole-demand] of pole 0 = 30 and [pole-usage] of pole 0 = 30) (list [pole-demand] of pole 0 [pole-usage] of pole 0)

  ask pole 0 [set pole-capacity 20]
  let persistent true
  repeat 3 [
    blackouts
    per-week
    if [pole-demand] of pole 0 != 30 or [pole-overloaded] of pole 0 != true or [pole-usage] of pole 0 != 0 [set persistent false]
  ]
  validation-record "sustained_overload_has_no_phantom_recovery" persistent (list [pole-demand] of pole 0 [pole-usage] of pole 0)
  validation-record "blackout_propagates_to_hookons" (all? formal-connections [overloaded = true] and all? informal-sds [overloaded = true] and all? informal-hookons [overloaded = true]) "All supplying links flagged"

  ask houses with [connection-status = "i"] [set demand 8]
  blackouts
  per-week
  validation-record "recovery_uses_current_load" ([pole-demand] of pole 0 = 8 and [pole-usage] of pole 0 = 8 and [pole-overloaded] of pole 0 = false) (list [pole-demand] of pole 0 [pole-usage] of pole 0)

  ask house 1 [set demand 400 set HH-budget 46]
  blackouts
  per-week
  validation-record "formal_load_obeys_cash_constraint" ([pole-demand] of pole 0 = 6 and [pole-usage] of pole 0 = 6 and [HH-budget] of house 1 = 0) (list [pole-demand] of pole 0 [pole-usage] of pole 0)

  validation-small-network
  set formal-connect-fee 90
  ask house 1 [set income 100 set tariff 10 set installments-remaining 1]
  ask houses with [connection-status = "i"] [set demand 8]
  go
  validation-record "billing_precedes_load_classification" ([pole-demand] of pole 0 = 5 and [pole-usage] of pole 0 = 5) (list [pole-demand] of pole 0 [pole-usage] of pole 0)
end

to-report validation-state
  let household-state map [h -> [(list who xcor ycor income demand connection-status
    HH-budget expense debt spend-ratio switchcount installments-remaining
    times-installment-not-paid times-ipd-not-paid informal-flat-fee
    attitude-kplc attitude-ipd weeks-continuous-informal cant-afford
    issues-this-tick switched-this-tick)] of h] sort houses
  let pole-state map [p -> [(list who pole-demand pole-usage pole-overloaded
    number-formal-connections number-informal-connections)] of p] sort poles
  let link-state map [connection -> [(list [who] of end1 [who] of end2
    validation-link-kind (ifelse-value (breed = pole-connections) [false] [overloaded]))] of connection] sort links
  report (list household-state pole-state link-state)
end

to-report validation-link-kind
  if breed = formal-connections [report "formal"]
  if breed = informal-sds [report "service_drop"]
  if breed = informal-hookons [report "hookon"]
  report "pole"
end

to validation-logging-contracts
  validation-base-settings
  random-seed 42
  setup
  repeat 52 [go]
  let unlogged-state validation-state
  let unlogged-next random-float 1

  validation-base-settings
  random-seed 42
  setup
  decision-log-start __TRAJECTORY_FILE__
  repeat 52 [go]
  let logged-state validation-state
  let logged-next random-float 1
  decision-log-stop
  validation-record "logging_state_invariant" (logged-state = unlogged-state) "All dynamic household, pole and link states after 52 weeks"
  validation-record "logging_random_stream_invariant" (logged-next = unlogged-next) (list unlogged-next logged-next)
end

to validation-forced-contracts
  validation-small-network
  decision-log-start __FORCED_FILE__
  ask house 1 [set times-installment-not-paid 6]
  add-drop-connections
  decision-log-stop

  validation-small-network
  decision-log-start __IPD_FILE__
  ask house 3 [set times-ipd-not-paid 1]
  set informal-sd-limit 0
  set hookon-limit 0
  random-seed 901
  repeat 100 [if count-disconnect-ipd = 0 [add-drop-connections]]
  validation-record "informal_nonpayment_fixture_disconnects" (count-disconnect-ipd = 1) count-disconnect-ipd
  decision-log-stop

  validation-small-network
  decision-log-start __ENFORCEMENT_FILE__
  set enforcement-number 1
  enforcement-actions
  decision-log-stop

  validation-small-network
  decision-log-start __HOST_FILE__
  ask house 1 [switch-to-informal]
  decision-log-stop
end
'''


class ModelBehaviorTests(unittest.TestCase):
    """Run contract fixtures once, then expose failures as individual tests."""

    @classmethod
    def setUpClass(cls):
        try:
            launcher = run_model.netlogo_launcher()
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc)) from exc
        cls.temporary = tempfile.TemporaryDirectory(prefix="kenya_abm_behavior_")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.output = Path(cls.temporary.name)
        root = ET.parse(MODEL).getroot()
        code = root.find("code")
        code.text += CONTRACT_PROCEDURES.replace(
            "__RESULTS_FILE__", json.dumps((cls.output / "contracts.csv").as_posix())
        ).replace("__TRAJECTORY_FILE__", json.dumps((cls.output / "trajectory.csv").as_posix())).replace(
            "__FORCED_FILE__", json.dumps((cls.output / "forced.csv").as_posix())
        ).replace("__IPD_FILE__", json.dumps((cls.output / "ipd.csv").as_posix())).replace(
            "__ENFORCEMENT_FILE__", json.dumps((cls.output / "enforcement.csv").as_posix())
        ).replace("__HOST_FILE__", json.dumps((cls.output / "host.csv").as_posix())).replace(
            "__BASE_SETTINGS__", "\n  ".join(
                f"set {name} {json.dumps(value)}"
                for name, value in run_model.read_json(ROOT / "experiments/base.json")["parameters"].items()
            )
        )
        widgets = root.find("widgets")
        for widget in list(widgets):
            if widget.tag in {"plot", "monitor", "button"}:
                widgets.remove(widget)
        ET.ElementTree(root).write(cls.output / "model.nlogox", encoding="utf-8", xml_declaration=True)
        for include in MODEL.parent.glob("*.nls"):
            shutil.copyfile(include, cls.output / include.name)
        experiments = ET.Element("experiments")
        experiment = ET.SubElement(experiments, "experiment", name="behavior_contracts",
                                   repetitions="1", sequentialRunOrder="true",
                                   runMetricsEveryStep="false", timeLimit="1")
        ET.SubElement(experiment, "setup").text = "validation-run-contracts"
        ET.SubElement(experiment, "go").text = "tick"
        metrics = ET.SubElement(experiment, "metrics")
        ET.SubElement(metrics, "metric").text = "ticks"
        ET.SubElement(ET.SubElement(experiment, "subExperiments"), "subExperiment")
        ET.ElementTree(experiments).write(cls.output / "experiment.xml", encoding="utf-8", xml_declaration=True)
        command = [str(launcher), "--headless", "--model", str(cls.output / "model.nlogox"),
                   "--setup-file", str(cls.output / "experiment.xml"), "--experiment", "behavior_contracts",
                   "--table", str(cls.output / "behavior.csv"), "--threads", "1"]
        result = subprocess.run(command, cwd=cls.output, capture_output=True, text=True, timeout=180,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        path = cls.output / "contracts.csv"
        if result.returncode or not path.exists():
            raise AssertionError(f"NetLogo behavioral fixtures failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
        with path.open(newline="", encoding="utf-8-sig") as stream:
            cls.contracts = {row[0]: (row[1] == "true", row[2]) for row in csv.reader(stream)}
        cls.engine_output = result.stdout + result.stderr + (cls.output / "behavior.csv").read_text(encoding="utf-8-sig")[:12000]

    def contract(self, name):
        self.assertIn(name, self.contracts, self.engine_output)
        passed, details = self.contracts[name]
        self.assertTrue(passed, f"{name}: {details}")

    def test_choice_monotonicity_and_magnitude(self):
        for name in ["choice_price_monotone", "choice_attitudes_monotone", "choice_equal_attitudes_equal_probability",
                     "choice_uses_cost_magnitude", "choice_cost_relative_to_budget"]:
            with self.subTest(contract=name):
                self.contract(name)

    def test_choice_numerical_boundaries(self):
        for name in ["choice_probability_bounds", "choice_extreme_inputs_finite", "choice_zero_sensitivities"]:
            with self.subTest(contract=name):
                self.contract(name)

    def test_neighborhood_cache_matches_final_positions(self):
        self.contract("neighborhoods_exact")

    def test_weekly_load_and_reliability(self):
        for name in ["informal_cap_both_link_types", "weekly_load_does_not_accumulate",
                     "sustained_overload_has_no_phantom_recovery", "blackout_propagates_to_hookons",
                     "recovery_uses_current_load", "formal_load_obeys_cash_constraint",
                     "billing_precedes_load_classification"]:
            with self.subTest(contract=name):
                self.contract(name)

    def test_logging_preserves_state_and_random_stream(self):
        self.contract("logging_state_invariant")
        self.contract("logging_random_stream_invariant")
        with (self.output / "trajectory.csv").open(newline="", encoding="utf-8-sig") as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(rows, "Enabled logging must contain actual decisions/events")
        self.assertEqual([int(row["event_id"]) for row in rows], list(range(1, len(rows) + 1)))
        for row in rows:
            self.assertIn(row["status_before"], {"f", "i", "n"})
            self.assertIn(row["status_after"], {"f", "i", "n"})
            self.assertIn(row["attitude_kplc_before"], {"true", "false"})
            self.assertIn(row["attitude_ipd_before"], {"true", "false"})
            self.assertGreaterEqual(float(row["income"]), 0)
            self.assertGreaterEqual(int(row["feasible_formal_sources"]), -1)
            self.assertGreaterEqual(int(row["feasible_informal_sources"]), -1)
            self.assertGreaterEqual(float(row["probability_pct"]), -1)
            self.assertLessEqual(float(row["probability_pct"]), 100)

    def test_forced_disconnection_causes_and_pre_event_state(self):
        self.contract("informal_nonpayment_fixture_disconnects")

        def records(filename):
            with (self.output / filename).open(newline="", encoding="utf-8-sig") as stream:
                return list(csv.DictReader(stream))

        formal = records("forced.csv")
        missed = [row for row in formal if row["reason"] == "nonpayment-kplc"]
        self.assertEqual(len(missed), 1)
        self.assertEqual((missed[0]["status_before"], missed[0]["status_after"]), ("f", "n"))
        self.assertEqual(missed[0]["source_id_before"], "0")
        self.assertEqual(missed[0]["source_id_after"], "-1")
        dependents = [row for row in formal if row["reason"] == "host-loss-nonpayment"]
        self.assertEqual(len(dependents), 1)
        self.assertEqual((dependents[0]["access_before"], dependents[0]["access_after"]), ("hookon", "unconnected"))
        self.assertEqual(dependents[0]["source_pole_id_before"], "0")
        self.assertEqual(dependents[0]["source_pole_id_after"], "-1")

        ipd = [row for row in records("ipd.csv") if row["reason"] == "nonpayment-ipd"]
        self.assertEqual(len(ipd), 1)
        self.assertEqual((ipd[0]["status_before"], ipd[0]["status_after"]), ("i", "n"))

        enforcement = records("enforcement.csv")
        self.assertEqual(len(enforcement), 2)
        self.assertEqual({row["reason"] for row in enforcement}, {"enforcement"})
        self.assertEqual({row["event_kind"] for row in enforcement}, {"forced-disconnection"})
        self.assertEqual({row["status_after"] for row in enforcement}, {"n"})

        host = records("host.csv")
        self.assertEqual(len(host), 1)
        self.assertEqual(host[0]["reason"], "host-loss-voluntary-switch")
        self.assertEqual((host[0]["access_before"], host[0]["access_after"]), ("hookon", "unconnected"))
        self.assertEqual(host[0]["source_pole_id_before"], "0")
        self.assertEqual(host[0]["source_pole_id_after"], "-1")


if __name__ == "__main__":
    unittest.main()
