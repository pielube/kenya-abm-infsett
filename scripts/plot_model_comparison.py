"""Compare original and revised rules, controlled probes and seed-42 runs.

Uses saved data and model snapshots. Never modifies either model or reruns it.
Controlled accounting corrections establish computational improvements; baseline
trajectory differences do not establish empirical fit or welfare improvements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from PIL import Image

from plot_base_figures import MM, panel, style


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "#777777"
REVISED = "#0072B2"
MODELS = [("original", "Original", ORIGINAL, "--"), ("revised", "Revised", REVISED, "-")]
INPUTS = [
    "results/base/data/aggregate.csv",
    "results/base/runs/52_ticks/plan.json",
    "results/base/runs/52_ticks/model.nlogox",
    "results/attitude_trust_revision/1480_ticks/trajectory.csv",
    "results/attitude_trust_revision/52_ticks/plan.json",
    "results/attitude_trust_revision/52_ticks/model.nlogox",
    "results/attitude_trust_revision/52_ticks/decision_logging.nls",
    "results/model_comparison/probes/energy.csv",
    "results/model_comparison/probes/neighborhoods.csv",
    "results/model_comparison/probes/validation.json",
    "results/model_comparison/events/weekly_churn.csv",
    "results/model_comparison/events/logging_funnel.csv",
    "results/model_comparison/events/forced_disconnections.csv",
    "results/model_comparison/events/summary.json",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original_probability(saving, current_positive, alternative_positive, params):
    """Analytical reconstruction of original ordered branches in either direction."""
    cheaper = saving > 0
    if current_positive == alternative_positive and cheaper:
        return params["p-switch-cost-only"]
    if current_positive and not cheaper:
        return params["p-switch-cost-despite-attitude"]
    if not current_positive and cheaper:
        return params["p-switch-all-factors"]
    if not current_positive:
        return params["p-switch-attitude"]
    return 0


def revised_probability(saving, current_positive, alternative_positive, params):
    z = (params["choice-cost-sensitivity"] * saving
         + params["choice-attitude-weight"] * (int(alternative_positive) - int(current_positive))
         - params["choice-switching-inertia"])
    e = np.exp(-abs(z))
    return 100 / (1 + e) if z >= 0 else 100 * e / (1 + e)


def model_legend(fig):
    handles = [plt.Line2D([], [], color=color, linestyle=ls, linewidth=.9, label=label)
               for _, label, color, ls in MODELS]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.12, .985), ncol=2, frameon=False)


def time_axis(ax, stop=1480):
    ax.set_xlim(0, stop)
    ax.set_xlabel("Time (model weeks)")
    ax.xaxis.set_major_locator(MaxNLocator(5, integer=True))


def percent_axis(ax, label):
    ax.set_ylim(-2, 102)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel(label)


def switching_figure(original_params, revised_params):
    fig, axes = plt.subplots(2, 2, figsize=(180 * MM, 150 * MM))
    cases = [(True, False, "Current positive; alternative negative"),
             (False, True, "Current negative; alternative positive"),
             (True, True, "Both providers positive"),
             (False, False, "Both providers negative")]
    tables = {}
    x = np.linspace(-3, 3, 601)
    for ax, letter, (current, alternative, title) in zip(axes.flat, "abcd", cases):
        original = np.array([original_probability(value, current, alternative, original_params) for value in x])
        revised = np.array([revised_probability(value, current, alternative, revised_params) for value in x])
        for mask in [x <= 0, x > 0]:
            ax.plot(x[mask], original[mask], color=ORIGINAL, ls="--", lw=.9)
        tie = original_probability(0, current, alternative, original_params)
        right = original_probability(1, current, alternative, original_params)
        ax.scatter([0], [right], facecolors="white", edgecolors=ORIGINAL, s=18, linewidths=.7, zorder=5)
        ax.scatter([0], [tie], color=ORIGINAL, s=15, zorder=6)
        ax.plot(x, revised, color=REVISED, lw=.9)
        ax.axvline(0, color="#B5B5B5", ls=":", lw=.5, zorder=0)
        ax.set_xlim(-3, 3)
        ax.set_xticks([-3, -1.5, 0, 1.5, 3])
        percent_axis(ax, "Probability of attempting switch (%)")
        ax.set_xlabel("Monthly saving / desired monthly spending\n(unitless; 1 = one month's desired spending)")
        panel(ax, letter, title)
        if letter == "a":
            ax.text(.05, .84, "Original falls to 0%\nwhen the alternative becomes cheaper",
                    transform=ax.transAxes, color=ORIGINAL, fontsize=6.2, va="top")
        tables[letter] = pd.DataFrame({"relative_saving": x, "current_positive": current,
                                      "alternative_positive": alternative,
                                      "original_probability_pct": original,
                                      "revised_probability_pct": revised})
        assert np.all(np.diff(revised) >= 0)
    model_legend(fig)
    fig.subplots_adjust(left=.12, right=.97, bottom=.13, top=.87, hspace=.78, wspace=.48)
    caption = ("Consistent switching responses replace contradictory conditional probabilities. "
        "a–d, Analytical evaluations of the coded rules for the four attitude combinations, conditional on an issue-triggered reconsideration. "
        "Positive values mean the alternative is cheaper. The horizontal axis is a unitless ratio to desired monthly electricity spending, not a percentage of the current bill: 1.5 means a saving equal to 150% of that spending reference. "
        "Original branches respond only to the sign of the price difference. Filled original symbols at zero show the actual equal-price value; open symbols show the cheaper-side limit. "
        "The revised logistic rule responds continuously to savings and respects current- and alternative-provider favorability. "
        "In a, the original paradoxically reduces switching from 20% to 0% when the alternative becomes cheaper. "
        "Revised cost sensitivity and attitude weight are one, and inertia is 2.2. These are uncalibrated assumptions, not estimated response curves. "
        "A selected attempt can still fail if no destination is reachable. Both-positive and both-negative revised responses coincide.")
    return "01_switching_rule", fig, tables, caption


def accounting_figure(energy, neighborhoods):
    fig, axes = plt.subplots(2, 2, figsize=(180 * MM, 150 * MM))
    ax = axes[0, 0]
    low = energy[energy["case"] == "below_capacity"]
    for model, label, color, ls in MODELS:
        frame = low[low.model == model]
        ax.plot(frame.step, frame.usage_after_consumption, color=color, ls=ls, marker="o", markersize=2.5)
    ax.axhline(20, color="#333333", ls=":", lw=.6)
    ax.text(11.7, 21, "Capacity", ha="right", va="bottom", fontsize=6)
    ax.set_xlabel("Controlled week")
    ax.set_ylabel("Reported pole use (kWh)")
    ax.set_ylim(-1, 34)
    ax.set_xlim(.6, 12.4)
    ax.set_xticks([1, 4, 8, 12])
    panel(ax, "a", "Below capacity: demand 10, limit 20")

    ax = axes[0, 1]
    high = energy[energy["case"] == "above_capacity"]
    for model, label, color, ls in MODELS:
        frame = high[high.model == model]
        ax.plot(frame.step, frame.overloaded.astype(int), color=color, ls=ls,
                marker="o", markersize=2.5, drawstyle="steps-mid")
    ax.set_xlabel("Controlled week")
    ax.set_ylabel("Pole state")
    ax.set_xlim(.6, 12.4)
    ax.set_xticks([1, 4, 8, 12])
    ax.set_ylim(-.15, 1.25)
    ax.set_yticks([0, 1], ["Available", "Outage"])
    panel(ax, "b", "Excess demand: 30, limit 20")

    ax = axes[1, 0]
    for model, label, color, ls in MODELS:
        frame = neighborhoods[neighborhoods.model == model].sort_values("radius")
        positions = np.arange(len(frame)) + (-.15 if model == "original" else .15)
        values = frame.households_missing_neighbors / frame.households * 100
        ax.barh(positions, values, height=.27, color=color)
        for y, value in zip(positions, values):
            if value == 0:
                ax.scatter(0, y, color=color, s=12, zorder=3, clip_on=False)
            ax.text(value + 2, y, f"{value:.1f}%" if value else "0%", va="center", fontsize=6.5, color=color)
    ax.set_yticks([0, 1], ["r = 2", "r = 3"])
    ax.set_xlabel("Households missing valid neighbors (%)")
    ax.set_xlim(-2, 103)
    ax.set_xticks([0, 25, 50, 75, 100])
    panel(ax, "c", "Neighborhood cache completeness")

    ax = axes[1, 1]
    cap = energy[energy["case"].isin(["direct_cap", "hook_cap"])]
    for model, label, color, ls in MODELS:
        frame = cap[cap.model == model].set_index("case").reindex(["direct_cap", "hook_cap"])
        positions = np.arange(2) + (-.16 if model == "original" else .16)
        ax.bar(positions, frame.usage_after_consumption, width=.28, color=color)
        for x, value in zip(positions, frame.usage_after_consumption):
            ax.text(x, value + .4, f"{value:g}", ha="center", fontsize=6.5)
    ax.axhline(13, color="#333333", ls=":", lw=.6)
    ax.set_ylabel("Informal delivery (kWh/week)")
    ax.set_xticks([0, 1], ["Service drop", "Hook-on"])
    ax.set_ylim(0, 23)
    ax.set_yticks([0, 5, 10, 13, 20])
    panel(ax, "d", "Same 13 kWh cap for both link types")
    model_legend(fig)
    fig.subplots_adjust(left=.12, right=.97, bottom=.12, top=.87, hspace=.75, wspace=.50)
    tables = {"a": low, "b": high, "c": neighborhoods, "d": cap}
    caption = ("Controlled checks demonstrate corrections to load accounting, neighborhoods and informal capacity. "
        "a, Fixed weekly demand of 10 kWh below a 20 kWh pole limit. Original reported use is an accumulator, producing false outages at weeks 4, 8 and 12; revised reported use is weekly delivered energy, with no outages. "
        "b, Fixed demand of 30 kWh above the same limit. Original outage flags alternate, whereas revised demand remains overloaded. "
        "Both energy fixtures hold connections and cash availability fixed and call only blackout and consumption procedures. "
        "c, Households with incomplete caches after seed-42 setup; r=2 is the safety radius and r=3 the hook-on radius. Revised caches contain every valid neighbor. "
        "d, Isolated informal sources facing 20 kWh weekly demand and a 13 kWh cap: the original hook-on exceeds the cap; the revision applies it consistently. "
        "These are exact computational diagnostics, not estimates of real-world reliability. Original accumulated use must not be interpreted as measured weekly delivery.")
    return "02_accounting_corrections", fig, tables, caption


def trajectories_figure(original, revised):
    fig, axes = plt.subplots(2, 2, figsize=(180 * MM, 145 * MM))
    columns = [("formal_households", "Formal connection", "Households (%)"),
               ("informal_households", "Informal connection", "Households (%)"),
               ("trust_kplc_pct", "Positive KPLC attitude", "Households positive (%)"),
               ("trust_ipd_pct", "Positive informal-provider attitude", "Households positive (%)")]
    tables = {}
    for ax, letter, (column, title, label) in zip(axes.flat, "abcd", columns):
        table = []
        for frame, (model, model_label, color, ls) in zip([original, revised], MODELS):
            values = frame[column] / frame.households * 100 if column.endswith("households") else frame[column]
            ax.plot(frame.tick, values, color=color, ls=ls, lw=.65)
            ax.scatter(frame.tick.iloc[-1], values.iloc[-1], color=color, s=10, clip_on=False, zorder=4)
            ax.annotate(f"{values.iloc[-1]:.2f}%", xy=(frame.tick.iloc[-1], values.iloc[-1]), xytext=(-3, 5),
                        textcoords="offset points", ha="right", color=color, fontsize=6.5,
                        bbox={"facecolor": "white", "edgecolor": "none", "pad": .6})
            table.append(pd.DataFrame({"model": model, "tick": frame.tick, "percentage": values}))
        percent_axis(ax, label)
        time_axis(ax)
        panel(ax, letter, title)
        tables[letter] = pd.concat(table, ignore_index=True)
    model_legend(fig)
    fig.subplots_adjust(left=.12, right=.97, bottom=.10, top=.87, hspace=.68, wspace=.48)
    caption = ("The combined revisions change access and attitude trajectories. "
        "a,b, Formal and informal household shares; informal combines service drops and hook-ons. "
        "c,d, Percentages with positive Boolean attitudes toward KPLC and informal providers. Curves show every recorded week without smoothing; labels give the final observations. "
        "Both runs use seed 42, 2,000 households and 100 poles, and begin with identical initial connection counts and attitude shares. "
        "The revised model ends with 19.8% formal access compared with 53.35% originally. "
        "These are consequences of combined changes in the switching kernel, neighborhoods, load accounting and caps, with uncalibrated revised weights. "
        "They do not identify each revision's effect or demonstrate improved empirical accuracy, welfare or equilibrium. "
        "A common initial seed does not impose identical subsequent random shocks after the paths diverge. There is one realization per model and no uncertainty band.")
    return "03_base_run_trajectories", fig, tables, caption


def logging_figure(churn, funnel, forced):
    fig = plt.figure(figsize=(180 * MM, 145 * MM))
    gs = fig.add_gridspec(2, 2, height_ratios=[.95, 1], hspace=.78, wspace=.50)
    ax = fig.add_subplot(gs[0, :])
    for model, label, color, ls in MODELS:
        ax.plot(churn.tick, churn[f"{model}_net_change_pct"], color=color, ls=ls, lw=.8)
    ax.set_ylabel("Households changing status (%)")
    ax.set_ylim(bottom=0)
    time_axis(ax, 52)
    panel(ax, "a", "Observed changes between adjacent weeks")

    ax = fig.add_subplot(gs[1, 0])
    funnel = funnel.set_index("event_kind").reindex(["voluntary-choice", "access-attempt"]).reset_index()
    categories = [("not_attempted", "No attempt", "#CCCCCC"),
                  ("blocked", "Attempt blocked", "#E69F00"),
                  ("successful", "Success", REVISED)]
    left = np.zeros(2)
    for col, label, color in categories:
        values = funnel[col] / funnel.evaluated * 100
        ax.barh([0, 1], values, left=left, height=.4, color=color, label=label)
        left += values
    ax.set_yticks([0, 1], ["Provider\nchoice", "Informal\nentry"])
    ax.set_ylim(1.65, -.55)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Share of evaluated decisions (%)")
    for i, n in enumerate(funnel.evaluated):
        ax.text(0, i + .32, f"n = {n:,}", va="top", fontsize=6.5, color="#555555")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, ncol=3, loc="lower left", bbox_to_anchor=(.12, .015), frameon=False, fontsize=6)
    panel(ax, "b", "Revised decisions and realized outcomes")

    ax = fig.add_subplot(gs[1, 1])
    visible = forced[forced.events > 0].copy()
    labels = {"host-loss-voluntary-switch": "Loss of host", "enforcement": "Enforcement"}
    ax.barh(np.arange(len(visible)), visible.events, height=.42, color=REVISED)
    ax.set_yticks(np.arange(len(visible)), [labels[x] for x in visible.reason])
    ax.invert_yaxis()
    ax.set_xlim(0, visible.events.max() * 1.16)
    ax.set_xlabel("Recorded forced disconnections")
    ax.xaxis.set_major_locator(MaxNLocator(4, integer=True))
    for i, value in enumerate(visible.events):
        ax.text(value + 12, i, f"{value:,}", va="center", fontsize=6.5)
    panel(ax, "c", "Revised forced losses")
    model_legend(fig)
    fig.subplots_adjust(left=.12, right=.97, bottom=.17, top=.87)
    caption = ("Decision logging distinguishes changes that aggregate counters conceal. "
        "a, Adjacent-week changes between formal, informal and unconnected states in the first 52 weeks. "
        "Original counts come from household transition records; revised counts reconstruct each household's first and last status per week from the event log. Weekly aggregate flows validate the reconstruction. "
        "Lower revised turnover is an outcome difference, not itself an improvement in realism. "
        "b, Revised evaluated provider choices and informal access opportunities, classified into no attempt, attempted but blocked, and successful connection. "
        "Of 3,878 voluntary attempts, 2,717 succeed; 1,161 cannot obtain a source. "
        "c, Revised forced losses are recorded separately: 623 dependent households lose a switching host and 65 lose supply through enforcement. "
        "The revised log also resolves 157 household-weeks with changes that return to the starting status. "
        "Original voluntary/forced event categories are unavailable, not zero. Panels b,c illustrate improved observability, not comparative causal effects. One seed per model; weeks 1–52.")
    return "04_changes_and_logging", fig, {"a": churn, "b": funnel, "c": forced}, caption


def export(output, figures, input_paths):
    fig_dir = output / "figures"
    source_dir = output / "source_data"
    fig_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"scope": "Controlled rule/probe comparisons and one seed-42 trajectory per model; revised weights uncalibrated", "width_mm": 180,
                "font": "Arial", "body_pt": 7, "panel_pt": 8, "raster_dpi": 300,
                "python": platform.python_version(), "matplotlib": matplotlib.__version__,
                "script_sha256": digest(__file__), "inputs": [{"path": p.resolve().relative_to(ROOT).as_posix() if p.resolve().is_relative_to(ROOT) else str(p.resolve()), "sha256": digest(p)} for p in input_paths], "figures": []}
    with PdfPages(fig_dir / "original_vs_revised.pdf") as combined:
        for name, fig, tables, caption in figures:
            fig.canvas.draw()
            bounds = fig.get_tightbbox(fig.canvas.get_renderer())
            assert bounds.x0 >= 0 and bounds.y0 >= 0 and bounds.x1 <= fig.get_figwidth() and bounds.y1 <= fig.get_figheight(), (name, bounds)
            fig.savefig(fig_dir / f"{name}.pdf", metadata={"Title": name})
            fig.savefig(fig_dir / f"{name}.svg")
            fig.savefig(fig_dir / f"{name}.png", dpi=300)
            fig.savefig(fig_dir / f"{name}_preview.png", dpi=180)
            with Image.open(fig_dir / f"{name}.png") as im:
                im.convert("RGB").save(fig_dir / f"{name}.tiff", compression="tiff_lzw", dpi=(300, 300))
            combined.savefig(fig)
            with pd.ExcelWriter(source_dir / f"{name}.xlsx", engine="openpyxl") as writer:
                for letter, data in tables.items():
                    data.to_csv(source_dir / f"{name}_panel_{letter}.csv", index=False)
                    data.to_excel(writer, sheet_name=f"panel_{letter}", index=False)
            assert len(caption.split()) < 250
            assert (fig_dir / f"{name}.tiff").stat().st_size < 10_000_000
            manifest["figures"].append({"name": name, "panels": list(tables), "size_mm": [180, round(fig.get_figheight() / MM, 2)],
                                       "caption": caption, "caption_words": len(caption.split()),
                                       "files": {ext: {"bytes": (fig_dir / f"{name}.{ext}").stat().st_size, "sha256": digest(fig_dir / f"{name}.{ext}")} for ext in ["pdf", "svg", "png", "tiff"]}})
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (output / "captions.md").write_text("# Original and revised model comparison legends\n\n" + "\n\n".join(f"**Figure {i + 1}.** {item[3]}" for i, item in enumerate(figures)) + "\n", encoding="utf-8")
    report(output, manifest)
    with zipfile.ZipFile(output / "comparison_figure_package.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in [fig_dir, source_dir]:
            for path in sorted(directory.iterdir()):
                if path.is_file() and not path.name.endswith("_preview.png"):
                    archive.write(path, path.relative_to(output))
        for filename in ["README.md", "captions.md", "figure_manifest.json", "events/summary.json", "events/provenance.json", "events/weekly_churn.csv", "events/logging_funnel.csv", "events/forced_disconnections.csv", "probes/validation.json", "probes/energy.csv", "probes/neighborhoods.csv"]:
            archive.write(output / filename, filename)
        for filename in ["scripts/plot_model_comparison.py", "scripts/collect_comparison_probes.py", "scripts/summarize_comparison_events.py", "scripts/plot_base_figures.py", "requirements-figures.txt"]:
            archive.write(ROOT / filename, f"code/{filename}")
        for path in input_paths[:7]:
            archive.write(path, "code/" + path.resolve().relative_to(ROOT).as_posix())
    print(json.dumps({"figures": 4, "output": str(output), "checks": "passed"}))


def report(output, manifest):
    summary = json.loads((output / "events/summary.json").read_text())
    text = f"""# Original and revised model comparison

