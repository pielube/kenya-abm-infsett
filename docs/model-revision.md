# Revised switching and experience accounting

The working model on `attitude-trust-review` implements priorities 1, 2 and 8 from the attitude assessment: a coherent switching rule, corrected neighborhood and weekly-load accounting, and decision-level logging. The original model, runs, figures and source data remain under [results/base](../results/base/README.md). Those publication figures describe the original implementation, not this revision.

The revised base settings are [experiments/base.json](../experiments/base.json). A [52-week logged run](../results/attitude_trust_revision/52_ticks/results.csv) and a [1,480-week run](../results/attitude_trust_revision/1480_ticks/results.csv) demonstrate the combined changes. They use seed 42 and are diagnostics, not calibration or a separation of the effects of individual changes.

## Switching probability

Connected households still reconsider their provider when an issue occurs. A probability determines whether they attempt a switch; a reachable source is required for the attempt to succeed. The same rule applies in both directions:

```text
relative saving = (current monthly cost - alternative monthly cost)
                  / max(desired monthly spending, 1)
attitude difference = alternative positive flag - current positive flag
score = cost sensitivity × relative saving
        + attitude weight × attitude difference
        - switching inertia
probability = 100 / (1 + exp(-score))
```

Positive flags map to 1 and negative flags to 0. The denominator uses the existing desired-spending reference; it does not introduce a new disposable-income budget. Stable logistic evaluation avoids exponential overflow for extreme scores.

| New input | Default | Interpretation |
| --- | --- | --- |
| `choice-cost-sensitivity` | 1 | Response to savings measured in units of desired monthly spending |
| `choice-attitude-weight` | 1 | Response to the difference in provider approval |
| `choice-switching-inertia` | 2.2 | Baseline reluctance to change provider |

All three inputs must be nonnegative. These are explicit, **uncalibrated starting assumptions**. At equal costs, the probabilities are approximately 10.0% for equal attitudes, 23.1% when only the alternative is positive, and 3.9% when only the current provider is positive. A larger saving raises switching probability continuously. More favorable alternative attitudes encourage switching; more favorable current attitudes discourage it. A weight of zero disables its contribution.

The four old `p-switch-*` inputs have been retired from the working model. They do not have a unique scientifically defensible mapping to the three new weights, so the runner rejects them rather than silently ignoring or translating them.

## Neighborhoods and weekly energy

Households cache nearby households only after all final positions have been assigned. The additional cache initialization runs inside `with-local-randomness`, preserving the random stream used for initial network construction. The base case retains the original setup counts of 995 formal and 1,005 unconnected households.

Poles now expose two different quantities:

- `pole-demand`: requested weekly energy after cash and informal-cap constraints, before any pole outage.
- `pole-usage`: electricity delivered during that week's consumption phase.

Both are recomputed each week. Fixed monthly payments happen before the load forecast, so formal consumption cannot assume cash already spent on an installment. Formal requested load is limited by remaining cash divided by tariff. Service drops and hook-ons both request at most `informal-connection-capacity` per household per week.

A pole whose current requested load exceeds capacity supplies no electricity that week. Persistent excess demand can therefore cause persistent outages; zero delivery during an outage does not manufacture an automatic recovery next week. When demand falls below capacity, service can recover. Pole connections still do not implement upstream power flows or voltage constraints.

Requested and delivered values describe the links present before consumption. Later connection changes and enforcement can alter the end-of-week network. An end-of-week connection is not evidence that electricity was delivered through it earlier that week.

## Decision and event logging

Logging is opt-in. The standard runner has no decision-file I/O unless logging is explicitly enabled. Use a fresh directory:

```powershell
python scripts/run_model_diagnostics.py --steps 52 --output outputs/base_revised_diagnostics
```

The diagnostic runner saves `decisions.csv`, weekly `trajectory.csv`, standard final `results.csv`, model and include snapshots, resolved inputs, provenance and summaries. `--no-log` retains weekly observations without the decision file. Manual NetLogo use is also supported:

```netlogo
setup
decision-log-start "decisions.csv"
repeat 52 [ go ]
decision-log-stop
```

An existing decision file is protected from overwrite. `decision-log-flush` writes buffered records; the diagnostic runner flushes each week and closes the file at its requested horizon. A new setup closes a previously open log.

The 52-column schema records:

- A consecutive event identifier, internal tick, household identifier, stage, event kind and reason.
- Status, source and upstream pole before and after the event, including a hook-on's original host and pole.
- Pre-decision attitudes toward both providers, expected monthly costs, income, available cash, expenditure and spending reference.
- Feasible formal and informal source counts, choice weights, relative savings, attitude difference, probability and actual random draw.
- Whether a switch was attempted, whether it succeeded, its target, and co-occurring issue labels.

`voluntary-choice` rows cover evaluated issue-triggered choices, including draws that do not lead to an attempt and attempts blocked by reach. `access-attempt` rows cover the existing informal-entry rule. `forced-disconnection` records distinguish KPLC/IPD nonpayment, enforcement, and loss of a host through nonpayment or voluntary switching. Multiple events for one household in one week remain separate.

Source counts represent reachable supply offers, not distinct companies. Counts and probability/draw fields use -1 when not applicable to a forced event. Blank derived score terms indicate no two-provider comparison. `decision_tick = 0` refers to the first go call; its outcome appears at tick 1 in the weekly trajectory. Initial setup assignments are not logged as voluntary decisions.

Issue labels include blackout, formal demand shortfall, informal capacity shortfall, spending pressure and safety incident. They record co-occurring experiences, not the causal contribution of each experience. Post-event attitudes are also saved, including changes caused by enforcement. The logger does not add behavioral random draws; observation work uses `with-local-randomness`.

## Compatibility and reproducibility

The model uses [decision_logging.nls](../models/decision_logging.nls). The standard runner discovers local includes, copies them next to each model snapshot, and includes their hashes in the run fingerprint. Changes or tampering with an include invalidate resume just like changes to the main model.

To rerun the original base profile:

```powershell
python run_model.py base --config experiments/original-model.json --base experiments/original-base.json --output outputs/base_original_repeat
```

The existing LHS design samples the retired controls. Use the explicit original configuration and a fresh output directory to run it against the original model. A revised-model LHS design must instead specify the new choice weights. The historical prepared LHS plan is retained but should not be resumed with the changed runner fingerprint.

The original benchmark, observation, descriptive-analysis and figure scripts are pinned to the archived original model and original profile. They will not silently regenerate original figures using revised dynamics. [models/source.json](../models/source.json) records both original and working model hashes.

## Verification and remaining scope

Twenty runner tests and nine sampling tests pass. Six real-NetLogo test groups cover 19 behavioral contracts plus log-file assertions: cost and attitude monotonicity, cost magnitude, numerical bounds, exact neighborhoods, fresh load and delivered energy, consistent informal caps, persistent overload and recovery, billing/cash order, and distinct forced events. Logging enabled and disabled gives identical complete dynamic states and the same next random draw over 52 weeks.

The [event validation](../results/attitude_trust_revision/event_validation.json) reconstructs every voluntary probability from the logged pre-decision values, checks draws and destinations, and verifies separate forced events. The logged 52-week trajectory equals the first 52 weeks of the unlogged 1,480-week run.

Attitudes remain Boolean and retain their original learning and blame rules. Household budgets still reset to total income. Unconnected households still seek informal entry, including possible same-week re-entry after a forced disconnection. Those are later proposed changes, not corrections included here. The existing mixed `switchcount` remains available for comparison; event kinds should be used when analysing voluntary switching.
