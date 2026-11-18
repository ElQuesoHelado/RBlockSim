#!/usr/bin/env python3
"""Generate the figures used in the RBlockSim reproduction report.

Only the successful reproduction folder (results_*_1) is used.  In
particular, performance figures are restricted to the thread counts that
actually completed on the 12-vCPU machine (1, 4 and 8).
"""

import json
import math
import os
import re
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
JSONS = ROOT / "reproduced" / "plots" / "plots_1" / "jsons"
PERF = ROOT / "reproduced" / "results_performance_1"
FIG8 = ROOT / "reproduced" / "results_figure_8_1"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)

SIZES = [100, 1000, 10000]
PERF_SIZES = [100, 1000, 10000, 50000]
VALID_THREADS = [1, 4, 8]

plt.rcParams.update(
    {
        "font.size": 8.5,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "legend.fontsize": 7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "lines.linewidth": 1.25,
        "lines.markersize": 3.2,
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "mathtext.fontset": "stix",
        "axes.grid": True,
        "grid.alpha": 0.30,
        "grid.linewidth": 0.45,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.08,
    }
)


# ---------------------------------------------------------------------------
# Data readers
# ---------------------------------------------------------------------------
def load_json(name):
    with open(JSONS / name) as fh:
        return json.load(fh)


def mining_rates(size):
    """Average observed mining rate for every attacker hash rate."""
    files = [
        f"{size}_51_c1.json",
        f"{size}_51_c2.json",
        f"{size}_selfish_c1_d1.json",
        f"{size}_selfish_c1_d2.json",
        f"{size}_selfish_c1_d3.json",
        f"{size}_selfish_c2_d1.json",
        f"{size}_selfish_c2_d2.json",
        f"{size}_selfish_c2_d3.json",
    ]
    by_hash = {}
    for fname in files:
        for run in load_json(fname):
            data = run["stats"]["data"]
            total = sum(row[2] for row in data)
            attacker = data[run["attack_info"]["attacker_id"]][2]
            hr = run["attack_info"]["attacker_hashpower"]
            by_hash.setdefault(hr, []).append(attacker / total if total else 0.0)
    xs = sorted(by_hash)
    ys = [sum(by_hash[x]) / len(by_hash[x]) for x in xs]
    return np.array(xs), np.array(ys)


def committed_fraction(data):
    """Most frequent (attacker blocks in main chain, main-chain height)."""
    counts = {}
    for row in data:
        key = (row[0], row[1])
        counts[key] = counts.get(key, 0) + 1
    (attacker_blocks, height), _ = max(counts.items(), key=lambda item: item[1])
    return attacker_blocks / height


def committed_51(size):
    out = {}
    for tol in (1, 2):
        by_hash = {}
        for run in load_json(f"{size}_51_c{tol}.json"):
            hr = run["attack_info"]["attacker_hashpower"]
            by_hash.setdefault(hr, []).append(committed_fraction(run["stats"]["data"]))
        xs = sorted(by_hash)
        out[tol] = (np.array(xs), np.array([np.mean(by_hash[x]) for x in xs]))
    return out


def committed_selfish(size):
    out = {}
    for tol in (1, 2):
        for depth in (1, 2, 3):
            by_hash = {}
            for run in load_json(f"{size}_selfish_c{tol}_d{depth}.json"):
                hr = run["attack_info"]["attacker_hashpower"]
                by_hash.setdefault(hr, []).append(committed_fraction(run["stats"]["data"]))
            xs = sorted(by_hash)
            out[(tol, depth)] = (
                np.array(xs),
                np.array([np.mean(by_hash[x]) for x in xs]),
            )
    return out


def success_selfish(size):
    out = {}
    for tol in (1, 2):
        for depth in (2, 3):
            by_hash = {}
            for run in load_json(f"{size}_selfish_c{tol}_d{depth}.json"):
                info = run["attack_info"]
                total = info["successful_conceals"] + info["failed_attacks"]
                # Same operational definition used by the original plotter:
                # normalised attacker blocks committed to the main chain.
                actual = sum(row[0] for row in run["stats"]["data"]) / (
                    info["depth"] * int(run["simulation_info"]["network_size"])
                )
                rate = actual / total if total else 0.0
                by_hash.setdefault(info["attacker_hashpower"], []).append(rate)
            xs = sorted(by_hash)
            out[(tol, depth)] = (
                np.array(xs),
                np.array([np.mean(by_hash[x]) for x in xs]),
            )
    return out


