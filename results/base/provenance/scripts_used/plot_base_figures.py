"""Render four reproducible Nature Extended Data candidates from observed base data.

Run with a Python environment containing requirements-figures.txt. All summaries
describe one seed-42 realization; variability bars describe household heterogeneity.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import platform
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MM = 1 / 25.4
COLORS = {"Formal": "#0072B2", "Service drop": "#D55E00", "Hook-on": "#CC79A7", "Unconnected": "#A5A5A5"}
KPLC, IPD = COLORS["Formal"], COLORS["Service drop"]
ATTITUDE_COLORS = ["#009E73", KPLC, IPD, "#D1D1D1"]
TIME_COLORS = {0: "#737373", 52: "#E69F00", 1480: KPLC}
ACCESS_COLUMNS = ["formal_households", "service_drop_households", "hookon_households", "unconnected_households"]
CAPTIONS = {}
FIGURES = []
SOURCE = {}


def style():
    plt.rcParams.update({
        "font.family": "Arial", "font.size": 7, "axes.labelsize": 7,
        "axes.titlesize": 7, "axes.titleweight": "normal", "axes.linewidth": .6,
        "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
        "xtick.major.width": .5, "ytick.major.width": .5,
        "xtick.major.size": 2.5, "ytick.major.size": 2.5,
        "legend.fontsize": 6.5, "legend.frameon": False, "legend.handlelength": 1.8,
        "lines.linewidth": .8, "lines.markersize": 3,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": False, "pdf.fonttype": 42, "ps.fonttype": 42,
        "svg.fonttype": "none", "savefig.facecolor": "white",
        "figure.facecolor": "white", "text.color": "black", "axes.labelcolor": "black",
    })


def panel(ax, letter, title):
    ax.annotate(letter, xy=(0, 1), xycoords="axes fraction", xytext=(-18, 9), textcoords="offset points", fontsize=8, fontweight="bold", va="bottom", annotation_clip=False)
    ax.set_title(title, loc="left", pad=9)


def time_axis(ax, stop=1480):
    ax.set_xlim(0, stop)
    ax.set_xlabel("Time (model weeks)")
    ax.xaxis.set_major_locator(MaxNLocator(5, integer=True))


def percent_axis(ax, label):
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel(label)


def legend(ax, ncol=1, **kwargs):
    return ax.legend(ncol=ncol, borderaxespad=0, labelspacing=.3, columnspacing=1.1, **kwargs)


def remember(number, slug, fig, tables, caption):
    name = f"extended_data_{number:02d}_{slug}"
    FIGURES.append((name, fig))
    SOURCE[name] = tables
    CAPTIONS[name] = caption


def access_figure(a, transitions):
    fig = plt.figure(figsize=(180 * MM, 140 * MM))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.08], width_ratios=[1.14, 1], hspace=.68, wspace=.55)
    ax = fig.add_subplot(gs[0, :])
    shares = a[ACCESS_COLUMNS].to_numpy().T / a.households.to_numpy() * 100
    ax.stackplot(a.tick, *shares, colors=list(COLORS.values()), linewidth=0)
    percent_axis(ax, "Households (%)")
    time_axis(ax)
    panel(ax, "a", "Connection composition over the full run")
    ax.legend(list(COLORS), ncol=4, loc="lower left", bbox_to_anchor=(0, 1.21), frameon=False, borderaxespad=0)

    ax = fig.add_subplot(gs[1, 0])
    early = a[a.tick <= 52]
    for name, col in zip(COLORS, ACCESS_COLUMNS):
        ax.plot(early.tick, early[col] / early.households * 100, label=name, color=COLORS[name])
    percent_axis(ax, "Households (%)")
    time_axis(ax, 52)
    panel(ax, "b", "First 52 weeks")

    ax = fig.add_subplot(gs[1, 1])
    states = ["f", "i", "n"]
    counts = transitions.groupby(["from_status", "to_status"]).households.sum().unstack().reindex(index=states, columns=states)
    rates = counts.div(counts.sum(axis=1), axis=0) * 100
    ax.imshow(rates, cmap="Blues", vmin=0, vmax=100, aspect="equal")
    for y in range(3):
        for x in range(3):
            value = rates.iloc[y, x]
            ax.text(x, y, f"{value:.1f}%", ha="center", va="center", color="white" if value > 60 else "black", fontsize=7)
    ax.set_xticks(range(3), ["Formal", "Informal", "Unconnected"])
    ax.set_yticks(range(3), ["Formal", "Informal", "Unconnected"])
    ax.set_xlabel("Status next week")
    ax.set_ylabel("Status this week")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    panel(ax, "c", "Observed weekly transitions")
    fig.subplots_adjust(left=.10, right=.97, top=.84, bottom=.10)

    transition_table = counts.stack().rename("observations").reset_index()
    transition_table["row_percentage"] = rates.stack().to_numpy()
    remember(1, "access_dynamics", fig, {"a": a[["tick", "households", *ACCESS_COLUMNS]], "b": early[["tick", "households", *ACCESS_COLUMNS]], "c": transition_table},
        "Connection composition and household transitions in the base realization. "
        "a, Household shares in formal, direct informal service-drop, informal hook-on and unconnected states over 1,480 model weeks. "
        "b, The first 52 weeks without smoothing. c, Row-normalized transition frequencies between adjacent end-of-week formal, informal and unconnected states, pooled over weeks 1–1,480. "
        "The informal category combines service drops and hook-ons. Rows sum to 100%; diagonal cells denote unchanged observed status. "
        "Transitions are reconstructed from household states and do not use the model's mixed switch counter. Changes reversed within a week and changes between informal subtypes are not resolved. "
        "One realization, seed 42; 2,000 households and 100 poles. No uncertainty intervals are implied.")


def attitudes_figure(a, h):
    fig, axes = plt.subplots(2, 2, figsize=(180 * MM, 145 * MM))
    ax = axes[0, 0]
    ax.plot(a.tick, a.trust_kplc_pct, color=KPLC, label="KPLC", lw=.65)
    ax.plot(a.tick, a.trust_ipd_pct, color=IPD, label="IPD", lw=.65, ls="--")
    percent_axis(ax, "Positive attitude (%)")
    time_axis(ax)
    panel(ax, "a", "Provider attitudes")
    legend(ax, ncol=2, loc="upper right")
    ax = axes[0, 1]
    columns = ["like_both", "like_kplc_only", "like_ipd_only", "like_neither"]
    ax.stackplot(a.tick, *(a[col] / a.households * 100 for col in columns), colors=ATTITUDE_COLORS, linewidth=0)
    percent_axis(ax, "Households (%)")
    time_axis(ax)
    panel(ax, "b", "Joint attitude states")
    ax.legend(["Both", "KPLC only", "IPD only", "Neither"], ncol=2, loc="lower left", bbox_to_anchor=(0, 1.16), borderaxespad=0, columnspacing=.8)
    tables = {"a": a[["tick", "trust_kplc_pct", "trust_ipd_pct"]], "b": a[["tick", "households", *columns]]}
    for letter, tick, ax in zip(["c", "d"], [52, 1480], axes[1]):
        frame = h[h.tick == tick]
        rows = []
        labels = []
        for index, (state, name) in enumerate([("f", "Formal"), ("i", "Informal"), ("n", "Unconnected")]):
            group = frame[frame.status == state]
            pk = group.attitude_kplc.mean() * 100
            pi = group.attitude_ipd.mean() * 100
            ax.plot([pk, pi], [index, index], color="#BDBDBD", lw=.6)
            ax.scatter(pk, index, color=KPLC, s=17, marker="o", label="KPLC" if index == 0 else None, zorder=3)
            ax.scatter(pi, index, color=IPD, s=18, marker="s", label="IPD" if index == 0 else None, zorder=3)
            labels.append(name)
            ax.text(98, index + .19, f"n = {len(group):,}", ha="right", va="center", fontsize=6, color="#555555")
            rows.append({"tick": tick, "status": state, "households": len(group), "positive_kplc_pct": pk, "positive_ipd_pct": pi})
        ax.set_yticks(range(3), labels)
        ax.set_ylim(2.5, -.65)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_xlabel("Positive attitude (%)")
        panel(ax, letter, f"Attitudes after {tick:,} weeks")
        if tick == 52:
            legend(ax, ncol=2, loc="lower right")
        tables[letter] = pd.DataFrame(rows)
    fig.subplots_adjust(left=.12, right=.97, bottom=.10, top=.84, hspace=.68, wspace=.60)
    remember(2, "provider_attitudes", fig, tables,
        "Boolean provider attitudes and their association with connection status. "
        "a, Percentage of households with a positive KPLC or informal power distributor (IPD) attitude at every recorded week. "
        "b, The four joint attitude states, which partition the population. c,d, Positive attitudes conditional on end-of-week connection status at weeks 52 and 1,480; symbols show the complete observed group and n is the household count. "
        "Both attitudes are Boolean flags, not continuous trust scores. The selected blackout rule can reduce KPLC attitudes among formal and informal customers. "
        "These panels describe associations and do not isolate a causal effect of attitudes on provider choice. One seed-42 realization; no smoothing or confidence intervals.")


def reliability_figure(a, p):
    fig = plt.figure(figsize=(180 * MM, 145 * MM))
    gs = fig.add_gridspec(2, 2, height_ratios=[.85, 1.1], width_ratios=[1, 1], hspace=.65, wspace=.5)
    ax = fig.add_subplot(gs[0, :])
    ax.plot(a.tick, a.overloaded_poles / a.poles * 100, label="Poles overloaded", color="#7B3294", lw=.55)
    ax.plot(a.tick, a.blackout_phase_total_exposed / a.households * 100, label="Households exposed", color="#333333", ls="--", lw=.55)
    percent_axis(ax, "Affected population (%)")
    time_axis(ax)
    panel(ax, "a", "Outages in the implemented loading process")
    legend(ax, ncol=2, loc="upper right")

    ax = fig.add_subplot(gs[1, 0])
    raster = p[(p.tick >= 1) & (p.tick <= 104)].pivot(index="who", columns="tick", values="overloaded").sort_index()
    ax.imshow(raster.to_numpy(), interpolation="nearest", aspect="auto", cmap=ListedColormap(["#F2F2F2", "#7B3294"]), vmin=0, vmax=1, extent=[.5, 104.5, 100.5, .5])
    ax.set_xlabel("Time (model weeks)")
    ax.set_ylabel("Pole rank (creation order)")
    ax.set_xticks([1, 26, 52, 78, 104])
    ax.set_yticks([1, 25, 50, 75, 100])
    panel(ax, "b", "Outage timing across poles")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor="#7B3294", label="Overloaded"), Patch(facecolor="#F2F2F2", edgecolor="#BDBDBD", linewidth=.4, label="Available")], loc="lower left", bbox_to_anchor=(0, 1.15), ncol=2, borderaxespad=0)

    rates = p[p.tick > 0].groupby("who").overloaded.mean()
    active = rates[rates > 0]
    selected = int((active - active.median()).abs().sort_values(kind="stable").index[0])
    trace = p[(p.who == selected) & (p.tick <= 52)].copy()
    trace["usage_capacity_ratio"] = trace.usage / trace.capacity
    trace["start_week_ratio"] = trace.usage_capacity_ratio.shift(1)
    ax = fig.add_subplot(gs[1, 1])
    for tick in trace.loc[trace.overloaded, "tick"]:
        ax.axvspan(tick - .5, tick + .5, color="#E8E8E8", lw=0, zorder=0)
    ax.axhline(1, color="#555555", ls="--", lw=.6)
    ax.plot(trace.tick, trace.usage_capacity_ratio, color="#7B3294", marker="o", markersize=1.8, lw=.7)
    ax.set_ylabel("Accumulated use / pole capacity")
    time_axis(ax, 52)
    ax.set_ylim(0, max(2, trace.usage_capacity_ratio.max() * 1.2))
    panel(ax, "c", f"Loading and reset at pole {selected}")
    ax.text(.02, .97, "Shading: outage week", transform=ax.transAxes, va="top", fontsize=6.5)
    fig.subplots_adjust(left=.10, right=.97, bottom=.10, top=.88)
    raster_source = raster.reset_index().melt(id_vars="who", var_name="tick", value_name="overloaded")
    remember(3, "reliability_diagnostics", fig, {
        "a": a[["tick", "poles", "households", "overloaded_poles", "blackout_phase_formal_exposed", "blackout_phase_informal_exposed", "blackout_phase_total_exposed"]],
        "b": raster_source, "c": trace,
    },
        "Outage exposure and the pole-usage accumulator in the current implementation. "
        "a, Fractions of poles marked overloaded and households exposed to overloaded supply. Household exposure is captured immediately after the blackout check, before consumption, switching or enforcement, and is plotted at the completed week's tick. "
        "b, Outage flags for all 100 poles during weeks 1–104, ordered by pole identifier. c, End-of-week accumulated usage divided by capacity for an objectively selected pole during weeks 0–52; shading denotes outage weeks and the dashed line denotes capacity. "
        "The selected pole has an outage fraction closest to the median among poles that ever overload; ties use identifier order. "
        "Usage accumulates across weeks and is reset during outage handling. This is an implementation diagnostic, not an instantaneous power-flow calculation. "
        "One seed-42 realization; no smoothing. Initial exposure is zero before any go call.")


def affordability_figure(a, h):
    fig, axes = plt.subplots(2, 2, figsize=(180 * MM, 145 * MM))
    initial = h[h.tick == 0].copy().sort_values("income")
    initial["income_decile"] = pd.qcut(initial.income, 10, labels=False) + 1
    initial["income_quintile"] = pd.qcut(initial.income, 5, labels=False) + 1
    quintiles = initial.set_index("who").income_quintile
    h = h.copy()
    h["income_quintile"] = h.who.map(quintiles)
    initial["formal_repaid_ratio"] = initial.demand * initial.tariff / initial.desired_expense
    initial["formal_installment_ratio"] = (initial.demand * initial.tariff + 625) / initial.desired_expense
    initial["informal_ratio"] = initial.informal_fee / initial.desired_expense
    cost = initial.groupby("income_decile")[["formal_repaid_ratio", "formal_installment_ratio", "informal_ratio"]].median().reset_index()
    ax = axes[0, 0]
    ax.axhline(1, color="#555555", lw=.6, ls=":")
    ax.plot(cost.income_decile, cost.formal_installment_ratio, color=KPLC, marker="o", label="Formal + installment")
    ax.plot(cost.income_decile, cost.formal_repaid_ratio, color=KPLC, ls="--", marker="s", label="Formal, repaid")
    ax.plot(cost.income_decile, cost.informal_ratio, color=IPD, marker="^", label="Informal")
    ax.set_xlabel("Household income decile")
    ax.set_ylabel("Predicted cost / desired spending")
    ax.set_xticks([1, 2, 4, 6, 8, 10])
    ax.set_ylim(bottom=0)
    legend(ax, loc="upper right")
    panel(ax, "a", "Price assumptions across incomes")

    ax = axes[0, 1]
    access_rows = []
    for tick, marker in [(0, "o"), (52, "s"), (1480, "^")]:
        frame = h[h.tick == tick]
        grouped = frame.groupby("income_quintile").status.agg(lambda values: (values == "f").mean() * 100)
        ax.plot(grouped.index, grouped.values, color=TIME_COLORS[tick], marker=marker, label="Setup" if tick == 0 else f"{tick:,} weeks")
        for quintile, value in grouped.items():
            access_rows.append({"tick": tick, "income_quintile": quintile, "formal_pct": value, "households": 400})
    ax.set_xlabel("Household income quintile")
    ax.set_xticks(range(1, 6), ["1\nLowest", "2", "3", "4", "5\nHighest"])
    percent_axis(ax, "Formally connected (%)")
    ax.set_ylim(-2, 102)
    legend(ax, loc="upper left")
    panel(ax, "b", "Formal access across incomes")

    ax = axes[1, 0]
    installment_pct = a.formal_installments_due / a.formal_households * 100
    ax.plot(a.tick, installment_pct, color=KPLC, lw=.7)
    percent_axis(ax, "Formal households owing installments (%)")
    time_axis(ax)
    panel(ax, "c", "Remaining connection installments")

    ax = axes[1, 1]
    expense_rows = []
    for tick, offset, marker in [(52, -.07, "s"), (1480, .07, "^")]:
        frame = h[h.tick == tick].copy()
        frame["expense_share_pct"] = frame.expense / frame.income * 100
        grouped = frame.groupby("income_quintile").expense_share_pct.quantile([.25, .5, .75]).unstack()
        ax.errorbar(grouped.index + offset, grouped[.5], yerr=[grouped[.5] - grouped[.25], grouped[.75] - grouped[.5]], color=TIME_COLORS[tick], marker=marker, lw=.7, capsize=2, label=f"{tick:,} weeks")
        for quintile, row in grouped.iterrows():
            expense_rows.append({"tick": tick, "income_quintile": quintile, "q25_pct": row[.25], "median_pct": row[.5], "q75_pct": row[.75], "households": 400})
    desired = initial.groupby("income_quintile").apply(lambda frame: np.median(frame.desired_expense / frame.income) * 100, include_groups=False)
    ax.plot(desired.index, desired, color="#555555", lw=.7, ls="--", label="Desired median")
    ax.set_xlabel("Household income quintile")
    ax.set_ylabel("Monthly electricity spending (% of income)")
    ax.set_xticks(range(1, 6), ["1\nLowest", "2", "3", "4", "5\nHighest"])
    ax.set_ylim(bottom=0)
    legend(ax, loc="upper right")
    panel(ax, "d", "Realized spending and heterogeneity")
    fig.subplots_adjust(left=.11, right=.97, top=.90, bottom=.11, wspace=.48, hspace=.67)
    expense_source = pd.DataFrame(expense_rows)
    expense_source["desired_median_pct"] = expense_source.income_quintile.map(desired)
    remember(4, "affordability_and_income", fig, {
        "a": cost, "b": pd.DataFrame(access_rows), "c": a[["tick", "formal_households", "formal_installments_due"]], "d": expense_source,
    },
        "Price assumptions, connection installments and income differences in access and spending. "
        "a, Median predicted monthly cost divided by desired monthly electricity spending within initial income deciles (200 households each). Formal scenarios assume full demand, either with a 625-unit installment or after repayment; informal cost is the initial flat fee. The dotted line denotes desired spending. "
        "b, Formal access by fixed initial income quintile (400 households each), at setup and weeks 52 and 1,480. "
        "c, Fraction of currently formal households with outstanding installments. d, Month-end electricity expenditure as a fraction of income, across all households within each quintile. Symbols show medians; whiskers show interquartile ranges, not confidence intervals. The dashed line gives median desired spending. "
        "Weeks 52 and 1,480 both close a four-week billing month. Recorded expenses can include multiple connection arrangements within that month. "
        "These are descriptive differences within one seed-42 realization and do not identify causal effects of repayment or income.")


def save_outputs(output, data):
    figures = output / "figures"
    source = output / "source_data"
    figures.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": 42, "replicates": 1, "width_mm": 180, "font": "Arial", "body_font_pt": 7, "panel_font_pt": 8, "raster_dpi": 300, "python": platform.python_version(), "matplotlib": matplotlib.__version__, "pandas": pd.__version__, "plot_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "input_sha256": {filename: hashlib.sha256((data / filename).read_bytes()).hexdigest() for filename in ["aggregate.csv", "households.csv", "poles.csv", "transitions.csv"]}, "figures": []}
    with PdfPages(figures / "base_model_extended_data.pdf", metadata={"Title": "Base model diagnostic figures", "Subject": "Seed 42; single realization"}) as combined:
        for name, fig in FIGURES:
            fig.canvas.draw()
            bounds = fig.get_tightbbox(fig.canvas.get_renderer())
            assert bounds.x0 >= 0 and bounds.y0 >= 0 and bounds.x1 <= fig.get_figwidth() and bounds.y1 <= fig.get_figheight(), (name, bounds)
            fig.savefig(figures / f"{name}.pdf", metadata={"Title": name, "Creator": "Matplotlib; scripts/plot_base_figures.py"})
            fig.savefig(figures / f"{name}.svg")
            fig.savefig(figures / f"{name}.png", dpi=300)
            fig.savefig(figures / f"{name}_preview.png", dpi=180)
            with Image.open(figures / f"{name}.png") as im:
                im.convert("RGB").save(figures / f"{name}.tiff", compression="tiff_lzw", dpi=(300, 300))
            assert (figures / f"{name}.tiff").stat().st_size < 10_000_000
            combined.savefig(fig)
            tables = SOURCE[name]
            with pd.ExcelWriter(source / f"{name}.xlsx", engine="openpyxl") as writer:
                for letter, frame in tables.items():
                    frame.to_csv(source / f"{name}_panel_{letter}.csv", index=False)
                    frame.to_excel(writer, sheet_name=f"panel_{letter}", index=False)
            manifest["figures"].append({"name": name, "panels": list(tables), "size_mm": [180, round(fig.get_figheight() / MM, 3)], "caption_words": len(CAPTIONS[name].split()), "files": {ext: {"bytes": (figures / f"{name}.{ext}").stat().st_size, "sha256": hashlib.sha256((figures / f"{name}.{ext}").read_bytes()).hexdigest()} for ext in ["pdf", "svg", "png", "tiff"]}})
    (output / "captions.md").write_text("# Base model Extended Data figure legends\n\n" + "\n\n".join(f"**Extended Data Figure {index + 1}.** {caption}" for index, caption in enumerate(CAPTIONS.values())) + "\n", encoding="utf-8")
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(output / "base_model_figure_package.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for directory in [figures, source]:
            for path in sorted(directory.iterdir()):
                if path.is_file() and not path.name.endswith("_preview.png"):
                    archive.write(path, path.relative_to(output))
        for filename in ["captions.md", "figure_manifest.json", "report.md"]:
            path = output / filename
            if path.exists():
                archive.write(path, path.name)
        for filename in ["provenance.json", "validation.json"]:
            archive.write(data / filename, f"data/{filename}")
        for filename in ["key_insights.json", "benchmark/timing.json", "benchmark/timing.csv"]:
            path = output / filename
            if path.exists():
                archive.write(path, filename)
        for filename in ["aggregate.csv", "households.csv", "poles.csv", "income_quintiles.csv", "transitions.csv", "links.csv", "observer_patch.diff", "data_integrity.json"]:
            archive.write(data / filename, f"data/{filename}")
        for relative in ["scripts/benchmark_base.py", "scripts/collect_base_diagnostics.py", "scripts/plot_base_figures.py", "requirements-figures.txt", "run_model.py", "models/kenya_informal_settlements.nlogox", "experiments/base.json", "experiments/model.json", "outputs/base_run/results.csv", "outputs/base_full/results.csv"]:
            archive.write(ROOT / relative, f"code/{relative}")
    return manifest


def write_report(output, data, a, h, p, transitions):
    output.mkdir(parents=True, exist_ok=True)
    changed = int(transitions.loc[transitions.from_status != transitions.to_status, "households"].sum())
    total = int(transitions.households.sum())
    completed = a[a.tick > 0]
    initial = h[h.tick == 0].copy()
    quintile = pd.Series(pd.qcut(initial.income, 5, labels=False).to_numpy() + 1, index=initial.who)
    h = h.copy()
    h["quintile"] = h.who.map(quintile)
    final_quintiles = h[h.tick == 1480].groupby("quintile").status.agg(lambda values: (values == "f").mean() * 100).to_list()
    poorest_expenses = {}
    for tick in [52, 1480]:
        poor = h[(h.tick == tick) & (h.quintile == 1)]
        poorest_expenses[tick] = float((poor.expense / poor.income * 100).median())
    insights = {
        "formal_min_week": int(a.loc[a.formal_households.idxmin(), "tick"]),
        "formal_min_pct": float(a.formal_households.min() / 20),
        "informal_max_week": int(a.loc[a.informal_households.idxmax(), "tick"]),
        "informal_max_pct": float(a.informal_households.max() / 20),
        "observed_status_changes": changed,
        "household_week_observations": total,
        "observed_status_change_pct": changed / total * 100,
        "minimum_kplc_positive_pct": float(a.trust_kplc_pct.min()),
        "minimum_kplc_positive_week": int(a.loc[a.trust_kplc_pct.idxmin(), "tick"]),
        "mean_poles_overloaded_pct": float((completed.overloaded_poles / completed.poles * 100).mean()),
        "mean_household_outage_exposure_pct": float((completed.blackout_phase_total_exposed / completed.households * 100).mean()),
        "final_formal_access_pct_by_income_quintile": final_quintiles,
        "poorest_quintile_median_expense_pct": poorest_expenses,
        "final_formal_installments_due": int(a.iloc[-1].formal_installments_due),
    }
    (output / "key_insights.json").write_text(json.dumps(insights, indent=2) + "\n", encoding="utf-8")
    timing_path = output / "benchmark/timing.json"
    timing = json.loads(timing_path.read_text()) if timing_path.exists() else None
    provenance = json.loads((data / "provenance.json").read_text())
    runtime_text = "Baseline benchmark records were not present in this output directory."
    if timing:
        short, full = timing["summary"]["52"], timing["summary"]["1480"]
        runtime_text = f"""| Execution | Repeats | Median wall time | Observed range |
