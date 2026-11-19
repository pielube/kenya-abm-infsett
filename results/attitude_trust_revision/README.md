# Revised model diagnostic runs

These runs implement priorities 1, 2 and 8: a monotone cost–attitude switching kernel, corrected neighborhood and weekly-load accounting, and decision-level logging. See the [revision guide](../../docs/model-revision.md) for the formula, parameter meanings, event schema and limits.

The original [base archive](../base/README.md) is retained. Both revised runs use the same seed 42 and begin with 995 formal and 1,005 unconnected households. This comparison combines the approved changes; it does not identify their separate contributions.

| Endpoint | Original formal | Revised formal | Original informal | Revised informal | Original unconnected | Revised unconnected |
| --- | --- | --- | --- | --- | --- | --- |
| 52 weeks | 578 | 206 | 1,254 | 1,599 | 168 | 195 |
| 1,480 weeks | 1,067 | 396 | 835 | 1,506 | 98 | 98 |

The three new weights are uncalibrated starting assumptions. These results demonstrate working code and changed dynamics, rather than improved empirical fit or validated estimates of attitude effects.

## Retained files

- [52-week results](52_ticks/results.csv), [weekly trajectory](52_ticks/trajectory.csv), and [decision/event log](52_ticks/decisions.csv).
- [1,480-week results](1480_ticks/results.csv) and [weekly trajectory](1480_ticks/trajectory.csv). Detailed logging was disabled for this longer run.
- [Original versus revised metrics](comparison.csv).
- [Event validation](event_validation.json) and [standard-runner equivalence](standard_runner_check.json).

Each run folder contains its model, local include, inputs, experiment definitions, raw engine output, named results, and provenance. Both logs are empty of engine errors. Runtime values in diagnostic provenance include observation/export overhead; the two jobs ran concurrently, so they are not comparable to the earlier isolated benchmarks.

## What the short-run log records

The log has 74,893 rows: 60,208 evaluated voluntary choices, 13,997 evaluated informal access attempts, and 688 forced disconnections. There are 3,878 voluntary switch attempts, of which 2,717 succeed; 3,491 access attempts produce 1,498 new connections. Forced losses comprise 623 dependent hook-ons losing their host through voluntary switching and 65 enforcement removals. No nonpayment disconnections occur in this seed-42 run.

These are distinct measures. A probability draw that does not select switching is retained as an evaluated decision. A selected switch can fail when no source is reachable. One household can have multiple events in a tick. Co-occurring issues are recorded without assigning an unsupported single causal explanation.

All voluntary probabilities reconstruct from logged costs, attitudes, reference spending and weights. Draws agree with attempts, successful targets agree with realized sources, and forced events are separately classified. The logged trajectory equals the first 52 weeks of the unlogged full run. The standard final-only runner also reproduces every short-run result cell.

## Reproduction

Use fresh output directories:

```powershell
python scripts/run_model_diagnostics.py --steps 52 --output outputs/base_revised_logged
python scripts/run_model_diagnostics.py --steps 1480 --no-log --output outputs/base_revised_full
```

The existing Boolean learning rules, full-income cash reset, and informal-only entry rule remain in this revision. The new event data support examining those mechanisms before further changes.
