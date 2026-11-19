"""Summarize descriptive attitude/income associations in the saved base run.

This script reads existing observations only. It does not run or alter NetLogo.
Current attitudes and connection status evolve jointly, so the output does not
estimate an independent or causal effect of attitudes on provider choice.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
# These observations and their interpretation describe the original baseline.
ORIGINAL_MODEL = ROOT / "results/base/runs/52_ticks/model.nlogox"
ORIGINAL_BASE = ROOT / "experiments/original-base.json"


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentage(count, total):
    return 100 * count / total if total else None


def is_positive(row, provider):
    value = row[f"attitude_{provider}"]
    if value not in ("true", "false"):
        raise ValueError(f"Unexpected attitude value {value!r}")
    return value == "true"


def status_counts(rows):
    return {state: sum(row["status"] == state for row in rows) for state in ("f", "i", "n")}


def cost_comparison(rows):
    formal = sum(float(row["formal_next_month_cost"]) < float(row["informal_next_month_cost"]) for row in rows)
    informal = sum(float(row["informal_next_month_cost"]) < float(row["formal_next_month_cost"]) for row in rows)
    equal = sum(float(row["informal_next_month_cost"]) == float(row["formal_next_month_cost"]) for row in rows)
    assert formal + informal + equal == len(rows)
    return {"formal_strictly_cheaper": formal, "informal_strictly_cheaper": informal, "equal_predicted_cost": equal}


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "results/base/data")
    parser.add_argument("--output", type=Path, default=ROOT / "results/attitude_trust_review")
    args = parser.parse_args()
    data = args.data.resolve()
    output = args.output.resolve()
    rows = read_csv(data / "households.csv")
    initial = [row for row in rows if int(row["tick"]) == 0]
    at52 = [row for row in rows if int(row["tick"]) == 52]
    final = [row for row in rows if int(row["tick"]) == 1480]
    base_path = ORIGINAL_BASE
    base = json.loads(base_path.read_text(encoding="utf-8"))
    expected_n = base["parameters"]["n-households"]
    assert len(initial) == len(at52) == len(final) == expected_n
    assert expected_n % 5 == 0
    initial_by_id = {int(row["who"]): row for row in initial}
    final_by_id = {int(row["who"]): row for row in final}
    assert len(initial_by_id) == len(final_by_id) == expected_n
    assert initial_by_id.keys() == final_by_id.keys()
    for identity in initial_by_id:
        assert initial_by_id[identity]["income"] == final_by_id[identity]["income"]
        assert initial_by_id[identity]["demand"] == final_by_id[identity]["demand"]
    ordered = sorted(initial, key=lambda row: (float(row["income"]), int(row["who"])))
    group_size = expected_n // 5
    quintile_by_id = {int(row["who"]): rank // group_size + 1 for rank, row in enumerate(ordered)}
    monthly_capacity = 4 * base["parameters"]["informal-connection-capacity"]
    income_summary = []
    association = []
    for quintile in range(1, 6):
        group_initial = [row for row in initial if quintile_by_id[int(row["who"])] == quintile]
        group_final = [row for row in final if quintile_by_id[int(row["who"])] == quintile]
        assert len(group_initial) == len(group_final) == group_size
        comparisons = cost_comparison(group_final)
        record = {
            "income_quintile": quintile,
            "n_households": group_size,
            "initial_income_min": min(float(row["income"]) for row in group_initial),
            "initial_income_max": max(float(row["income"]) for row in group_initial),
            "median_monthly_income": median(float(row["income"]) for row in group_initial),
            "median_monthly_demand_kwh": median(float(row["demand"]) for row in group_initial),
            "informal_monthly_capacity_kwh": monthly_capacity,
            "n_demand_above_informal_capacity": sum(float(row["demand"]) > monthly_capacity for row in group_initial),
            "initial_formal_pct": percentage(status_counts(group_initial)["f"], group_size),
            "final_formal_pct": percentage(status_counts(group_final)["f"], group_size),
            "n_formal_strictly_cheaper_final": comparisons["formal_strictly_cheaper"],
            "n_equal_predicted_cost_final": comparisons["equal_predicted_cost"],
        }
        for provider in ("kplc", "ipd"):
            record[f"initial_positive_{provider}_pct"] = percentage(sum(is_positive(row, provider) for row in group_initial), group_size)
            record[f"final_positive_{provider}_pct"] = percentage(sum(is_positive(row, provider) for row in group_final), group_size)
            for positive in (False, True):
                subgroup = [row for row in group_final if is_positive(row, provider) == positive]
                counts = status_counts(subgroup)
                association.append({
                    "income_quintile": quintile,
                    "attitude_provider": provider,
                    "positive_attitude": int(positive),
                    "n_households": len(subgroup),
                    "n_formal": counts["f"],
                    "n_informal": counts["i"],
                    "n_unconnected": counts["n"],
                    "formal_pct": percentage(counts["f"], len(subgroup)),
                    "informal_pct": percentage(counts["i"], len(subgroup)),
                    "unconnected_pct": percentage(counts["n"], len(subgroup)),
                })
        income_summary.append(record)
    assert sum(row["n_households"] for row in income_summary) == expected_n
    for provider in ("kplc", "ipd"):
        subset = [row for row in association if row["attitude_provider"] == provider]
        assert sum(row["n_households"] for row in subset) == expected_n
        for state, label in [("f", "n_formal"), ("i", "n_informal"), ("n", "n_unconnected")]:
            assert sum(row[label] for row in subset) == status_counts(final)[state]
    for tick, retained, snapshot in [(52, "52_ticks", at52), (1480, "1480_ticks", final)]:
        reference = read_csv(ROOT / "results/base/runs" / retained / "results.csv")[0]
        assert int(float(reference["ticks"])) == tick
        counts = status_counts(snapshot)
        assert counts["f"] == int(float(reference["formal_households"]))
        assert counts["i"] == int(float(reference["informal_households"]))
        assert counts["n"] == int(float(reference["unconnected_households"]))
    aggregate = read_csv(data / "aggregate.csv")
    final_aggregate = next(row for row in aggregate if int(row["tick"]) == 1480)
    summary = {
        "seed": base["seed"],
        "realizations": 1,
        "households": expected_n,
        "household_snapshots": sorted({int(row["tick"]) for row in rows}),
        "household_rows": len(rows),
        "household_fields": len(rows[0]),
        "final_tick": 1480,
        "final_status_counts": status_counts(final),
        "minimum_realized_monthly_income": min(float(row["income"]) for row in initial),
        "maximum_initial_informal_fee": max(float(row["informal_fee"]) for row in initial),
        "formal_monthly_installment": base["parameters"]["formal-connect-fee"],
        "informal_monthly_capacity_kwh": monthly_capacity,
        "predicted_cost_comparison": {"0": cost_comparison(initial), "52": cost_comparison(at52), "1480": cost_comparison(final)},
        "cumulative_nonpayment_disconnects": {"kplc": int(float(final_aggregate["cumulative_nonpayment_disconnects_kplc"])), "ipd": int(float(final_aggregate["cumulative_nonpayment_disconnects_ipd"]))},
        "interpretation": "Descriptive within-realization associations, not independent or causal attitude effects. Final attitudes, expenses, remaining installments and connection states have evolved jointly.",
    }
    limits = [
        "One seed-42 realization; households interact and are not independent simulation replicates.",
        "Attitudes are Boolean flags and observed after the model go procedure; they may already reflect current-provider experience in that week.",
        "Income quintiles are fixed ranks of initial income; both income and demand remain fixed in this run.",
        "Controlling for income groups does not control for service history, spatial reach, available alternatives, connection history or income-linked demand.",
        "Within-income associations do not separate attitude-driven selection from experience-driven attitude changes.",
        "Predicted costs assume the model's full-demand tariff rule and remaining installment state; a cheaper alternative need not be feasible or deliver equivalent service.",
        "The informal cap comparison uses the nominal13kWh weekly cap times four; direct service drops and hook-ons do not apply this cap consistently in the model.",
        "Existing household observations are11 selected snapshots, not complete decision-level histories; issue reasons and prospective choice sets are not recorded.",
    ]
    input_paths = [data / "households.csv", data / "aggregate.csv", base_path, ORIGINAL_MODEL, ROOT / "results/base/runs/52_ticks/results.csv", ROOT / "results/base/runs/1480_ticks/results.csv"]
    provenance = {
        "analysis": "Existing-base descriptive attitude and income assessment",
        "model_role": "original-archived-base",
        "script": "scripts/assess_attitude_data.py",
        "script_sha256": digest(Path(__file__)),
        "inputs": [{"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path), "sha256": digest(path)} for path in input_paths],
        "seed": base["seed"],
        "model_sha256": digest(ORIGINAL_MODEL),
        "quintiles": "Five equal-size groups ordered by initial income, with household identifier as a deterministic tie-breaker.",
        "cost_comparisons": "Strict numeric less-than comparisons; equal-cost observations counted separately.",
        "limits": limits,
        "validation": {"group_totals": "passed", "fixed_income_and_demand": "passed", "tick52_and1480_status_counts_match_canonical_runs": "passed"},
    }
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "income_summary.csv", income_summary)
    write_csv(output / "within_income_association.csv", association)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "income_groups": len(income_summary), "association_rows": len(association), "validation": "passed"}))


if __name__ == "__main__":
    main()
