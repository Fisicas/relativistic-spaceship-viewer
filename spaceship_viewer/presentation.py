"""Presentation settings do not change catalog selection or the Lorentz boost."""
from dataclasses import dataclass
import math
from .targets import ReferenceTarget
from .solar import SolarSettings,solar_reference


@dataclass(frozen=True)
class Presentation:
    comparison: bool = False
    grid: bool = True
    max_labels: int = 12
    marker_scale: float = .85
    selected_row: int | None = None
    reference_target: ReferenceTarget | None = None
    solar: SolarSettings | None = None

    def __post_init__(self):
        if self.solar is not None and not isinstance(self.solar,SolarSettings):
            raise ValueError('Invalid solar settings.')
        if isinstance(self.reference_target,ReferenceTarget) and self.reference_target.object_kind=='solar_disk':
            # Metadata is saved provenance, including legacy neutral-disk notes.
            # Validate intrinsic target geometry, not wording from another version.
            fields=('name','ra_deg','dec_deg','vmag','bv','distance_pc','object_kind')
            if self.solar is None or any(getattr(self.reference_target,key)!=getattr(solar_reference(self.solar),key) for key in fields):
                raise ValueError('Solar reference must match its saved model geometry.')
        if self.reference_target is not None:
            if not isinstance(self.reference_target, ReferenceTarget) or self.selected_row is not None:
                raise ValueError('Select either a named reference or a loaded catalog row.')
        if type(self.max_labels) is not int or not 0 <= self.max_labels <= 40:
            raise ValueError('Label limit must be an integer in [0, 40].')
        if not math.isfinite(self.marker_scale) or not .1 <= self.marker_scale <= 3.:
            raise ValueError('Marker area scale must be in [0.1, 3].')
        if self.selected_row is not None and (type(self.selected_row) is not int or self.selected_row < 0):
            raise ValueError('Selected row must be a nonnegative catalog index or None.')