def read_performance():
    """Return times[size][interval][threads] and peaks[size][interval][threads]."""
    times = {}
    peaks = {}
    for size in PERF_SIZES:
        folder = PERF / f"results_{size}"
        times[size] = {}
        peaks[size] = {}
        for path in sorted(folder.glob("out_*.txt")):
            name = path.name
            wt = int(re.search(r"_w(\d+)_", name).group(1))
            interval = int(re.search(r"_bi(\d+)_", name).group(1))
            text = path.read_text(errors="ignore")
            match = re.search(r"Simulation completed in ([\d.]+) seconds", text)
            if not match:
                continue
            times[size].setdefault(interval, {})[wt] = float(match.group(1))
        ram_path = folder / f"RAM_usage_peaks_Bytes_{size}_abenchmark.json"
        with open(ram_path) as fh:
            ram = json.load(fh)
        for wt_str, intervals in ram.items():
            wt = int(wt_str)
            for interval, value in intervals.items():
                peaks[size].setdefault(int(interval), {})[wt] = value / 1024**3
    return times, peaks


def read_ram_history(size):
    folder = FIG8 / f"results_{size}"
    path = next(folder.glob("experiments_ran_metadata_and_RAM_*.json"))
    with open(path) as fh:
        record = json.load(fh)[0]
    history = np.array(record["RAM_history"], dtype=float) / 1024**3
    # Remove the allocator teardown tail: keep the last sample that is still
    # close to the steady-state peak, then renormalise progress to 0-100 %.
    peak = float(np.max(history))
    keep = np.where(history >= 0.95 * peak)[0]
    if len(keep):
        history = history[: keep[-1] + 1]
    x = np.linspace(0.0, 100.0, len(history))
    # Light smoothing so that the curve is readable at report scale.
    if len(history) >= 5:
        kernel = np.ones(5) / 5.0
        smooth = np.convolve(history, kernel, mode="same")
        smooth[:2] = history[:2]
        smooth[-2:] = history[-2:]
        history = smooth
    return x, history


def fmt_size(size):
    return f"{size:,}".replace(",", " ")


def r2_mae(x, y):
    y = np.asarray(y)
    x = np.asarray(x)
    ss_res = float(np.sum((y - x) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    return 1.0 - ss_res / ss_tot, float(np.mean(np.abs(y - x)))


# ---------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------
def shared_legend(fig, handles, labels, ncol=3, y=0.0):
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=ncol,
        frameon=True,
        bbox_to_anchor=(0.5, y),
        handlelength=2.2,
        columnspacing=1.2,
    )


def hide_inner_y(axes):
    for ax in axes[1:]:
        ax.tick_params(labelleft=False)


def shared_ylabel(fig, text, x=0.025, y=0.55):
    fig.text(x, y, text, rotation=90, va="center", ha="center", fontsize=9)


def style_panel(ax, title):
    ax.set_title(title, pad=3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_xticklabels(["0", "0.25", "0.5", "0.75", "1"])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])