| --- | --- | --- | --- |
| Default base run, 52 ticks | {short['n']} | {short['median_seconds']:.2f} s | {short['min_seconds']:.2f}–{short['max_seconds']:.2f} s |
| Full model horizon, 1,480 ticks | {full['n']} | {full['median_seconds']:.2f} s | {full['min_seconds']:.2f}–{full['max_seconds']:.2f} s |

Fresh processes ran sequentially, headlessly, with one NetLogo thread and seed 42. Wall time includes Python and JVM startup, compilation, setup, simulation, and output writing. These are execution repeats of the same stochastic realization, not independent random seeds. All six endpoints reproduced the saved reference results. Hardware: {timing['environment']['cpu']}; NetLogo {timing['environment']['netlogo_version']}. Exact timings and environment details are in [timing.json](benchmark/timing.json)."""
    report = f"""# Base model runtime and diagnostic figures

Four candidate Extended Data figures describe the existing seed-42 base model over its full 1,480-tick horizon. They combine weekly observations, selected household cross-sections, and a diagnostic of the implemented outage process. One tick is approximately one model week; financial routines use four-week months.

## Runtime

{runtime_text}

The separately instrumented run took {provenance['observation_wall_seconds']:.2f} s, including startup and detailed observation exports. This is data-collection overhead, not the ordinary base runtime. All 13 reference metrics matched at ticks 52 and 1,480. [Validation](data/validation.json) and [observation provenance](data/provenance.json) record the checks and exact additions to the private model copy.

