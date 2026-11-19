"""Portable named navigation references, independent of the sky catalog."""
from dataclasses import dataclass
import numpy as np
from .catalog import StarCatalog, CatalogMetadata


@dataclass(frozen=True)
class ReferenceTarget:
    name: str
    ra_deg: float
    dec_deg: float
    vmag: float | None
    bv: float | None
    distance_pc: float | None
    object_kind: str
    metadata: CatalogMetadata

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name or not isinstance(self.object_kind, str):
            raise ValueError('Reference target needs a name and object kind.')
        if not isinstance(self.metadata, CatalogMetadata):
            raise ValueError('Reference target needs explicit catalog provenance.')
        if self.vmag is None and self.object_kind != 'solar_disk':
            raise ValueError('Only the non-photometric solar model may omit V magnitude.')
        self.as_catalog()  # Reuse the scientific catalog validation.

    @classmethod
    def from_catalog(cls, catalog, row):
        optional = lambda x: float(x) if np.isfinite(x) else None
        return cls(str(catalog.name[row]), float(catalog.ra_deg[row]), float(catalog.dec_deg[row]),
                   float(catalog.vmag[row]), optional(catalog.bv[row]), optional(catalog.distance_pc[row]),
                   str(catalog.object_kind[row]), catalog.metadata)

    @classmethod
    def from_dict(cls, value):
        value = dict(value)
        metadata = dict(value['metadata'])
        metadata['notes'] = tuple(metadata.get('notes', ()))
        value['metadata'] = CatalogMetadata(**metadata)
        return cls(**value)

    def as_catalog(self):
        # Solar magnitude is intentionally unknown; the zero is an internal
        # direction-adapter placeholder, never a rendered/measured magnitude.
        return StarCatalog([self.name], [self.ra_deg], [self.dec_deg], [0. if self.vmag is None else self.vmag],
                           [np.nan if self.bv is None else self.bv],
                           [np.nan if self.distance_pc is None else self.distance_pc],
                           metadata=self.metadata, object_kind=[self.object_kind])
