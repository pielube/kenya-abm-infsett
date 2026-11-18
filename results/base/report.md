# Base model runtime and diagnostic figures

Four candidate Extended Data figures describe the existing seed-42 base model over its full 1,480-tick horizon. They combine weekly observations, selected household cross-sections, and a diagnostic of the implemented outage process. One tick is approximately one model week; financial routines use four-week months.

## Runtime

| Execution | Repeats | Median wall time | Observed range |
| --- | --- | --- | --- |
| Default base run, 52 ticks | 3 | 13.35 s | 13.03–13.62 s |
| Full model horizon, 1,480 ticks | 3 | 30.59 s | 30.34–32.53 s |

Fresh processes ran sequentially, headlessly, with one NetLogo thread and seed 42. Wall time includes Python and JVM startup, compilation, setup, simulation, and output writing. These are execution repeats of the same stochastic realization, not independent random seeds. All six endpoints reproduced the saved reference results. Hardware: 12th Gen Intel(R) Core(TM) i7-1265U; NetLogo 7.0.3. Exact timings and environment details are in [timing.json](benchmark/timing.json).

The separately instrumented run took 137.34 s, including startup and detailed observation exports. This is data-collection overhead, not the ordinary base runtime. All 13 reference metrics matched at ticks 52 and 1,480. [Validation](data/validation.json) and [observation provenance](data/provenance.json) record the checks and exact additions to the private model copy.

## Figure ideas and measured findings

1. **Connection composition and churn.** Formal access drops to 23.3% at week 8, while informal access peaks at 66.25% at week 46. Formal access ends at 53.35%. Across the full run, 274,900 adjacent-week status changes represent 9.29% of household-week observations. Changing aggregate composition therefore coexists with frequent household changes. The transition matrix excludes within-week reversals and informal subtype changes.
2. **Provider attitudes.** Positive KPLC attitudes reach 8.0% at week 56 and end at 32.4%; positive IPD attitudes end at 40.6%. Joint states and status-conditioned endpoints show that attitudes and current connection arrangements are associated. The model represents attitudes as Boolean flags; these observations do not isolate causal effects.
3. **Reliability and accumulated loading.** An average of 36.38% of poles are overloaded across completed weeks, while 36.92% of households are exposed before consumption and connection changes. The pole raster and representative trace show repeated loading and resets. The implementation accumulates pole usage across weeks, so this figure must not be described as instantaneous electrical power flow.
4. **Affordability and income differences.** Predicted formal charges exceed desired spending across income groups even after repayment, while informal charges become relatively inexpensive at higher incomes. At the endpoint no currently formal household has installments due; formal access by income quintile is 68.25%, 51.25%, 43.25%, 45.25%, 58.75%, lowest to highest. Access is nonmonotonic in income. The poorest quintile's median month-end electricity expenditure falls from 13.58% of income at week 52 to 5.84% at week 1,480. These associations do not establish repayment as the cause of changing access.

## Files and production settings

- [All four figures in one vector PDF](figures/base_model_extended_data.pdf).
- [Complete figure package](base_model_figure_package.zip), with individual PDF, SVG, RGB TIFF and PNG files, panel-level source CSVs, one source-data workbook per figure, raw observations, scripts, configuration, and original model.
- [Figure legends](captions.md), each below 250 words, and [figure manifest](figure_manifest.json).

Each figure is 180 mm wide and 140 or 145 mm high. Body text is Arial 7 pt; panel letters are bold 8 pt. PDF fonts are embedded TrueType and SVG text remains editable. TIFFs are 300 dpi RGB with lossless LZW compression and are below 10 MB each. Colors, line styles and marker shapes distinguish related variables. Source-data whiskers in Figure 4 represent household interquartile ranges, not confidence intervals.

Nature generally places additional ordinary figures in Extended Data; the destination can differ for other Nature Portfolio journals. Formatting follows the current [Extended Data guide](https://research-figure-guide.nature.com/figures/extended-data-formatting-guidelines/) and [figure export guide](https://research-figure-guide.nature.com/figures/building-and-exporting-figure-panels/). These are publication-format candidates; scientific acceptance also depends on validation and the manuscript's claims.

## Scope and implementation details

These figures describe one seed, not stochastic robustness or empirical validation. Confidence bands and inferential tests would be inappropriate for the present collection. The known incomplete household-neighbor cache affects hook-on availability and safety exposure. The outage accumulator and other implementation details in the [base model guide](../../docs/base-model-guide.md) also apply. No correction to the supplied model dynamics is included here.

Added observations execute inside `with-local-randomness`, and a private model copy contains the observer wrappers and a read-only hook immediately after blackout classification. Household outage exposure is captured before consumption and switching; other aggregate states are recorded after the original `go` completes. Tick 0 records setup. Enforcement at internal tick 0 appears at observation tick 1; subsequent sweeps appear at 111, 221 and so on. Selected expense snapshots at ticks 52 and 1,480 close a four-week billing month and can include multiple arrangements within that month.

## Reproduction

Use the repository's NetLogo 7.0.3 runtime and standard Python environment for benchmarking and collection. Run plotting in an environment with [requirements-figures.txt](../../requirements-figures.txt); the supplied environment already had the required packages. Use a fresh output directory for repeated benchmark or collection jobs.

```powershell
python scripts/benchmark_base.py --output outputs/base_publication_repeat/benchmark
python scripts/collect_base_diagnostics.py --output outputs/base_publication_repeat/data
python scripts/plot_base_figures.py --data outputs/base_publication_repeat/data --output outputs/base_publication_repeat
```

Source model SHA256: `859d920dcb381ebdffc381525c24747d0dff3d7fbd315959f540cd9dd957c987`. Each plotting input and the plotting script have their own SHA256 recorded in the figure manifest.