## Figure ideas and measured findings

1. **Connection composition and churn.** Formal access drops to {insights['formal_min_pct']:.1f}% at week {insights['formal_min_week']}, while informal access peaks at {insights['informal_max_pct']:.2f}% at week {insights['informal_max_week']}. Formal access ends at 53.35%. Across the full run, {changed:,} adjacent-week status changes represent {insights['observed_status_change_pct']:.2f}% of household-week observations. Changing aggregate composition therefore coexists with frequent household changes. The transition matrix excludes within-week reversals and informal subtype changes.
2. **Provider attitudes.** Positive KPLC attitudes reach {insights['minimum_kplc_positive_pct']:.1f}% at week {insights['minimum_kplc_positive_week']} and end at 32.4%; positive IPD attitudes end at 40.6%. Joint states and status-conditioned endpoints show that attitudes and current connection arrangements are associated. The model represents attitudes as Boolean flags; these observations do not isolate causal effects.
3. **Reliability and accumulated loading.** An average of {insights['mean_poles_overloaded_pct']:.2f}% of poles are overloaded across completed weeks, while {insights['mean_household_outage_exposure_pct']:.2f}% of households are exposed before consumption and connection changes. The pole raster and representative trace show repeated loading and resets. The implementation accumulates pole usage across weeks, so this figure must not be described as instantaneous electrical power flow.
4. **Affordability and income differences.** Predicted formal charges exceed desired spending across income groups even after repayment, while informal charges become relatively inexpensive at higher incomes. At the endpoint no currently formal household has installments due; formal access by income quintile is {', '.join(f'{value:.2f}%' for value in final_quintiles)}, lowest to highest. Access is nonmonotonic in income. The poorest quintile's median month-end electricity expenditure falls from {poorest_expenses[52]:.2f}% of income at week 52 to {poorest_expenses[1480]:.2f}% at week 1,480. These associations do not establish repayment as the cause of changing access.

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