# ---------------------------------------------------------------------------
# Figure 3: statistical validation
# ---------------------------------------------------------------------------
def figure_validation():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65), sharey=True)
    for ax, size in zip(axes, SIZES):
        x, y = mining_rates(size)
        r2, mae = r2_mae(x, y)
        ax.plot([0, 1], [0, 1], "--", color="0.55", lw=1.0, label="Esperado")
        ax.plot(x, y, "o-", color="#1f77b4", ms=2.4, lw=1.1, label="Observado")
        style_panel(ax, f"{fmt_size(size)} nodos")
        ax.text(
            0.04,
            0.96,
            f"$R^2={r2:.4f}$\nMAE $={mae:.4f}$",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=7.2,
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="0.8", lw=0.5),
        )
    shared_ylabel(fig, "Tasa de minería")
    fig.text(0.5, 0.17, "Tasa de hash", ha="center", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=2, y=-0.02)
    hide_inner_y(axes)
    fig.subplots_adjust(left=0.14, bottom=0.30, wspace=0.16)
    fig.savefig(OUT / "fig_validacion.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4a-c: 51 % attack
# ---------------------------------------------------------------------------
def figure_51():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.95), sharey=True)
    colors = {1: "#1f77b4", 2: "#ff7f0e"}
    for ax, size in zip(axes, SIZES):
        data = committed_51(size)
        ax.plot([0, 1], [0, 1], "--", color="0.55", lw=1.0, label="Esperado")
        for tol in (1, 2):
            x, y = data[tol]
            ax.plot(x, y, "o-", color=colors[tol], ms=2.0, lw=1.0, label=f"Tolerancia {tol}")
        style_panel(ax, f"{fmt_size(size)} nodos")
    shared_ylabel(fig, "% de bloques del atacante")
    fig.text(0.5, 0.17, "Potencia de hash del atacante", ha="center", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=3, y=-0.02)
    hide_inner_y(axes)
    fig.subplots_adjust(left=0.14, bottom=0.30, wspace=0.16)
    fig.savefig(OUT / "fig_51.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 4d-f: selfish mining, committed blocks
# ---------------------------------------------------------------------------
def figure_selfish_committed():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.95), sharey=True)
    styles = {
        (1, 1): ("#1f77b4", "o", "Tol. 1, prof. 1"),
        (1, 2): ("#ff7f0e", "x", "Tol. 1, prof. 2"),
        (1, 3): ("#2ca02c", "s", "Tol. 1, prof. 3"),
        (2, 1): ("#d62728", "v", "Tol. 2, prof. 1"),
        (2, 2): ("#9467bd", "^", "Tol. 2, prof. 2"),
        (2, 3): ("#8c564b", "D", "Tol. 2, prof. 3"),
    }
    for ax, size in zip(axes, SIZES):
        data = committed_selfish(size)
        ax.plot([0, 1], [0, 1], "-", color="0.55", lw=1.1, label="Esperado", zorder=1)
        for key, (color, marker, label) in styles.items():
            x, y = data[key]
            ax.plot(
                x,
                y,
                marker=marker,
                color=color,
                ms=2.2,
                lw=0.8,
                ls=(0, (1, 1)),
                label=label,
                zorder=2,
            )
        style_panel(ax, f"{fmt_size(size)} nodos")
    shared_ylabel(fig, "% de bloques del atacante")
    fig.text(0.5, 0.15, "Potencia de hash del atacante", ha="center", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=4, y=-0.04)
    hide_inner_y(axes)
    fig.subplots_adjust(left=0.14, bottom=0.33, wspace=0.16)
    fig.savefig(OUT / "fig_selfish_committed.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 5: selfish mining success rate
# ---------------------------------------------------------------------------
def figure_success():
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.95), sharey=True)
    styles = {
        (1, 2): ("#1f77b4", "Tol. 1, prof. 2"),
        (1, 3): ("#ff7f0e", "Tol. 1, prof. 3"),
        (2, 2): ("#2ca02c", "Tol. 2, prof. 2"),
        (2, 3): ("#d62728", "Tol. 2, prof. 3"),
    }
    for ax, size in zip(axes, SIZES):
        data = success_selfish(size)
        for key, (color, label) in styles.items():
            x, y = data[key]
            ax.plot(x, y, "-", color=color, lw=1.15, label=label)
        style_panel(ax, f"{fmt_size(size)} nodos")
    shared_ylabel(fig, "Tasa de éxito")
    fig.text(0.5, 0.17, "Potencia de hash del atacante", ha="center", fontsize=9)
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=4, y=-0.02)
    hide_inner_y(axes)
    fig.subplots_adjust(left=0.14, bottom=0.30, wspace=0.16)
    fig.savefig(OUT / "fig_selfish_success.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6: reproduced performance, only valid thread counts
# ---------------------------------------------------------------------------
def figure_performance(times):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.7), sharex=True)
    panels = [(100, axes[0, 0]), (1000, axes[0, 1]), (10000, axes[1, 0]), (50000, axes[1, 1])]
    for size, ax in panels:
        for interval, color, marker in ((13, "#1f77b4", "o"), (600, "#ff7f0e", "s")):
            xs = [t for t in VALID_THREADS if t in times[size].get(interval, {})]
            ys = [times[size][interval][t] for t in xs]
            ax.plot(xs, ys, marker=marker, color=color, lw=1.25, ms=3.5, label=f"BI = {interval} s")
        ax.set_yscale("log")
        ax.set_xticks(VALID_THREADS)
        ax.set_xlim(0.5, 9.5)
        ax.set_title(f"{fmt_size(size)} nodos")
        ax.grid(True, which="both", alpha=0.25, lw=0.4)
    axes[0, 0].legend(loc="best", fontsize=7)
    for ax in axes[1, :]:
        ax.set_xlabel("Número de hilos de trabajo")
    for ax in axes[:, 0]:
        ax.set_ylabel("Tiempo de ejecución (s)\nescala logarítmica")
    fig.subplots_adjust(hspace=0.30, wspace=0.22)
    fig.savefig(OUT / "fig_performance.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 6 vs paper: common thread counts
# ---------------------------------------------------------------------------
PAPER = {
    100: {13: [12.4, 7.26, 6.71], 600: [0.39, 0.29, 0.29]},
    1000: {13: [392.06, 158.63, 132.95], 600: [9.30, 4.53, 3.82]},
    10000: {13: [5965.97, 2102.57, 1339.27], 600: [141.56, 64.66, 49.81]},
}


def figure_performance_vs_paper(times):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.75), sharey=False)
    for ax, size in zip(axes, [100, 1000, 10000]):
        for interval, color in ((13, "#1f77b4"), (600, "#ff7f0e")):
            xs = [t for t in VALID_THREADS if t in times[size].get(interval, {})]
            ys = [times[size][interval][t] for t in xs]
            ax.plot(xs, ys, "o-", color=color, lw=1.25, ms=3.3, label=f"Reprod., BI {interval} s")
            ax.plot(
                VALID_THREADS,
                PAPER[size][interval],
                "s--",
                color=color,
                lw=1.0,
                ms=2.6,
                alpha=0.75,
                label=f"Artículo, BI {interval} s",
            )
        ax.set_yscale("log")
        ax.set_xticks(VALID_THREADS)
        ax.set_xlim(0.5, 9.5)
        ax.set_title(f"{fmt_size(size)} nodos")
        ax.set_xlabel("Número de hilos")
        ax.grid(True, which="both", alpha=0.25, lw=0.4)
    axes[0].set_ylabel("Tiempo de ejecución (s)\nescala logarítmica")
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=2, y=-0.02)
    fig.subplots_adjust(bottom=0.34, wspace=0.30)
    fig.savefig(OUT / "fig_performance_vs_paper.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 7: peak RAM, only valid thread counts
# ---------------------------------------------------------------------------
def figure_ram(peaks):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.65), sharey=True)
    colors = {100: "#1f77b4", 1000: "#2ca02c", 10000: "#9467bd", 50000: "#d62728"}
    markers = {100: "o", 1000: "s", 10000: "^", 50000: "D"}
    for ax, interval in zip(axes, (13, 600)):
        for size in PERF_SIZES:
            xs = [t for t in VALID_THREADS if t in peaks[size].get(interval, {})]
            ys = [peaks[size][interval][t] for t in xs]
            ax.plot(
                xs,
                ys,
                marker=markers[size],
                color=colors[size],
                lw=1.2,
                ms=3.4,
                label=f"{fmt_size(size)} nodos",
            )
        ax.set_yscale("log")
        ax.set_xticks(VALID_THREADS)
        ax.set_xlim(0.5, 9.5)
        ax.set_title(f"BI = {interval} s")
        ax.set_xlabel("Número de hilos de trabajo")
        ax.grid(True, which="both", alpha=0.25, lw=0.4)
    axes[0].set_ylabel("RAM máxima (GB)\nescala logarítmica")
    handles, labels = axes[0].get_legend_handles_labels()
    shared_legend(fig, handles, labels, ncol=4, y=-0.03)
    fig.subplots_adjust(bottom=0.33, wspace=0.10)
    fig.savefig(OUT / "fig_ram.pdf")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 8: aggregated RAM over simulation progress
# ---------------------------------------------------------------------------
def figure_ram_history():
    fig, ax = plt.subplots(figsize=(4.6, 3.2))
    colors = {1000: "#1f77b4", 10000: "#ff7f0e", 50000: "#2ca02c"}
    for size in (1000, 10000, 50000):
        x, y = read_ram_history(size)
        ax.plot(x, y, color=colors[size], lw=1.4, label=f"{fmt_size(size)} nodos")
    ax.set_xlabel("Progreso de la simulación (%)")
    ax.set_ylabel("Uso de RAM (GB)")
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.legend(loc="center right")
    fig.savefig(OUT / "fig_ram_history.pdf")
    plt.close(fig)


def main():
    times, peaks = read_performance()
    figure_validation()
    figure_51()
    figure_selfish_committed()
    figure_success()
    figure_performance(times)
    figure_performance_vs_paper(times)
    figure_ram(peaks)
    figure_ram_history()
    print("Figures written to", OUT)


if __name__ == "__main__":
    main()