Four figures distinguish verified computational corrections from changes in the seed-42 base trajectory. Original is gray and dashed; revised is blue and solid. Full legends are in [captions.md](captions.md).

1. **Switching responses.** The original current-positive/alternative-negative rule switches with 20% probability when the alternative is not cheaper, but 0% when cheaper. The revised logistic rule responds continuously and monotonically to savings and attitudes. Revised weights remain uncalibrated. The x-axis is unitless: monthly cost savings divided by desired monthly electricity spending. It is not the percentage reduction in the current bill. For a current bill of 1,000 and desired spending of 500, an alternative costing 985 saves 1.5% of the bill but appears at x=0.03; an alternative costing 250 appears at x=1.5.
2. **Accounting corrections.** Controlled fixed-demand networks expose false below-capacity outages and automatic recovery under persistent overload in the original. The revision removes both artifacts, applies the 13 kWh cap to hook-ons, and eliminates incomplete neighborhood caches. Original reported usage is an accumulator; revised reported usage is weekly delivery.
3. **Base-run trajectories.** Formal access ends at 53.35% originally and 19.8% after revision; positive KPLC attitudes end at 32.4% and 24.4%. These are combined-change outcomes, not evidence of better empirical fit or household welfare.
4. **Changes and logging.** The original first-52-week observed status-change rate is {summary['original_mean_weekly_status_change_pct']:.2f}% of households per week, versus {summary['revised_mean_weekly_status_change_pct']:.2f}% revised. The new log separates evaluated choices, failed attempts, successful connections and forced losses, including changes reversed within a week.

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
"""
    (output / "README.md").write_text(text, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/model_comparison")
    args = parser.parse_args()
    style()
    original = pd.read_csv(ROOT / INPUTS[0])
    revised = pd.read_csv(ROOT / INPUTS[3]).rename(columns={"ticks": "tick"})
    energy = pd.read_csv(args.output / "probes/energy.csv")
    energy["overloaded"] = energy.overloaded.map({True: True, False: False, "true": True, "false": False})
    assert energy.overloaded.notna().all()
    neighborhoods = pd.read_csv(args.output / "probes/neighborhoods.csv")
    churn = pd.read_csv(args.output / "events/weekly_churn.csv")
    funnel = pd.read_csv(args.output / "events/logging_funnel.csv")
    forced = pd.read_csv(args.output / "events/forced_disconnections.csv")
    assert list(original.tick) == list(revised.tick) == list(range(1481))
    shared = ["households", "poles", "formal_households", "informal_households", "unconnected_households", "trust_kplc_pct", "trust_ipd_pct"]
    assert np.allclose(original.loc[0, shared].to_numpy(float), revised.loc[0, shared].to_numpy(float))
    for data in [original, revised]:
        assert np.all(data.formal_households + data.informal_households + data.unconnected_households == data.households)
    assert json.loads((args.output / "probes/validation.json").read_text())["passed"]
    original_params = json.loads((ROOT / INPUTS[1]).read_text())["runs"][0]["parameters"]
    revised_params = json.loads((ROOT / INPUTS[4]).read_text())["runs"][0]["parameters"]
    figures = [switching_figure(original_params, revised_params), accounting_figure(energy, neighborhoods),
               trajectories_figure(original, revised), logging_figure(churn, funnel, forced)]
    input_paths = [ROOT / p for p in INPUTS]
    for index, relative in enumerate(["probes/energy.csv", "probes/neighborhoods.csv", "probes/validation.json", "events/weekly_churn.csv", "events/logging_funnel.csv", "events/forced_disconnections.csv", "events/summary.json"], 7):
        input_paths[index] = args.output / relative
    export(args.output, figures, input_paths)


if __name__ == "__main__":
    main()
