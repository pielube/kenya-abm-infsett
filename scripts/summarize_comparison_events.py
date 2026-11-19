"""Compare observed weekly status changes and summarize revised decision logs.

Uses retained seed-42 data only; no NetLogo runs or source changes. A status
change is not necessarily a voluntary provider switch. Original data resolve
adjacent weekly states, while revised events also resolve within-week changes.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATES = {"f": "formal_households", "i": "informal_households", "n": "unconnected_households"}


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rate(count, total):
    return count / total * 100 if total else 0.0


def summarize(output):
    original_transitions = ROOT / "results/base/data/transitions.csv"
    original_aggregate = ROOT / "results/base/data/aggregate.csv"
    revised_log = ROOT / "results/attitude_trust_revision/52_ticks/decisions.csv"
    revised_trajectory = ROOT / "results/attitude_trust_revision/52_ticks/trajectory.csv"
    validation_path = ROOT / "results/attitude_trust_revision/event_validation.json"
    original = {int(row["tick"]): row for row in read_csv(original_aggregate)}
    revised = {int(float(row["ticks"])): row for row in read_csv(revised_trajectory)}
    horizon = max(revised)
    population = int(float(revised[0]["households"]))
    assert horizon == 52 and population == 2000
    assert sorted(revised) == list(range(horizon + 1))

    original_by_week = defaultdict(list)
    for row in read_csv(original_transitions):
        tick = int(row["tick"])
        if 1 <= tick <= horizon:
            original_by_week[tick].append(row)

    # Each group records first pre-state, final post-state and all status changes.
    grouped = {}
    last_state, inferred_initial = {}, {}
    kind_counts, attempts, successes, reason_counts = Counter(), Counter(), Counter(), Counter()
    events = 0
    previous_tick = -1
    with revised_log.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            events += 1
            assert int(row["event_id"]) == events
            tick, household = int(row["decision_tick"]), int(row["household_id"])
            assert 0 <= tick < horizon and tick >= previous_tick
            previous_tick = tick
            before, after = row["status_before"], row["status_after"]
            assert before in STATES and after in STATES
            if household in last_state:
                assert last_state[household] == before, (events, household, last_state[household], before)
            inferred_initial.setdefault(household, before)
            last_state[household] = after
            record = grouped.setdefault((tick + 1, household), [before, after, 0])
            record[1] = after
            record[2] += int(before != after)
            kind = row["event_kind"]
            kind_counts[kind] += 1
            attempts[kind] += int(row["attempted"] == "true")
            successes[kind] += int(row["success"] == "true")
            reason_counts[row["reason"]] += 1

    reference = json.loads(validation_path.read_text(encoding="utf-8"))
    assert reference["events"] == events
    assert dict(kind_counts) == reference["by_kind"]
    assert dict(attempts) == reference["attempted_by_kind"]
    assert dict(successes) == reference["successful_by_kind"]
    assert dict(reason_counts) == reference["by_reason"]
    assert len(inferred_initial) == population
    initial_counts = Counter(inferred_initial.values())
    for state, column in STATES.items():
        assert initial_counts[state] == int(float(revised[0][column]))

    grouped_by_week = defaultdict(list)
    for (tick, household), record in grouped.items():
        grouped_by_week[tick].append(record)

    rows = []
    for tick in range(1, horizon + 1):
        transition_rows = original_by_week[tick]
        assert len(transition_rows) == 9
        assert sum(int(row["households"]) for row in transition_rows) == population
        for state, column in STATES.items():
            origin = sum(int(row["households"]) for row in transition_rows if row["from_status"] == state)
            destination = sum(int(row["households"]) for row in transition_rows if row["to_status"] == state)
            assert origin == int(float(original[tick - 1][column]))
            assert destination == int(float(original[tick][column]))
            net_change = sum(int(after == state) - int(before == state) for before, after, _ in grouped_by_week[tick])
            expected = int(float(revised[tick][column])) - int(float(revised[tick - 1][column]))
            assert net_change == expected, (tick, state, net_change, expected)
        original_changed = sum(int(row["households"]) for row in transition_rows if row["from_status"] != row["to_status"])
        groups = grouped_by_week[tick]
        revised_changed = sum(before != after for before, after, _ in groups)
        change_events = sum(changes for _, _, changes in groups)
        touched = sum(changes > 0 for _, _, changes in groups)
        reversals = sum(changes > 0 and before == after for before, after, changes in groups)
        rows.append({
            "tick": tick, "households": population,
            "original_net_changed_households": original_changed,
            "original_net_change_pct": rate(original_changed, population),
            "revised_net_changed_households": revised_changed,
            "revised_net_change_pct": rate(revised_changed, population),
            "revised_status_change_events": change_events,
            "revised_households_with_changes": touched,
            "revised_within_week_return_to_start": reversals,
            "revised_additional_intermediate_changes": change_events - revised_changed,
        })

    funnel = []
    for kind in ["voluntary-choice", "access-attempt"]:
        funnel.append({
            "event_kind": kind, "evaluated": kind_counts[kind], "attempted": attempts[kind],
            "successful": successes[kind], "blocked": attempts[kind] - successes[kind],
            "not_attempted": kind_counts[kind] - attempts[kind],
            "attempt_pct_of_evaluated": rate(attempts[kind], kind_counts[kind]),
            "success_pct_of_attempted": rate(successes[kind], attempts[kind]),
        })
    forced_reasons = ["host-loss-voluntary-switch", "enforcement", "nonpayment-kplc", "nonpayment-ipd", "host-loss-nonpayment"]
    forced = [{"reason": reason, "events": reason_counts[reason]} for reason in forced_reasons]
    assert sum(row["events"] for row in forced) == kind_counts["forced-disconnection"]
    original_changes = sum(row["original_net_changed_households"] for row in rows)
    revised_changes = sum(row["revised_net_changed_households"] for row in rows)
    changed_events = sum(row["revised_status_change_events"] for row in rows)
    assert changed_events == sum(successes.values())
    summary = {
        "seed": 42, "realizations": 1, "weeks": horizon, "households": population,
        "household_week_pairs": horizon * population,
        "original_observed_net_status_changes": original_changes,
        "revised_observed_net_status_changes": revised_changes,
        "original_mean_weekly_status_change_pct": rate(original_changes, horizon * population),
        "revised_mean_weekly_status_change_pct": rate(revised_changes, horizon * population),
        "revised_status_change_events": changed_events,
        "revised_within_week_return_to_start_household_weeks": sum(row["revised_within_week_return_to_start"] for row in rows),
        "revised_additional_intermediate_status_changes": changed_events - revised_changes,
        "evaluated_events": events,
        "logging_funnel": funnel,
        "forced_disconnections": forced,
        "checks": ["Consecutive event IDs and ordered ticks", "Every household's pre-state equals its preceding post-state", "Event counts match retained validation", "All 2000 inferred initial household states match setup totals", "Original transition margins match adjacent aggregate states", "Revised event net flows match adjacent aggregate states at every week", "All revised status-changing events agree with successful event totals"],
        "limits": [
            "One seed-42 realization with several model changes combined; differences do not identify individual mechanism effects.",
            "Adjacent-week status changes include access and forced losses, not only voluntary provider switching.",
            "Original data do not identify corresponding voluntary/forced event counts; absent original categories must not be plotted as zero.",
            "Statuses f/i/n omit changes between informal service drops and hook-ons.",
            "Lower churn is an outcome difference, not evidence of improved empirical realism or household welfare.",
        ],
    }
    inputs = [original_transitions, original_aggregate, revised_log, revised_trajectory, validation_path]
    provenance = {
        "script": "scripts/summarize_comparison_events.py", "script_sha256": digest(Path(__file__)),
        "inputs": [{"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)} for path in inputs],
        "alignment": "Original transition tick t compares setup/observation t-1 to t; revised decision_tick t-1 events are pooled to completed observation tick t.",
        "inference": "For each household-week, compare its first logged pre-state to its last logged post-state. A household with no logged event has no recorded state change. The event completeness assumption is checked against aggregate flows at every week and all per-household event sequences.",
    }
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "weekly_churn.csv", rows)
    write_csv(output / "logging_funnel.csv", funnel)
    write_csv(output / "forced_disconnections.csv", forced)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/model_comparison/events")
    args = parser.parse_args()
    result = summarize(args.output.resolve())
    print(json.dumps({"output": str(args.output), "validation": "passed", "original_mean_weekly_status_change_pct": result["original_mean_weekly_status_change_pct"], "revised_mean_weekly_status_change_pct": result["revised_mean_weekly_status_change_pct"], "revised_status_change_events": result["revised_status_change_events"], "revised_net_status_changes": result["revised_observed_net_status_changes"]}, indent=2))


if __name__ == "__main__":
    main()
