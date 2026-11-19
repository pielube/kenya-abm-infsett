"""Combine the four plain-language explanations and vector plots in an A4 PDF."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Affine2D
import pandas as pd
import json

import plot_model_comparison as comparison


ROOT = Path(__file__).resolve().parents[1]
MM = 1 / 25.4
POINTS_PER_MM = 72 / 25.4
BODY_SIZE = 10
LINE_HEIGHT = 13.3

SECTIONS = [
    (
        "1. More consistent switching decisions.",
        [
            ("We changed three things: how households decide to switch, how service problems are calculated, and how decisions are recorded.", False),
            ("Look at the top-left panel below. In the original model, a household that liked its current provider became less likely to switch when the alternative became cheaper: the gray line drops from 20% to zero.", False),
            ("The revised blue line removes that contradiction. A cheaper alternative makes switching more likely. Liking the alternative encourages switching; liking the current provider encourages staying. Decisions remain probabilistic.", False),
            ("On the horizontal axis, moving right means switching saves more money.", False),
            ("Axis clarification: the values are unitless. +1.5 means savings equal to 1.5 times desired monthly electricity spending, not a 1.5% reduction in the current bill.", False),
        ],
    ),
    (
        "2. Outages and nearby connections are calculated correctly.",
        [
            ("The four panels below show the clearest corrections:", False),
            ("a: A household uses 10 units each week, while the pole can handle 20. The original incorrectly accumulated past use—10, 20, 30—and caused an outage. The revised model checks each week separately.", True),
            ("b: When demand stays above capacity, the original repeatedly cleared the outage simply because no electricity had been delivered. The revised model keeps the pole overloaded while demand remains excessive.", True),
            ("c: Some households previously failed to ‘see’ nearby households because neighbor lists were built before everyone was positioned. The revised lists include all valid neighbors.", True),
            ("d: Hook-ons could previously exceed the informal connection limit. Both informal connection types now obey the same limit.", True),
        ],
    ),
    (
        "3. Those changes substantially alter the model’s story.",
        [
            ("In the revised run, informal supply remains much more common. By the end, roughly 20% of households have formal connections, compared with 53% in the original.", False),
            ("Attitudes also change because households experience different service problems and make different choices.", False),
            ("These differences show that the corrections matter. They do not yet tell us which trajectory better describes real households; the revised decision weights still need calibration.", False),
        ],
    ),
    (
        "4. We can now see what happened behind each connection change.",
        [
            ("Previously, the switching counter mixed several events together. The new log distinguishes:", False),
            ("A household deciding to switch.", True),
            ("A household trying but finding no reachable connection.", True),
            ("A household losing supply through enforcement.", True),
            ("A hooked-on household losing supply because its host switched.", True),
            ("Panel a shows fewer households moving between formal, informal and unconnected states in the revised run. Panels b–c show why recording separate events matters: wanting a different connection does not guarantee obtaining one, and losing a connection does not necessarily reflect a choice.", False),
        ],
    ),
]


def wrap_measured(text, renderer, width_pt, dpi):
    font = FontProperties(family="Arial", size=BODY_SIZE)
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        width = renderer.get_text_width_height_descent(candidate, font, ismath=False)[0] * 72 / dpi
        if current and width > width_pt:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def explanatory_page(fig, number):
    """Reposition existing vector artists into a plot rectangle on an A4 page."""
    original_height_mm = fig.get_figheight() / MM
    axes_boxes = [(ax, ax.get_position().frozen()) for ax in fig.axes]
    legend_boxes = [(legend, legend.get_bbox_to_anchor().transformed(fig.transFigure.inverted()).frozen())
                    for legend in fig.legends]
    fig.set_size_inches(210 * MM, 297 * MM)
    left, bottom = 15 / 210, 14 / 297
    width, height = 180 / 210, original_height_mm / 297
    for ax, box in axes_boxes:
        ax.set_position([left + width * box.x0, bottom + height * box.y0,
                         width * box.width, height * box.height])
    plot_transform = Affine2D().scale(width, height).translate(left, bottom) + fig.transFigure
    for legend, box in legend_boxes:
        legend.set_bbox_to_anchor(box, transform=plot_transform)

    fig.text(15 / 210, 1 - 14 / 297, "Understanding the model revisions", fontsize=15,
             fontweight="bold", va="top", color="#133C55")
    title, paragraphs = SECTIONS[number - 1]
    fig.text(15 / 210, 1 - 27 / 297, title, fontsize=12, fontweight="bold", va="top")
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    y_pt = 297 * POINTS_PER_MM - 39 * POINTS_PER_MM
    for text, bullet in paragraphs:
        indent = 10 if bullet else 0
        lines = wrap_measured(text, renderer, 180 * POINTS_PER_MM - indent, fig.dpi)
        if bullet:
            fig.text(15 / 210, y_pt / (297 * POINTS_PER_MM), "•", fontsize=BODY_SIZE, va="top")
        for line in lines:
            fig.text((15 * POINTS_PER_MM + indent) / (210 * POINTS_PER_MM),
                     y_pt / (297 * POINTS_PER_MM), line, fontsize=BODY_SIZE, va="top")
            y_pt -= LINE_HEIGHT
        y_pt -= 5 if not bullet else 3
    text_bottom_mm = (y_pt + LINE_HEIGHT) / POINTS_PER_MM
    plot_top_mm = 14 + original_height_mm
    assert text_bottom_mm > plot_top_mm + 3, (number, text_bottom_mm, plot_top_mm)
    fig.text(15 / 210, 8 / 297, "Original model and revised model · Seed 42", fontsize=8, color="#555555")
    fig.text(195 / 210, 8 / 297, f"{number} / 4", fontsize=8, color="#555555", ha="right")
    fig.canvas.draw()
    bbox = fig.get_tightbbox(fig.canvas.get_renderer())
    assert bbox.x0 >= 0 and bbox.y0 >= 0 and bbox.x1 <= fig.get_figwidth() and bbox.y1 <= fig.get_figheight(), bbox
    return fig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "results/model_comparison/model_comparison_explained.pdf")
    parser.add_argument("--previews", action="store_true", help="Also save PNG pages for visual inspection")
    args = parser.parse_args()
    comparison.style()
    data = ROOT / "results/model_comparison"
    original = pd.read_csv(ROOT / comparison.INPUTS[0])
    revised = pd.read_csv(ROOT / comparison.INPUTS[3]).rename(columns={"ticks": "tick"})
    energy = pd.read_csv(data / "probes/energy.csv")
    energy["overloaded"] = energy.overloaded.map({True: True, False: False, "true": True, "false": False})
    neighborhoods = pd.read_csv(data / "probes/neighborhoods.csv")
    original_params = json.loads((ROOT / comparison.INPUTS[1]).read_text())["runs"][0]["parameters"]
    revised_params = json.loads((ROOT / comparison.INPUTS[4]).read_text())["runs"][0]["parameters"]
    figures = [
        comparison.switching_figure(original_params, revised_params),
        comparison.accounting_figure(energy, neighborhoods),
        comparison.trajectories_figure(original, revised),
        comparison.logging_figure(pd.read_csv(data / "events/weekly_churn.csv"),
                                  pd.read_csv(data / "events/logging_funnel.csv"),
                                  pd.read_csv(data / "events/forced_disconnections.csv")),
    ]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    previews = args.output.parent / "explained_pdf_previews"
    if args.previews:
        previews.mkdir(exist_ok=True)
    metadata = {"Title": "Understanding the model revisions", "Subject": "Four plain-language explanations with original-versus-revised plots", "Author": "Kenya informal settlements model project"}
    with PdfPages(args.output, metadata=metadata) as pdf:
        for number, (_, fig, _, _) in enumerate(figures, 1):
            explanatory_page(fig, number)
            pdf.savefig(fig)
            if args.previews:
                fig.savefig(previews / f"page_{number:02d}.png", dpi=120)
            plt.close(fig)
    print(json.dumps({"pdf": str(args.output), "pages": 4, "plots": "vector", "explanations": "Four original explanations, with the clarified savings-axis note"}))


if __name__ == "__main__":
    main()
