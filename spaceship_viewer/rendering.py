"""Matplotlib drawing kept separate from numerical state and GUI event handling."""
import numpy as np
from .scene import ComputedScene
from .state import ViewState


def draw_scene(ax, scene: ComputedScene, state: ViewState, catalog_title: str):
    x, y = scene.x_deg[scene.visible], scene.y_deg[scene.visible]
    sizes, colors = scene.marker_area_pt2, scene.rgb
    names = scene.candidates.name[scene.visible]
    distances = scene.candidates.distance_pc[scene.visible]
    ax.clear()
    ax.set_facecolor("black")
    for spine in ax.spines.values():
        spine.set_color("0.35")
    ax.tick_params(colors="0.65")
    ax.xaxis.label.set_color("0.75")
    ax.yaxis.label.set_color("0.75")
    ax.title.set_color("0.9")
    if len(x):
        if state.glow:
            ax.scatter(x, y, s=np.clip(sizes * 4.5, 2, 900), c=colors, alpha=.10, linewidths=0)
            ax.scatter(x, y, s=np.clip(sizes * 2., 1, 500), c=colors, alpha=.18, linewidths=0)
        ax.scatter(x, y, s=sizes, c=colors, alpha=.95, linewidths=0)
        if state.labels:
            for i in np.argsort(scene.display_magnitude)[:min(24, len(x))]:
                if sizes[i] < 1.:
                    continue
                distance = f" ({distances[i]:.0f} pc)" if np.isfinite(distances[i]) else ""
                ax.text(x[i] + .35, y[i] + .35, f"{names[i]}{distance}", color="0.82", fontsize=8, alpha=.85)
    ax.set_xlim(-state.hfov_deg / 2, state.hfov_deg / 2)
    ax.set_ylim(-state.vfov_deg / 2, state.vfov_deg / 2)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(color="0.18", linewidth=.5, alpha=.5)
    ax.set_xlabel("apparent horizontal angle from center, degrees  (right = camera west)")
    ax.set_ylabel("apparent vertical angle from center, degrees")
    ra, dec = state.camera.radec
    ax.set_title(f"Camera toward RA {ra:.2f}°, Dec {dec:.2f}°  |  {catalog_title}", fontsize=11)
