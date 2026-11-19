"""Pure numerical scene calculation: catalog cut, boost, camera, display mapping."""
from dataclasses import dataclass
import numpy as np
from .catalog import StarCatalog
from .display import bv_to_temperature, temperature_to_rgb, display_mag, marker_sizes
from .geometry import project_directions
from .relativity import aberrate
from .state import ViewState


@dataclass(frozen=True)
class ComputedScene:
    candidates: StarCatalog
    apparent: np.ndarray
    doppler: np.ndarray
    mu: np.ndarray
    x_deg: np.ndarray
    y_deg: np.ndarray
    visible: np.ndarray
    display_magnitude: np.ndarray
    marker_area_pt2: np.ndarray
    rgb: np.ndarray

    @property
    def n_visible(self):
        return int(self.visible.sum())


def compute_scene(catalog: StarCatalog, state: ViewState) -> ComputedScene:
    # The limit is on REST V magnitudes, before boosting. It does not predict
    # observed detectability or include objects absent from the source catalog.
    cat = catalog.limited(state.rest_mag_limit)
    apparent, doppler, mu = aberrate(cat.vectors, state.velocity_direction, state.beta)
    x, y, visible = project_directions(apparent, state.camera, state.hfov_deg, state.vfov_deg)
    mag_eff = display_mag(cat.vmag[visible], doppler[visible], state.illustrative_brightness)
    temp = bv_to_temperature(cat.bv[visible])
    if state.doppler_colors:
        temp = temp * doppler[visible]
    return ComputedScene(cat, apparent, doppler, mu, x, y, visible, mag_eff,
                         marker_sizes(mag_eff), temperature_to_rgb(temp))
