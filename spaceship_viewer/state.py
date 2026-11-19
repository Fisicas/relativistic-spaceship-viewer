"""Application state independent of Tk, Matplotlib, and catalog I/O."""
from dataclasses import dataclass, field, replace
import numpy as np
from .geometry import CameraPose, finite_scalar, radec_to_unit
from .relativity import validate_beta


@dataclass(frozen=True)
class ViewState:
    beta: float = 0.
    heading_ra_deg: float = 84.
    heading_dec_deg: float = -1.
    camera: CameraPose = field(default_factory=lambda: CameraPose.from_radec(84., -1.))
    camera_locked: bool = True
    hfov_deg: float = 45.
    vfov_deg: float = 45.
    rest_mag_limit: float = 8.
    doppler_colors: bool = True
    illustrative_brightness: bool = True
    labels: bool = True
    glow: bool = True

    def __post_init__(self):
        beta = validate_beta(self.beta)
        if beta < 0:
            raise ValueError("Application speed must be nonnegative; change heading instead.")
        object.__setattr__(self, "beta", beta)
        object.__setattr__(self, "heading_ra_deg", finite_scalar(self.heading_ra_deg, "heading RA") % 360.)
        object.__setattr__(self, "heading_dec_deg", finite_scalar(self.heading_dec_deg, "heading Dec"))
        radec_to_unit(self.heading_ra_deg, self.heading_dec_deg)
        finite_scalar(self.rest_mag_limit, "rest-frame magnitude limit")
        for fov in (self.hfov_deg, self.vfov_deg):
            if not 0 < finite_scalar(fov, "FOV") < 180:
                raise ValueError("FOV must be in (0, 180) degrees.")
        if self.camera_locked and not np.allclose(self.camera.forward, self.velocity_direction,
                                                   atol=2e-12, rtol=0.):
            raise ValueError("Locked camera must point along velocity heading.")

    @property
    def velocity_direction(self):
        return radec_to_unit(self.heading_ra_deg, self.heading_dec_deg)[0]

    def with_heading(self, ra_deg, dec_deg):
        camera = CameraPose.from_radec(ra_deg, dec_deg) if self.camera_locked else self.camera
        return replace(self, heading_ra_deg=ra_deg, heading_dec_deg=dec_deg, camera=camera)

    def with_lock(self, locked):
        camera = CameraPose.from_radec(self.heading_ra_deg, self.heading_dec_deg) if locked else self.camera
        return replace(self, camera_locked=bool(locked), camera=camera)

    def with_camera(self, camera):
        if self.camera_locked:
            ra, dec = camera.radec
            return replace(self, heading_ra_deg=ra, heading_dec_deg=dec, camera=camera)
        return replace(self, camera=camera)
