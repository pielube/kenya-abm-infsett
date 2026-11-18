import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

import lhs


class LHSTests(unittest.TestCase):
    def setUp(self):
        self.parameters = lhs.load_parameters()
        self.active = [p for p in self.parameters if p.kind != "excluded"]

    def write_spec(self, path, **changes):
        row = dict(var="example", range="0 to 1", kind="continuous",
                   lower="0", upper="1", categories="", notes="")
        row.update(changes)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=row)
            writer.writeheader()
            writer.writerow(row)
        return path

    def read_csv(self, path):
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def test_default_specification(self):
        self.assertEqual(len(self.parameters), 35)
        self.assertEqual(len(self.active), 31)
        self.assertEqual({p.name for p in self.parameters if p.kind == "excluded"}, {
            "pole-connection-limit", "formal-connection-limit", "informal-sd-limit", "hookon-limit",
        })
        categorical = [p for p in self.active if p.kind == "categorical"]
        self.assertEqual([(p.name, p.categories) for p in categorical], [
            ("blackouts-attitude", ("a", "b", "c", "d")),
        ])

    def test_default_sampling_properties(self):
        rows, unit = lhs.sample_lhs(self.parameters)
        self.assertEqual(unit.shape, (256, 31))
        self.assertEqual(len(rows), 256)
        self.assertTrue(np.isfinite(unit).all())
        self.assertTrue(((unit >= 0) & (unit < 1)).all())
        np.testing.assert_array_equal(
            np.sort(np.floor(unit * 256).astype(int), axis=0),
            np.broadcast_to(np.arange(256)[:, None], (256, 31)),
        )
        self.assertEqual([row["sample_id"] for row in rows], list(range(1, 257)))
        for row in rows:
            self.assertEqual(set(row), {"sample_id", *(p.name for p in self.active)})
            for p in self.active:
                value = row[p.name]
                if p.kind == "categorical":
                    self.assertIn(value, p.categories)
                else:
                    self.assertTrue(np.isfinite(value))
                    self.assertGreaterEqual(value, p.lower)
                    self.assertLessEqual(value, p.upper)
                    if p.kind == "integer":
                        self.assertIsInstance(value, int)
        categories = [row["blackouts-attitude"] for row in rows]
        self.assertEqual([categories.count(c) for c in "abcd"], [64] * 4)

    def test_reproducibility_and_seed_effect(self):
        rows_a, unit_a = lhs.sample_lhs(self.parameters, samples=16, seed=7)
        rows_b, unit_b = lhs.sample_lhs(self.parameters, samples=16, seed=7)
        _, unit_c = lhs.sample_lhs(self.parameters, samples=16, seed=8)
        self.assertEqual(rows_a, rows_b)
        np.testing.assert_array_equal(unit_a, unit_b)
        self.assertFalse(np.array_equal(unit_a, unit_c))

    def test_integer_mapping_has_uniform_endpoint_probabilities(self):
        rows, _ = lhs.sample_lhs([lhs.Parameter("count", "integer", 0, 7)])
        self.assertEqual([sum(row["count"] == v for row in rows) for v in range(8)], [32] * 8)

    def test_invalid_parameter_definitions(self):
        p = lhs.Parameter("example", "continuous", 0, 1)
        cases = [[], [p, p], [replace(p, name="")], [replace(p, kind="unknown")],
                 [replace(p, lower=float("nan"))], [replace(p, upper=float("inf"))],
                 [replace(p, lower=1)], [replace(p, lower=2)],
                 [replace(p, kind="integer", lower=0.5)],
                 [replace(p, categories=("a", "b"))],
                 [lhs.Parameter("count", "integer", 0, 2**54)],
                 [lhs.Parameter("choice", "categorical")],
                 [lhs.Parameter("choice", "categorical", categories=("a", "a"))],
                 [lhs.Parameter("choice", "categorical", categories=("", "b"))],
                 [lhs.Parameter("choice", "categorical", lower=0, categories=("a",))],
                 [lhs.Parameter("unused", "excluded")],
                 [p, lhs.Parameter("unused", "excluded", lower=0)]]
        cases.extend([replace(p, name=name)] for name in lhs.RESERVED_NAMES)
        for parameters in cases:
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                lhs.sample_lhs(parameters, samples=8)

    def test_invalid_sampling_settings(self):
        for name, values in {"samples": (0, -1, 1.5, True), "seed": (-1, 1.5, True)}.items():
            for value in values:
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    lhs.sample_lhs(self.parameters, **{name: value})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            for replicates in (0, -1, 1.5, True):
                with self.subTest(replicates=replicates), self.assertRaises(ValueError):
                    lhs.create_experiment(lhs.DEFAULT_PARAMETERS, Path(temporary) / "new",
                                          replicates=replicates)

    def test_loader_rejects_malformed_csv(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            path = Path(temporary) / "parameters.csv"
            for changes in ({"var": "sample_id"}, {"lower": "nan"}, {"upper": "inf"},
                            {"lower": "not a number"}, {"lower": "2"}, {"kind": "unknown"},
                            {"kind": "integer", "lower": "0.5"},
                            {"kind": "categorical", "lower": "", "upper": "", "categories": "a||b"}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    lhs.load_parameters(self.write_spec(path, **changes))
            for contents in ("var,range\na,0 to 1\n", ",".join(lhs.PARAMETER_FIELDS) + "\na\n",
                             ",".join(lhs.PARAMETER_FIELDS) + "\na,b,c,d,e,f,g,h\n"):
                path.write_text(contents, encoding="utf-8")
                with self.subTest(contents=contents), self.assertRaises(ValueError):
                    lhs.load_parameters(path)

    def test_experiment_files_and_replications(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            output = Path(temporary) / "experiment"
            metadata = lhs.create_experiment(lhs.DEFAULT_PARAMETERS, output, 16, 7, 3)
            self.assertEqual({p.name for p in output.iterdir()}, {
                "design.csv", "unit_samples.csv", "runs.csv", "metadata.json", "parameters.csv",
            })
            self.assertEqual(metadata, json.loads((output / "metadata.json").read_text()))
            for key, value in {"samples": 16, "seed": 7, "replicates": 3,
                               "dimensions": 31, "total_runs": 48}.items():
                self.assertEqual(metadata[key], value)
            self.assertEqual(lhs.load_parameters(output / "parameters.csv"), self.parameters)
            self.assertEqual(metadata["parameter_sha256"],
                             hashlib.sha256((output / "parameters.csv").read_bytes()).hexdigest())
            design = self.read_csv(output / "design.csv")
            runs = self.read_csv(output / "runs.csv")
            self.assertEqual(len(design), 16)
            self.assertEqual(len(self.read_csv(output / "unit_samples.csv")), 16)
            self.assertEqual(len(runs), 48)
            self.assertEqual([int(r["run_id"]) for r in runs], list(range(1, 49)))
            seeds = [int(row["model_seed"]) for row in runs]
            self.assertEqual(len(set(seeds)), 48)
            self.assertTrue(all(0 <= seed < 2**31 for seed in seeds))
            for scenario in design:
                matches = [row for row in runs if row["sample_id"] == scenario["sample_id"]]
                self.assertEqual({int(row["replicate"]) for row in matches}, {1, 2, 3})
                for run in matches:
                    for p in self.active:
                        self.assertEqual(run[p.name], scenario[p.name])
            second = Path(temporary) / "repeated"
            lhs.create_experiment(lhs.DEFAULT_PARAMETERS, second, np.int64(16), np.int64(7), np.int64(3))
            for file in output.iterdir():
                self.assertEqual(file.read_bytes(), (second / file.name).read_bytes())
            third = Path(temporary) / "more_replicates"
            lhs.create_experiment(lhs.DEFAULT_PARAMETERS, third, 16, 7, 4)
            self.assertEqual((output / "design.csv").read_bytes(), (third / "design.csv").read_bytes())
            with self.assertRaises(FileExistsError):
                lhs.create_experiment(lhs.DEFAULT_PARAMETERS, output)

    def test_cli_success_and_clean_errors(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            output = root / "experiment"
            command = [sys.executable, str(Path(lhs.__file__).resolve()),
                       "--parameters", str(lhs.DEFAULT_PARAMETERS), "--samples", "16",
                       "--replicates", "2", "--seed", "7", "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(self.read_csv(output / "runs.csv")), 32)
            invalid_config = self.write_spec(root / "bad.csv", lower="nan")
            for args in (command, command + ["--samples", "0"],
                         command + ["--parameters", str(invalid_config)]):
                result = subprocess.run(args, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
