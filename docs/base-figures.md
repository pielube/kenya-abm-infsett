# Base model diagnostic figures

Four figures describe the archived original model's access and churn, Boolean provider attitudes, outage process, and affordability across household incomes. The deliverables are in the Git-tracked [base results archive](../results/base/README.md). The revised working model is described separately in [model revisions](model-revision.md); its changes are not represented in these original figures.

- [Runtime and interpretation report](../results/base/report.md).
- [All four figures as a vector PDF](../results/base/figures/base_model_extended_data.pdf).
- [Complete package with source data and code](../results/base/base_model_figure_package.zip).
- [Full figure legends](../results/base/captions.md).

The ordinary base-run endpoints and their experiment files are preserved in [runs/52_ticks](../results/base/runs/52_ticks/) and [runs/1480_ticks](../results/base/runs/1480_ticks/). The [setup diagnostic](../results/base/setup/) preserves the initial-state and neighborhood-cache checks. Weekly observations used for the figures are in [data](../results/base/data/), and numerical panel tables are in [source_data](../results/base/source_data/).

On the tested Intel Core i7-1265U, sequential fresh-process benchmarks gave median wall times of **13.35 seconds for 52 ticks** and **30.59 seconds for 1,480 ticks**, using three executions per horizon. These times include startup, setup, simulation and output writing. Detailed observation collection took **137.34 seconds** separately. Both observed endpoints reproduced all 13 original result metrics.

The figures describe a single seed-42 realization, rather than an ensemble or empirical validation. Household interquartile ranges show heterogeneity, not uncertainty in an estimated mean. The archived original's incomplete neighbor cache and accumulated pole-usage mechanism remain part of the implementation being described; see the [base model guide](base-model-guide.md).

The artwork follows the current [Nature Extended Data specifications](https://research-figure-guide.nature.com/figures/extended-data-formatting-guidelines/): 180 mm wide, under 170 mm high, Arial text, consistent panel labels and strokes. PDF and SVG files are editable masters. The submission-format TIFFs are 300 dpi RGB, losslessly compressed, and under 10 MB each. Numerical source data are supplied as panel CSVs and a workbook per figure. Final placement and scientific claims should follow the intended journal and manuscript.

To reproduce the analysis, use NetLogo 7.0.3 and run these commands from the repository root, choosing a fresh output directory:

```powershell
python scripts/benchmark_base.py --output outputs/base_publication_repeat/benchmark
python scripts/collect_base_diagnostics.py --output outputs/base_publication_repeat/data
python scripts/plot_base_figures.py --data outputs/base_publication_repeat/data --output outputs/base_publication_repeat
```

The benchmark and collection scripts pin `results/base/runs/52_ticks/model.nlogox` and `experiments/original-base.json`; the benchmark also selects `experiments/original-model.json`. They therefore reproduce the original model even as the working model changes. The first two scripts use the existing Python environment. Plotting needs the packages in [requirements-figures.txt](../requirements-figures.txt). The analysis used an existing `dataviz-env` environment with those packages, leaving the simulation environment intact.

The plotting script defaults to the archived `results/base/data` inputs and `results/base` output. To re-render the archive from its saved observations, run `python scripts/plot_base_figures.py`. Benchmarking and collection default to ignored scratch outputs; the explicit fresh-directory commands above keep new executions separate from the reviewed archive.

The benchmark records exact commands and hardware. The archive retains consolidated timings instead of redundant repeated-run folders. Collection saves the private observer copy, its patch and hashes, phase definitions, endpoint validation, and data-integrity checks. The figure manifest records input hashes, output hashes, dimensions, fonts, resolution, and package versions. The reviewed results in `results/base/` are tracked by Git; new scratch runs under `outputs/base_*/`, `outputs/batch_*/`, and `outputs/smoke_*/` are ignored.
