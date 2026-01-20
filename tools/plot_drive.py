"""Quick look at one or two drives while tuning the core.

    fgsim run --family s_curve --seed 3 --frames a.csv
    fgsim run --family s_curve --seed 3 --build rc.json --frames b.csv
    fgsim scenario --family s_curve --seed 3 --geometry > sc.json
    python tools/plot_drive.py a.csv b.csv --scenario sc.json -o drive.png
"""
import argparse
import csv
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = {}
    for key in rows[0]:
        cols[key] = [float(r[key]) if r[key] != "" else float("nan") for r in rows]
    return cols


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames", nargs="+", help="telemetry CSV files from fgsim run --frames")
    ap.add_argument("--scenario", help="fgsim scenario --geometry output")
    ap.add_argument("-o", "--out", default="drive.png")
    args = ap.parse_args()

    fig, axes = plt.subplots(4, 1, figsize=(10, 12))
    ax_xy, ax_v, ax_cte, ax_steer = axes

    if args.scenario:
        with open(args.scenario) as f:
            geo = json.load(f)["geometry"]
        rx, ry = zip(*geo["route"])
        ax_xy.plot(rx, ry, color="0.7", lw=6, label="lane")
        if "map_route" in geo:
            mx, my = zip(*geo["map_route"])
            ax_xy.plot(mx, my, color="0.85", lw=2, ls="--", label="prior map")

    for path in args.frames:
        d = load(path)
        ax_xy.plot(d["x"], d["y"], label=path)
        ax_v.plot(d["t"], d["v"], label=f"{path} v")
        ax_v.plot(d["t"], d["v_ref"], ls=":", label=f"{path} v_ref")
        ax_cte.plot(d["s"], d["cte"], label=path)
        ax_steer.plot(d["t"], d["steer"], label=path)

    ax_xy.set_aspect("equal", adjustable="datalim")
    ax_xy.set_title("trajectory")
    ax_v.set_title("speed (m/s)")
    ax_cte.set_title("cross-track error (m) vs s")
    ax_steer.set_title("road-wheel angle (rad)")
    for ax in axes:
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(args.out, dpi=110)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
