"""Presentation settings do not change catalog selection or the Lorentz boost."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Presentation:
    comparison: bool = False
    grid: bool = True
    max_labels: int = 12
    marker_scale: float = .85
    selected_row: int | None = None

    def __post_init__(self):
        if type(self.max_labels) is not int or not 0 <= self.max_labels <= 40:
            raise ValueError('Label limit must be an integer in [0, 40].')
        if not math.isfinite(self.marker_scale) or not .1 <= self.marker_scale <= 3.:
            raise ValueError('Marker area scale must be in [0.1, 3].')
        if self.selected_row is not None and (type(self.selected_row) is not int or self.selected_row < 0):
            raise ValueError('Selected row must be a nonnegative catalog index or None.')
