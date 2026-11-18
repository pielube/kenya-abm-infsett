# Choosing model inputs with Latin Hypercube Sampling

This project creates sets of input values for an agent-based model (ABM) of
Kenya's informal settlements. It uses the ranges in `data/parameters.csv` to
choose combinations of values to try. See [running the model](running.md) for
the separate base-run and batch-run workflow.

## Configurations and runs

A **configuration** is one combination of input values, such as the number of
households, number of poles, and starting trust levels.

The default settings create **256 configurations**. Each is repeated **five
times**, keeping the same inputs but using a different random seed for each run:

**256 configurations × 5 repeats = 1,280 planned model runs.**

A random seed is a starting number for the program's random choices. Repeating
each configuration with different seeds helps show how much the model's results
vary because of randomness. The command-line option for repeats is `--replicates`.

## How the values are chosen

The code uses **Latin Hypercube Sampling (LHS)** to spread the chosen values
across each input's range. For a decimal-valued input, it divides the range into
256 equal parts, picks one value from each part, and shuffles the values before
combining them with the other inputs.

Whole numbers and category labels are chosen from the same underlying sampling
process. Their values can repeat because there may be fewer possible choices
than configurations. Each allowed whole number or category has an equal chance
of being chosen. Decimal values are spread evenly across the original scale;
they do not usually include the exact endpoints.

For `blackouts-attitude`, the four choices are `a`, `b`, `c`, and `d`. Each appears
in exactly **64 of the 256 configurations**. Equal category counts are not
guaranteed when the configuration count is not divisible by four.

256 configurations and five repeats are starting choices. Larger experiments
with different seeds can help check whether the findings hold up. Use the
variation between repeated runs to decide whether more repeats are needed. LHS
accepts any positive number of configurations; changing that number creates a
new set rather than adding rows to the old one.

The code uses
[SciPy's LHS tool](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.LatinHypercube.html).
Its detailed settings are saved in `metadata.json`.

## Install and run

Requires Python 3.10 or newer. Open a terminal in this project's main folder:

```sh
python -m pip install -r requirements.txt
python lhs.py --output outputs/my_experiment
```

The default experiment is already saved in `outputs/lhs_256/`. Choose a new
output folder when generating another set; the code will not overwrite an
existing folder.

To choose different settings:

```sh
python lhs.py --samples 512 --replicates 10 --seed 123 --output outputs/lhs_512
```

This creates **512 configurations × 10 repeats = 5,120 planned runs**.
`--samples` sets the number of configurations. `--seed` controls the random
choices used to prepare the experiment; the default is **42**.

Use `--parameters path/to/parameters.csv` to read another parameter table.
By default, the code reads `parameters.csv` from the `data` folder next to
`lhs.py`. Output paths start from the folder where you run the command.

## The parameter table

`data/parameters.csv` keeps all **35 variable names and original range
descriptions**. The code chooses values for **31 parameters**. These four were
marked "not necessary to test?" and had no ranges, so they are excluded:

- `pole-connection-limit`
- `formal-connection-limit`
- `informal-sd-limit`
- `hookon-limit`

Set their values in the model, or use its known defaults. The sampler does not
assign values to them.

To change how a parameter is sampled, edit these columns:

| Column | Meaning |
| --- | --- |
| `kind` | `continuous` for numbers that allow decimals; `integer` for whole numbers; `categorical` for labels; `excluded` to leave it out |
| `lower`, `upper` | Smallest and largest allowed numeric values |
| `categories` | Allowed labels, separated by `\|`, for example `a\|b\|c\|d` |
| `range`, `notes` | Human-readable descriptions; update them when changing the choices above |

To include an excluded parameter, give it a suitable kind and range or category
list. Whole-number ranges include both endpoints.

The current choices are:

- `n-households`, `n-poles`, `enforcement-number`, and `enforcement-freq` use whole
  numbers. This assumes enforcement intervals use whole model time steps.
- Other numeric inputs allow decimals. Change this if the model requires whole
  numbers, for example for connection capacities.
- Percentages use **0-100**, not 0-1. The four `p-switch-*` percentages are chosen
  independently and do not need to add up to 100.
- `a`, `b`, `c`, and `d` are short labels. The model runner translates them to
  the four attitude choices found in the supplied model.

These choices use the supplied ranges; they are not estimates fitted to Kenyan
observations. Units and extra relationships between inputs have not been assumed.
Check that the combinations are allowed by the model. The supplied fee ranges
already ensure `min-informal-fee` cannot exceed `max-informal-fee`.

## Saved files

Each experiment folder contains these files. The row counts below describe the
default experiment.

| File | What it contains |
| --- | --- |
| `design.csv` | The 256 configurations, each with a `sample_id` and 31 input values |
| `runs.csv` | The 1,280 planned runs, including all input values, run and configuration IDs, repeat number, and `model_seed` |
| `unit_samples.csv` | The sampled numbers between 0 and 1, before turning them into model inputs; used to check how values are spread |
| `parameters.csv` | A copy of the parameter table used to create this experiment |
| `metadata.json` | Settings, seed, software versions, parameter order, and a checksum to identify the parameter table |

Keep these files together. To recreate an experiment exactly, use the same table,
settings, seed, and software versions. A seed alone is not enough if software
versions change.

Each planned run has its own `model_seed`, chosen separately from the random
choices used to build the configurations. Keeping the table, sample count, and
seed the same while changing the repeat count leaves the configurations
unchanged, but can change the model seeds. Reuse the saved `runs.csv` when you
want to repeat exactly the same runs.

## Using the inputs in a model

Use `runs.csv` to run the full experiment. CSV readers may load every value as
text, so convert numeric columns to whole or decimal numbers using the saved
parameter table. Start each run with its `model_seed` and pass the input columns
to the model. Keep the IDs with the results so you can match them to the inputs.

`run_model.py` handles these steps, supplies the model's saved defaults for the
excluded limits, and translates the attitude labels. Run duration and recorded
results are explained in [running the model](running.md).

You can also call the sampler directly from Python:

```python
from lhs import load_parameters, sample_lhs

parameters = load_parameters()
scenarios, unit_samples = sample_lhs(parameters, samples=256, seed=42)
model_inputs = {key: value for key, value in scenarios[0].items() if key != "sample_id"}
```

Here, `scenarios` contains the configurations as Python numbers and labels.
`model_inputs` contains the first configuration's inputs without its ID.

## Check the code

```sh
python -m unittest discover -s tests -v
```

The tests check that values stay within their ranges, whole numbers and labels
are valid, the sampling covers each part of the ranges, and the same settings
produce the same files. They also check repeats, model seeds, and command-line
use. They test input generation; running and checking the ABM requires the model.