Source model SHA256: `{provenance['source_sha256']}`. Each plotting input and the plotting script have their own SHA256 recorded in the figure manifest.
"""
    (output / "report.md").write_text(report, encoding="utf-8")


def validate_data(data, a, h, p, transitions):
    assert list(a.tick) == list(range(1481))
    assert np.all(a.formal_households + a.informal_households + a.unconnected_households == a.households)
    assert np.all(a[ACCESS_COLUMNS].sum(axis=1) == a.households)
    assert np.all(a[["like_both", "like_kplc_only", "like_ipd_only", "like_neither"]].sum(axis=1) == a.households)
    assert np.all(transitions.groupby("tick").households.sum() == 2000)
    assert len(p) == 148100
    assert np.all(p.groupby("tick").size() == 100)
    assert np.all(h.groupby("tick").size() == 2000)
    assert np.all(h.groupby("who")[["income", "demand", "x", "y"]].nunique().to_numpy() == 1)
    states = ["f", "i", "n"]
    aggregate_states = a[["formal_households", "informal_households", "unconnected_households"]].to_numpy()
    origins = transitions.groupby(["tick", "from_status"]).households.sum().unstack().reindex(columns=states)
    destinations = transitions.groupby(["tick", "to_status"]).households.sum().unstack().reindex(columns=states)
    assert np.array_equal(origins.to_numpy(), aggregate_states[:-1])
    assert np.array_equal(destinations.to_numpy(), aggregate_states[1:])
    q = pd.read_csv(data / "income_quintiles.csv")
    assert len(q) == 7405 and np.all(q.households == 400)
    assert np.all(q.groupby("tick").size() == 5)
    assert np.array_equal(q.groupby("tick").blackout_phase_exposed.sum().to_numpy(), a.blackout_phase_total_exposed.to_numpy())
    for tick in [52, 1480]:
        row = a[a.tick == tick].iloc[0]
        frame = h[h.tick == tick]
        for status, column in [("f", "formal_households"), ("i", "informal_households"), ("n", "unconnected_households")]:
            assert (frame.status == status).sum() == row[column]
    source = ROOT / "models/kenya_informal_settlements.nlogox"
    provenance = json.loads((data / "provenance.json").read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == provenance["source_sha256"]
    checks = {"passed": True, "aggregate_ticks": len(a), "pole_rows": len(p), "household_rows": len(h), "quintile_rows": len(q), "transition_rows": len(transitions), "checks": ["Consecutive ticks 0 through 1480", "100 poles and five 400-household quintiles per tick", "2000 households per selected snapshot", "Fixed household locations, incomes and demands", "Adjacent transition origin and destination totals match states", "Quintile and aggregate pre-switch outage exposure agree"], "source_sha256": provenance["source_sha256"]}
    (data / "data_integrity.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    patch = difflib.unified_diff(source.read_text(encoding="utf-8").splitlines(keepends=True), (data / "observed_model.nlogox").read_text(encoding="utf-8").splitlines(keepends=True), fromfile="models/kenya_informal_settlements.nlogox", tofile="observed_model.nlogox", n=2)
    (data / "observer_patch.diff").write_text("".join(patch), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "outputs/base_publication/data")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/base_publication")
    args = parser.parse_args()
    style()
    a = pd.read_csv(args.data / "aggregate.csv")
    h = pd.read_csv(args.data / "households.csv")
    p = pd.read_csv(args.data / "poles.csv")
    transitions = pd.read_csv(args.data / "transitions.csv")
    for col in ["attitude_kplc", "attitude_ipd"]:
        h[col] = h[col].map({True: True, False: False, "true": True, "false": False})
        assert h[col].notna().all()
    p["overloaded"] = p.overloaded.map({True: True, False: False, "true": True, "false": False})
    assert p.overloaded.notna().all()
    validate_data(args.data, a, h, p, transitions)
    access_figure(a, transitions)
    attitudes_figure(a, h)
    reliability_figure(a, p)
    affordability_figure(a, h)
    write_report(args.output, args.data, a, h, p, transitions)
    manifest = save_outputs(args.output, args.data)
    print(json.dumps({"figures": len(manifest["figures"]), "output": str(args.output), "all_source_data_checks_passed": True}))


if __name__ == "__main__":
    main()
