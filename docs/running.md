# Running the model

Use these commands from the project's main folder. `run_model.py` starts NetLogo
in the background, so you do not need to open its window or change sliders by
hand. The runner uses only Python's built-in libraries. The LHS sampler also
needs NumPy and SciPy.

The default model is the revised working version. The original model and its
figures remain in [results/base](../results/base/README.md). See
[model revisions](model-revision.md) for the changed rules and logging schema.

## Keep Python separate from other projects

A dedicated conda environment is recommended:

```sh
conda env create -f environment.yml
conda activate kenya-abm
```

This creates a new environment. It does not install packages into the environment
you were previously using. To leave it, run `conda deactivate`.

## NetLogo setup

The supplied model was saved with **NetLogo 7.0.3**, the version tested here.
Get that version from the [official release](https://github.com/NetLogo/NetLogo/releases/tag/v7.0.3).
Its Windows distribution includes Java; a separate Java install is not needed
when using `NetLogo_Console.exe`.

On the machine where this project was set up, the official Windows runtime is
already extracted in `.tools/NetLogo 7.0.3/`. The runner finds it automatically.
This folder is excluded from Git, so someone cloning the repo needs their own
NetLogo copy.

For another installation location, pass its folder:

```powershell
python run_model.py base --netlogo-home "C:\Program Files\NetLogo 7.0.3"
```

Alternatively, set `NETLOGO_HOME`. This PowerShell command sets it for the current
terminal session:

```powershell
$env:NETLOGO_HOME = "C:\Program Files\NetLogo 7.0.3"
```

NetLogo's [background execution guide](https://docs.netlogo.org/7.0.3/behaviorspace.html#advanced-usage)
covers other operating systems. The runner uses their `NetLogo_Console` launcher.
The Windows workflow has been tested here; other operating systems have not.

## Develop with the base run

```sh
python run_model.py base
```

This runs **52 ticks**, starting with seed **42**, and saves results in
`outputs/base_run/`. Starting values are in `experiments/base.json` and match the
sliders and chooser saved in the revised working model. Its three choice weights
are cost sensitivity **1**, attitude weight **1**, and switching inertia **2.2**.
Edit that file to try different
starting conditions. Edit `models/kenya_informal_settlements.nlogox` to develop the
model, or open it in NetLogo to use the visual interface.

Use a new output folder for each change you want to compare:

```sh
python run_model.py base --steps 104 --output outputs/base_104
```

The model advances one tick per `go` call and stops at tick **1480**. The runner
therefore allows at most 1480 steps. The code treats four ticks as about a month;
52 ticks is a convenient development check, not a calibrated study duration.
If you change the stopping rule, update `max_steps` in `experiments/model.json`.

The model's `bau` helper changes some settings and is marked as needing an update.
The runner uses the explicit base profile instead. Old experiments saved inside
the model refer to removed variables; the runner generates new experiments.

## Record revised model decisions

Use a fresh output directory:

```sh
python scripts/run_model_diagnostics.py --steps 52 --output outputs/base_revised_diagnostics
```

This writes final `results.csv`, weekly `trajectory.csv`, and a decision/event
log in `decisions.csv`, together with the model snapshot, settings and provenance.
The log captures pre-choice attitudes, costs, cash, feasible source counts,
probability and draw, then attempted and realized outcomes. Voluntary choices,
informal entry and forced losses are distinct events; initial setup assignment
is excluded. Co-occurring issue labels do not identify individual causal effects.
`--no-log` disables decision/event file logging without disabling attitude
mechanisms; weekly metrics are still collected.

The ordinary `run_model.py` workflow leaves decision logging off. All local
NetLogo includes are copied with the model and checked during resume.

## Run the archived original model

Select both the original source configuration and original base parameters:

```sh
python run_model.py base --config experiments/original-model.json --base experiments/original-base.json --output outputs/base_original_check
```

Add `--steps 1480` for the full horizon. The original source is pinned to
`results/base/runs/52_ticks/model.nlogox`; it does not use the revised model.

## Archived base results and figures

The reviewed original base outputs are preserved in the Git-tracked
[results/base archive](../results/base/README.md). It contains the ordinary
[52-tick run](../results/base/runs/52_ticks/) and
[1,480-tick run](../results/base/runs/1480_ticks/), their settings and model copies,
the setup diagnostic, detailed observations, benchmark summaries, figures, and
numerical figure source data. See [base figures](base-figures.md) for reproduction
commands and interpretation.

New executions still default to `outputs/base_run/`; base, batch, and smoke
output folders are ignored scratch space. Use a fresh folder for a new run,
and preserve reviewed outputs separately in the tracked archive.

## Run the LHS experiment

The original 256-configuration experiment is already in `outputs/lhs_256/`.
Its four `p-switch-*` controls were retired from the revised model, so this design
must run with `experiments/original-model.json`. A revised-model LHS study requires
a new parameter table and a newly sampled design; see [sampling](sampling.md).
To generate another original-model set:

```sh
python lhs.py --samples 256 --replicates 5 --seed 42 --output outputs/lhs_new
```

Try a small part first:

```sh
python run_model.py batch --config experiments/original-model.json --runs outputs/lhs_256/runs.csv --limit 2 --steps 52 --output outputs/batch_original_small
```

`--limit 2` selects the first two rows. The existing list has five repeats per
configuration, so these two rows use the same configuration with different seeds.

To run the full existing experiment:

```sh
python run_model.py batch --config experiments/original-model.json --runs outputs/lhs_256/runs.csv --threads 4 --output outputs/batch_original
```

The historical prepared plan in `outputs/batch_lhs/` contains **1280 runs of 1480
ticks each** and is retained as provenance. Its old runner fingerprint does not
match the current runner, so prepare the fresh `outputs/batch_original/` folder
above rather than trying to resume that historical plan. A full batch can take
much longer than the base run. `--threads 4` runs up to four simulations at once
and uses more memory; the default is one. Change `--steps` if a different study duration is intended.
Each LHS row stays together as one combination of values. The runner uses the
five existing repeats once, without multiplying them again.

To prepare files without launching NetLogo:

```sh
python run_model.py batch --config experiments/original-model.json --prepare-only --output outputs/batch_original_plan
```

This works without NetLogo. To execute that plan later, use the same command
without `--prepare-only` and add `--resume`.

## Stop and restart

The runner saves each attempt's raw output and log. To restart, repeat the same
command with `--resume`:

```sh
python run_model.py batch --config experiments/original-model.json --runs outputs/lhs_256/runs.csv --threads 4 --output outputs/batch_original --resume
```

Only runs with valid results at the requested final tick count as complete.
Unfinished runs are retried with their original inputs and seeds. Results are
matched by run number and checked against recorded inputs, even when parallel
runs finish out of order. A process exiting without an error does not by itself
count as a successful model run.

Resume requires the same model, local includes, runner, settings, and inputs.
If any changed, choose a new output folder. You can change the thread count. `--timeout 600`
sets a ten-minute limit for one execution attempt, not for each individual run.

## Input names and defaults

`experiments/model.json` and `experiments/original-model.json` record these translations:

| Sampling input | Model input |
| --- | --- |
| `init-trust-kplc` | `init-attitude-kplc` |
| `init-trust-ipd` | `init-attitude-ipd` |
| blackout choice `a` | `only-hurt-kplc` |
| blackout choice `b` | `hurt-both-providers` |
| blackout choice `c` | `ipd-partial-mitigation` |
| blackout choice `d` | `ipd-full-mitigation` |

The four unsampled limits use the saved model defaults: pole connection limit
**5**, formal connection limit **5**, informal service-drop limit **4**, and
hook-on limit **3**. `formal-connect-fee`, absent from the original table, stays
at **625**. Every resolved value is saved in the experiment's `inputs.csv`.

The original LHS ranges and files are preserved. Some ranges extend beyond the
visual sliders: debt threshold reaches 40 while its slider ends at 20. NetLogo's
background runner accepts these values. Decimal values are passed through without
snapping them to slider increments. Review those choices as part of developing
the scientific experiment.

The revised choice parameters are `choice-cost-sensitivity`,
`choice-attitude-weight`, and `choice-switching-inertia`. Original `p-switch-*`
values are rejected for the revised source rather than silently ignored.

## Files to inspect

| File | Purpose |
| --- | --- |
| `results.csv` | One row per successful run, with run IDs, seed, and named results |
| `inputs.csv` | Actual model names and values, including defaults |
| `plan.json` | Run settings, resolved inputs, version, and checksums |
| `model.nlogox` | Exact model copy used for the experiment |
| Local `.nls` includes | Dependencies copied beside the model; their hashes are recorded in the plan |
| `experiment.xml` | The complete NetLogo experiment setup |
| `attempt_001.*` | An attempt's setup, raw CSV, log, and mapping to original run IDs |

The initial results include connection types, trust percentages, mean debt,
mean number of switches, and overloaded poles. These describe the final tick
only. Edit the named reporters in `experiments/model.json` to change which
results are collected. Keep `ticks` so the runner can check completion.

Test the Python code with:

```sh
python -m unittest discover -s tests -v
```

These tests cover sampling, input translation, experiment generation, include
snapshots, result matching, and restarting. When NetLogo is installed, the
behavioral tests also launch it to check choice monotonicity, neighborhood and
load accounting, and logging equivalence; those tests skip when it is unavailable.
The archived original engine
benchmarks repeated both the 52-tick base case and the 1,480-tick case three times
with seed 42 and reproduced the original endpoints. The diagnostic observation
run also reproduced both endpoints. The full 1,280-run LHS experiment has not
been executed; its input design remains tracked in `outputs/lhs_256/`, and the
prepared plan and resolved inputs remain in `outputs/batch_lhs/`.
