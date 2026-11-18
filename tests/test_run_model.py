import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import run_model as runner


class RunnerTests(unittest.TestCase):
    def temporary(self):
        directory = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(directory.cleanup)
        return Path(directory.name)

    def batch(self):
        source = runner.ROOT / "outputs/lhs_256/runs.csv"
        with source.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        selected = [rows[5], rows[0], rows[1]]
        manifest = self.temporary() / "runs.csv"
        runner.write_csv(manifest, fields, selected)
        shutil.copyfile(source.with_name("parameters.csv"), manifest.with_name("parameters.csv"))
        return runner.build_plan("batch", runs_path=manifest, steps=52), selected, manifest

    def attempt(self, plan, output, records, index=1, omit=None, wrong_seed=False, version="7.0.3"):
        mapping = output / f"attempt_{index:03d}_runs.json"
        if not mapping.exists():
            runner.write_json(mapping, {"fingerprint": plan["fingerprint"],
                                        "run_ids": [r["run_id"] for r in plan["runs"]]})
        ids = runner.read_json(mapping)["run_ids"]
        by_id = {r["run_id"]: r for r in plan["runs"]}
        names = list(plan["runs"][0]["parameters"])
        metrics = [r for r in plan["config"]["metrics"].values() if r != omit]
        path = output / f"attempt_{index:03d}.csv"
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream, quoting=csv.QUOTE_ALL)
            writer.writerow([f"BehaviorSpace results (NetLogo {version})"])
            writer.writerow(["example metadata"])
            writer.writerow(["[run number]", *names, "random-seed", "[step]", *metrics])
            for number, ticks, invalid in records:
                row = by_id[ids[number - 1]]
                values = [ticks if metric == "ticks" else 1 for metric in metrics]
                if invalid is not None:
                    values[-1] = invalid
                writer.writerow([number, *(row["parameters"][n] for n in names),
                                 row["model_seed"] + int(wrong_seed), ticks, *values])
        return path

    def test_base_profile_and_model_defaults(self):
        plan = runner.build_plan("base")
        self.assertEqual(plan["model_version"], "NetLogo 7.0.3")
        self.assertEqual(plan["steps"], 52)
        self.assertEqual(len(plan["runs"]), 1)
        values = plan["runs"][0]["parameters"]
        for name, value in {"n-households": 2000, "n-poles": 100, "pole-connection-limit": 5,
                            "formal-connection-limit": 5, "informal-sd-limit": 4,
                            "hookon-limit": 3, "formal-connect-fee": 625,
                            "enforcement-freq": 110}.items():
            self.assertEqual(values[name], value)

    def test_aliases_and_category_mapping(self):
        config = runner.read_json(runner.DEFAULT_CONFIG)
        _, defaults, choices = runner.model_defaults(runner.ROOT / config["model"])
        for label, native in config["category_values"]["blackouts-attitude"].items():
            actual = runner.resolve_parameters({"init-trust-kplc": 25, "init-trust-ipd": 75,
                                                "blackouts-attitude": label}, defaults, choices, config)
            self.assertEqual(actual["init-attitude-kplc"], 25)
            self.assertEqual(actual["init-attitude-ipd"], 75)
            self.assertEqual(actual["blackouts-attitude"], native)
            self.assertNotIn("init-trust-kplc", actual)
        for overrides in ({"unknown": 1}, {"blackouts-attitude": "unknown"},
                          {"init-trust-kplc": 25, "init-attitude-kplc": 25},
                          {"enforcement-number": 101}, {"enforcement-freq": 0},
                          {"n-households": 10.5}, {"min-income": float("nan")}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                runner.resolve_parameters(overrides, defaults, choices, config)

    def test_lhs_rows_are_kept_together(self):
        plan, source, _ = self.batch()
        self.assertEqual(len(plan["runs"]), 3)
        self.assertEqual([r["run_id"] for r in plan["runs"]], [6, 1, 2])
        for row, original in zip(plan["runs"], source):
            for name in runner.IDS:
                self.assertEqual(row[name], int(original[name]))
            self.assertEqual(row["parameters"]["n-households"], int(original["n-households"]))
            self.assertEqual(row["parameters"]["init-attitude-kplc"], float(original["init-trust-kplc"]))
            self.assertEqual(row["parameters"]["formal-connect-fee"], 625)
            self.assertEqual(row["parameters"]["hookon-limit"], 3)

    def test_xml_has_one_explicit_combination_per_run(self):
        plan, _, _ = self.batch()
        experiment = ET.fromstring(runner.experiment_xml(plan, plan["runs"])).find("experiment")
        self.assertEqual(experiment.get("repetitions"), "1")
        self.assertEqual(experiment.get("timeLimit"), "52")
        self.assertEqual(experiment.get("runMetricsEveryStep"), "false")
        self.assertEqual(len(experiment.findall("metrics/metric")), len(plan["config"]["metrics"]))
        combinations = experiment.findall("subExperiments/subExperiment")
        self.assertEqual(len(combinations), len(plan["runs"]))
        for sub, row in zip(combinations, plan["runs"]):
            values = {}
            for parameter in sub:
                self.assertEqual(len(parameter), 1)
                values[parameter.get("variable")] = json.loads(parameter[0].get("value"))
            self.assertEqual(values, {**row["parameters"], "random-seed": row["model_seed"]})

    def test_preparation_and_resume_protect_existing_work(self):
        plan = runner.build_plan("base")
        output = runner.prepare(plan, self.temporary() / "run")
        self.assertEqual(runner.digest(output / "model.nlogox"), plan["model_sha256"])
        with self.assertRaises(FileExistsError):
            runner.prepare(plan, output)
        self.assertEqual(runner.prepare(plan, output, resume=True), output)
        with self.assertRaises(ValueError):
            runner.prepare(runner.build_plan("base", steps=2), output, resume=True)
        (output / "model.nlogox").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            runner.prepare(plan, output, resume=True)

    def test_resume_rejects_changed_manifest_or_configuration(self):
        plan, source, manifest = self.batch()
        output = runner.prepare(plan, self.temporary() / "run")
        source[0]["model_seed"] = str(int(source[0]["model_seed"]) + 1)
        runner.write_csv(manifest, source[0].keys(), source)
        changed = runner.build_plan("batch", runs_path=manifest, steps=52)
        with self.assertRaises(ValueError):
            runner.prepare(changed, output, resume=True)
        base = runner.build_plan("base")
        output = runner.prepare(base, self.temporary() / "base")
        config = runner.read_json(runner.DEFAULT_CONFIG)
        config["category_values"]["blackouts-attitude"]["a"] = "hurt-both-providers"
        path = self.temporary() / "model.json"
        runner.write_json(path, config)
        with self.assertRaises(ValueError):
            runner.prepare(runner.build_plan("base", config_path=path), output, resume=True)

    def test_parallel_result_order_maps_to_original_ids(self):
        plan, _, _ = self.batch()
        output = self.temporary()
        self.attempt(plan, output, [(2, 52, None), (1, 52, None)])
        self.assertEqual(set(runner.completed_runs(plan, output)), {6, 1})

    def test_partial_and_invalid_results_remain_pending(self):
        plan, _, _ = self.batch()
        for invalid in ("nan", "inf", "-inf", ""):
            with self.subTest(invalid=invalid):
                output = self.temporary()
                raw = self.attempt(plan, output, [(1, 52, None), (2, 51, None), (3, 52, invalid)])
                with raw.open("a", encoding="utf-8") as stream:
                    stream.write('"3","unfinished')
                self.assertEqual(set(runner.completed_runs(plan, output)), {6})

    def test_duplicate_results_and_wrong_inputs_are_rejected(self):
        plan, _, _ = self.batch()
        for kwargs in ({}, {"wrong_seed": True}, {"omit": "ticks"}, {"version": "7.0.4"}):
            with self.subTest(kwargs=kwargs):
                output = self.temporary()
                self.attempt(plan, output, [(1, 52, None), (1, 52, None)], **kwargs)
                with self.assertRaises(ValueError):
                    runner.completed_runs(plan, output)

    def test_truncated_final_value_is_not_counted_as_complete(self):
        plan, _, _ = self.batch()
        output = self.temporary()
        raw = self.attempt(plan, output, [(1, 52, None), (2, 52, None)])
        # Keep all columns but remove the last value's closing quote and newline.
        raw.write_bytes(raw.read_bytes()[:-3])
        self.assertEqual(set(runner.completed_runs(plan, output)), {6})

    def test_failed_batch_resumes_only_unfinished_runs(self):
        plan, _, _ = self.batch()
        output = runner.prepare(plan, self.temporary() / "run")
        def first_attempt(*args, **kwargs):
            self.attempt(plan, output, [(1, 52, None)])
            return subprocess.CompletedProcess(args[0], 1)
        with patch.object(runner.subprocess, "run", side_effect=first_attempt):
            with self.assertRaises(RuntimeError):
                runner.execute(plan, output, Path("fake_netlogo"))
        self.assertEqual(set(runner.completed_runs(plan, output)), {6})
        def second_attempt(*args, **kwargs):
            self.attempt(plan, output, [(2, 52, None), (1, 52, None)], index=2)
            return subprocess.CompletedProcess(args[0], 0)
        with patch.object(runner.subprocess, "run", side_effect=second_attempt):
            self.assertEqual(runner.execute(plan, output, Path("fake_netlogo")), 3)
        self.assertEqual(runner.read_json(output / "attempt_002_runs.json")["run_ids"], [1, 2])
        with patch.object(runner.subprocess, "run", side_effect=AssertionError("Already done")):
            self.assertEqual(runner.execute(plan, output, Path("fake_netlogo")), 3)
        with (output / "results.csv").open(newline="") as stream:
            self.assertEqual([int(r["run_id"]) for r in csv.DictReader(stream)], [6, 1, 2])

    def test_invalid_settings_and_manifest(self):
        for steps in (0, -1, 1481, True):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                runner.build_plan("base", steps=steps)
        _, rows, path = self.batch()
        for changed in ({"model_seed": "-1"}, {"n-households": "10.5"},
                        {"blackouts-attitude": "unknown"}, {"min-income": "nan"}):
            raw = {**rows[0], **changed}
            runner.write_csv(path, raw.keys(), [raw])
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                runner.read_runs(path)
        with self.assertRaises(FileNotFoundError):
            runner.netlogo_launcher(self.temporary())

    def test_cli_prepares_without_netlogo(self):
        output = self.temporary() / "run"
        command = [sys.executable, str(Path(runner.__file__)), "batch", "--limit", "2",
                   "--steps", "2", "--prepare-only", "--output", str(output),
                   "--netlogo-home", str(output / "not_installed")]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(runner.read_json(output / "plan.json")["runs"]), 2)
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
