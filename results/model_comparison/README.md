# Original and revised model comparison

Four figures distinguish verified computational corrections from changes in the seed-42 base trajectory. Original is gray and dashed; revised is blue and solid. Full legends are in [captions.md](captions.md).

1. **Switching responses.** The original current-positive/alternative-negative rule switches with 20% probability when the alternative is not cheaper, but 0% when cheaper. The revised logistic rule responds continuously and monotonically to savings and attitudes. Revised weights remain uncalibrated. The x-axis is unitless: monthly cost savings divided by desired monthly electricity spending. It is not the percentage reduction in the current bill. For a current bill of 1,000 and desired spending of 500, an alternative costing 985 saves 1.5% of the bill but appears at x=0.03; an alternative costing 250 appears at x=1.5.
2. **Accounting corrections.** Controlled fixed-demand networks expose false below-capacity outages and automatic recovery under persistent overload in the original. The revision removes both artifacts, applies the 13 kWh cap to hook-ons, and eliminates incomplete neighborhood caches. Original reported usage is an accumulator; revised reported usage is weekly delivery.
3. **Base-run trajectories.** Formal access ends at 53.35% originally and 19.8% after revision; positive KPLC attitudes end at 32.4% and 24.4%. These are combined-change outcomes, not evidence of better empirical fit or household welfare.
4. **Changes and logging.** The original first-52-week observed status-change rate is 13.64% of households per week, versus 4.35% revised. The new log separates evaluated choices, failed attempts, successful connections and forced losses, including changes reversed within a week.

## Downloads and source data

- [Combined vector PDF](figures/original_vs_revised.pdf).
- [Complete figure package](comparison_figure_package.zip).
- Individual PDF, editable SVG, PNG and 300 dpi RGB TIFF files are in `figures/`.
- Panel CSVs and one workbook per figure are in `source_data/`.
- [Controlled energy data](probes/energy.csv), [neighborhood checks](probes/neighborhoods.csv), and [validation](probes/validation.json).
- [Event reconstruction and limits](events/summary.json).

Figures are 180 mm wide and no more than 150 mm high, using Arial 7 pt and bold 8 pt panel letters. Source and output hashes are recorded in [figure_manifest.json](figure_manifest.json).

## Interpretation

Controlled accounting probes isolate the targeted implementation corrections by fixing connections, demand and cash. They execute blackout and consumption procedures, not full economic or switching dynamics. The neighborhood check uses each model's actual seed-42 setup.

Base trajectories use one seed per model with several revisions combined. Identical starting seeds do not impose identical subsequent stochastic shocks. There are no confidence intervals or calibration claims. Original and revised overload counts must not be treated as the same physical measure, and the mixed model switch counter is not used as a voluntary switching rate. Missing original voluntary/forced categories are never plotted as zero.

## Reproduction

To redraw the retained figures, run `python scripts/plot_model_comparison.py`. To regenerate the checks and figures in a fresh folder:

```powershell
python scripts/collect_comparison_probes.py --output outputs/base_comparison_repeat/probes
python scripts/summarize_comparison_events.py --output outputs/base_comparison_repeat/events
python scripts/plot_model_comparison.py --output outputs/base_comparison_repeat
```

The first command needs NetLogo 7.0.3 and fresh probe output folders. The final command needs the packages in `requirements-figures.txt` and the retained baseline inputs. Plotting reuses saved data and does not run either model. The original archive and revised baseline runs are unchanged. The downloaded package includes the plotting inputs; from its extracted root, `python code/scripts/plot_model_comparison.py --output .` redraws the figures.
