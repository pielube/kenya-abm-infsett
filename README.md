# Kenya informal settlements: agent-based model experiments

This project keeps the model, its starting values, and its experiments together.
Python can run NetLogo in the background and save results without opening the
NetLogo window.

There are two separate workflows:

- **Base run:** one set of starting values for testing and developing the model.
- **LHS batch:** many input combinations, each repeated with different random
  seeds, for exploring how the model behaves.

## Set up once

A separate conda environment is recommended:

```sh
conda env create -f environment.yml
conda activate kenya-abm
```

This creates a new environment and leaves your previous one unchanged.

The model uses **NetLogo 7.0.3**. On the machine where this repo was set up, a
local runtime is already available in `.tools/NetLogo 7.0.3/`. The runner finds
it automatically. This folder is not included in Git. For another machine,
download NetLogo 7.0.3 and follow the [setup instructions](docs/running.md#netlogo-setup).

## Test and develop the model

```sh
python run_model.py base
```

This runs **52 ticks** with seed **42**, using the values in
`experiments/base.json`. Results go to `outputs/base_run/results.csv`.
If that folder already exists, use `--resume` to finish the same run or choose
a new folder for a new experiment:

```sh
python run_model.py base --output outputs/base_test_2
```

Edit `experiments/base.json` to change starting values. Edit
`models/kenya_informal_settlements.nlogox` to change the model. The supplied model
was copied unchanged; `models/source.json` records its original filename and
checksum. Each experiment also saves its own model copy.

The reviewed 52-tick and 1,480-tick base runs, diagnostic observations, figures,
and source data are preserved in the Git-tracked [base results archive](results/base/README.md).
New runs still use `outputs/` as scratch space; the `base_*`, `batch_*`, and
`smoke_*` output folders are ignored by Git.

## Create sampled inputs

A **configuration** is one combination of input values. Latin Hypercube Sampling
(LHS) spreads values across the ranges in `data/parameters.csv`.

The existing experiment in `outputs/lhs_256/` has **256 configurations**, each
repeated five times with different random seeds:

**256 configurations x 5 repeats = 1,280 planned model runs.**

To make a new set:

```sh
python lhs.py --samples 256 --replicates 5 --seed 42 --output outputs/lhs_new
```

The table keeps all 35 original variables. 31 are sampled; the four excluded
connection limits use the model's saved defaults when it runs. The runner also
translates the two trust input names and the four blackout labels to match the
model. See [sampling details](docs/sampling.md).

## Run a batch

Start with a short check of the first two rows:

```sh
python run_model.py batch --limit 2 --steps 52 --output outputs/batch_small
```

These rows are two repeats of the first configuration. To run the full existing
experiment with up to four simulations at once:

```sh
python run_model.py batch --threads 4 --output outputs/batch_lhs --resume
```

The full batch uses **1,280 runs of 1,480 ticks** and can take much longer.
Choose another duration with `--steps` and a new output folder. The prepared
1,280-run plan remains in `outputs/batch_lhs/`; `--resume` starts its pending
runs. To prepare a separate plan without launching NetLogo, choose a fresh
output folder and add `--prepare-only`.

To continue an interrupted or prepared batch, repeat its command with `--resume`.
Completed runs are kept; unfinished ones are retried with their original inputs
and seeds. Changes to the model, runner, settings, or inputs require a new output
folder.

## Find files and check results

| File or folder | What it is for |
| --- | --- |
| `models/` | The supplied NetLogo model and its source details |
| [Base model guide](docs/base-model-guide.md) | Model purpose, rules, base results, interpretation, and code navigation |
| [Base figures](docs/base-figures.md) | Runtime benchmarks, four diagnostic figures, source data, and reproduction |
| [Base results archive](results/base/README.md) | Git-tracked base runs, figures, observations, source data, and provenance |
| `experiments/base.json` | Starting values for the base run |
| `experiments/model.json` | Input-name translations and results to record |
| `data/parameters.csv` | Ranges and types for LHS inputs |
| `lhs.py` | Creates configurations and the list of runs |
| `run_model.py` | Prepares, runs, and restarts NetLogo experiments |
| `outputs/lhs_256/` | The original sampled inputs |
| `outputs/batch_lhs/` | Preserved prepared full-batch plan and resolved inputs; no completed simulations |
| `outputs/base_*/`, `outputs/batch_*/` | Ignored scratch runs, actual inputs, model copies, and logs |

Each successful run has one row in `results.csv`, with its IDs and seed.
The starting results include connection types, trust, debt, switching, and
overloaded poles. Keep output folders to trace results back to their inputs.

Run the Python checks with:

```sh
python -m unittest discover -s tests -v
```

More detail: [running and restarting experiments](docs/running.md) and
[how sampling works](docs/sampling.md).
