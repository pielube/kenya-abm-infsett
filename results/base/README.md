# Base model runs and figures

This Git-tracked archive contains the seed-42 base runs, four publication-format diagnostic figures, numerical source data, and execution provenance.

| Location | Contents |
| --- | --- |
| [runs/52_ticks](runs/52_ticks/results.csv) | Canonical 52-tick base result, inputs, model snapshot, experiment definition, and execution records |
| [runs/1480_ticks](runs/1480_ticks/results.csv) | Canonical full-horizon result and its execution records |
| [figures](figures/base_model_extended_data.pdf) | Four figures in a combined PDF and individual PDF, SVG, PNG, and RGB TIFF files |
| [source_data](source_data) | Panel-level CSVs and a workbook per figure |
| [data](data/provenance.json) | Weekly observations, selected household states, links, observer model, and validation |
| [setup](setup/diagnostics.json) | Initial conditions and household-neighborhood cache diagnostic |
| [benchmark](benchmark/timing.json) | Three timing measurements per horizon and consolidated logs |
| [report.md](report.md) | Runtime definitions, measured findings, interpretation, and reproduction |
| [captions.md](captions.md) | Full figure legends |
| [base_model_figure_package.zip](base_model_figure_package.zip) | Portable figure, source-data, run, and code package |

The original source model is unchanged. Observation endpoints match the canonical results at ticks 52 and 1,480. The figures describe one realization and the current implementation, including the known neighborhood-cache and pole-loading behavior.

The [cleanup manifest](cleanup_manifest.json) maps former output locations to this archive and lists removed checks and duplicate benchmark runs. Original execution scripts and the earlier figure manifest are retained in `provenance/`; historical commands in timing and provenance records keep the paths used during execution. Current scripts resolve the archived reference results here.

New experimental runs continue to use ignored folders under `outputs/`. The original LHS design in `outputs/lhs_256/` and the prepared plan in `outputs/batch_lhs/` are preserved.

To regenerate the figures from retained data, run `python scripts/plot_base_figures.py` from a plotting environment at the repository root. See [the figure guide](../../docs/base-figures.md) for fresh benchmarking and collection commands.
