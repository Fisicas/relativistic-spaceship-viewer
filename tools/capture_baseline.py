"""Capture and compare original numerical scenes without running its Tk GUI.

The source is obtained from the specified Git commit, or --legacy-source.
Only pure legacy functions and its catalog dataclass are evaluated. No source
from attachments or untrusted repositories should be supplied to this tool.
Outputs are exclusive-create: choose a new directory for every run.
"""
from __future__ import annotations
import argparse
import ast
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
from types import SimpleNamespace

import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.rendering import draw_scene
from spaceship_viewer.scene import compute_scene
from spaceship_viewer.state import ViewState

BASE_COMMIT = "0f4d46a7451f71969c3d90b9225703e64b1a691b"


def legacy_namespace(source):
    tree = ast.parse(source)
    allowed = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name != "main"
               or isinstance(node, ast.ClassDef) and node.name == "StarCatalog"]
    namespace = {"np": np, "math": math, "csv": csv, "dataclass": dataclass,
                 "Path": Path, "EPS": 1e-12}
    module = ast.Module(body=allowed, type_ignores=[])
    exec(compile(module, "legacy_reference", "exec"), namespace)
    viewer = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Viewer")
    update = next(n for n in viewer.body if isinstance(n, ast.FunctionDef) and n.name == "update_plot")
    update.name = "legacy_update_plot"
    namespace.update(HFOV_DEG=45., VFOV_DEG=45.)
    exec(compile(ast.Module(body=[update], type_ignores=[]), "legacy_renderer", "exec"), namespace)
    return namespace


def legacy_scene(ns, beta):
    cat = ns["built_in_catalog"]().limited(8.)
    fwd, east, north = ns["basis_from_radec"](84., -1.)
    apparent, doppler, mu = ns["aberrate"](cat.vectors, fwd, beta)
    z = apparent @ fwd
    x = -np.rad2deg(np.arctan2(apparent @ east, z))
    y = np.rad2deg(np.arctan2(apparent @ north, z))
    visible = (z > 0) & (np.abs(x) <= 22.5) & (np.abs(y) <= 22.5)
    mag_eff = ns["display_mag"](cat.vmag[visible], doppler[visible], True)
    return dict(apparent=apparent, doppler=doppler, mu=mu, x_deg=x, y_deg=y, visible=visible,
                display_magnitude=mag_eff, marker_area_pt2=ns["marker_sizes"](mag_eff),
                rgb=ns["temperature_to_rgb"](ns["bv_to_temperature"](cat.bv[visible]) * doppler[visible]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-source", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    raw = args.legacy_source.read_bytes() if args.legacy_source else subprocess.check_output(
        ["git", "show", f"{BASE_COMMIT}:relativistic_spaceship_viewer.py"], cwd=ROOT)
    source = raw.decode("utf-8-sig")
    ns = legacy_namespace(source)
    old_catalog, new_catalog = ns["built_in_catalog"](), built_in_catalog()
    for field in ("name", "ra_deg", "dec_deg", "vmag", "bv", "distance_pc"):
        np.testing.assert_array_equal(getattr(old_catalog, field), getattr(new_catalog, field))
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / "original_source.py").write_bytes(raw)
    environment = {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                   "numpy": np.__version__, "matplotlib": matplotlib.__version__}
    report = {"baseline_commit": BASE_COMMIT, "legacy_source_sha256": hashlib.sha256(raw).hexdigest(),
              "environment": environment, "conventions": "docs/PHYSICS.md", "scenes": []}
    for label, beta in (("beta_0", 0.), ("beta_0_30", .30), ("beta_0_87", .87), ("gamma_2", math.sqrt(3.) / 2.)):
        state = ViewState(beta=beta)
        old = legacy_scene(ns, beta)
        new = compute_scene(built_in_catalog(), state)
        errors = {}
        for field, old_value in old.items():
            new_value = getattr(new, field)
            if field == "visible":
                np.testing.assert_array_equal(new_value, old_value)
                errors[field] = 0.
            else:
                np.testing.assert_allclose(new_value, old_value, rtol=2e-12, atol=2e-12)
                errors[field] = float(np.max(np.abs(new_value - old_value))) if old_value.size else 0.
        np.savez(out / f"{label}_original.npz", **old)
        report["scenes"].append({"label": label, "beta": beta, "gamma": 1 / math.sqrt(1 - beta * beta),
                                  "heading_ra_deg": 84., "heading_dec_deg": -1., "fov_deg": [45., 45.],
                                  "rest_vmag_limit": 8., "visible_names": new.candidates.name[new.visible].tolist(),
                                  "n_visible": new.n_visible, "max_abs_difference": errors,
                                  "display_modes": "legacy B-V->T->RGB, D^3 magnitude mapping, clipped markers, glow, labels"})
        if args.render:
            class Variable:
                def __init__(self, value):
                    self.value = value
                def get(self):
                    return self.value
                def configure(self, **kwargs):
                    pass

            legacy_fig = Figure(figsize=(8.8, 7.), dpi=100, facecolor="black")
            legacy_ax = legacy_fig.add_subplot(111)
            stub = SimpleNamespace(beta_var=Variable(beta), maglim_var=Variable(8.),
                                   ra_var=Variable(84.), dec_var=Variable(-1.),
                                   beta_label=Variable(None), maglim_label=Variable(None),
                                   catalog=old_catalog, catalog_title="Built-in bright-star demo catalog",
                                   doppler_bright_var=Variable(True), doppler_color_var=Variable(True),
                                   labels_var=Variable(True), glow_var=Variable(True),
                                   ax=legacy_ax, canvas=SimpleNamespace(draw_idle=lambda: None),
                                   status=Variable(None))
            ns["legacy_update_plot"](stub)
            legacy_canvas = FigureCanvasAgg(legacy_fig)
            legacy_canvas.draw()
            old_pixels = np.asarray(legacy_canvas.buffer_rgba()).copy()
            legacy_fig.savefig(out / f"{label}_baseline.png", dpi=100)
            fig = Figure(figsize=(8.8, 7.), dpi=100, facecolor="black")
            ax = fig.add_subplot(111)
            draw_scene(ax, new, state, "Built-in bright-star demo catalog")
            ax.set_xlabel("apparent horizontal angle from center, degrees  (right = celestial west)")
            ax.set_title("Forward view toward RA 84.00°, Dec -1.00°  |  Built-in bright-star demo catalog", fontsize=11)
            new_canvas = FigureCanvasAgg(fig)
            new_canvas.draw()
            new_pixels = np.asarray(new_canvas.buffer_rgba())
            report["scenes"][-1]["render_changed_pixels"] = int(np.any(old_pixels != new_pixels, axis=2).sum())
            report["scenes"][-1]["render_max_channel_difference"] = int(np.abs(old_pixels.astype(int) - new_pixels.astype(int)).max())
            fig.savefig(out / f"{label}_refactored_legacy_text.png", dpi=100)
    (out / "baseline_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
