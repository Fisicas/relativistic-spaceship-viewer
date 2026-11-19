"""Catalog loading with explicit units, preserved row order, and import reports."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import io
from pathlib import Path
import numpy as np
from .geometry import radec_to_unit, finite_scalar


@dataclass(frozen=True)
class RowIssue:
    line: int
    reason: str


@dataclass(frozen=True)
class ImportReport:
    total_rows: int
    accepted_rows: int
    rejected: tuple[RowIssue, ...] = ()
    notes: tuple[str, ...] = ()

    def summary(self):
        text = [f"Accepted {self.accepted_rows} of {self.total_rows} data rows; rejected {len(self.rejected)}."]
        text.extend(self.notes)
        text.extend(f"Line {row.line}: {row.reason}" for row in self.rejected[:8])
        if len(self.rejected) > 8:
            text.append(f"{len(self.rejected) - 8} more rejected rows are recorded in import_report.")
        return "\n".join(text)


@dataclass(frozen=True)
class CatalogMetadata:
    source: str = "unspecified"
    source_sha256: str | None = None
    coordinate_frame: str = "unspecified equatorial frame"
    coordinate_epoch: str = "unspecified"
    magnitude_system: str = "V magnitude assumed by schema; calibration unspecified"
    retrieved_utc: str | None = None
    selection: str = "none declared; completeness unknown"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class StarCatalog:
    name: np.ndarray
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    vmag: np.ndarray
    bv: np.ndarray
    distance_pc: np.ndarray
    metadata: CatalogMetadata = field(default_factory=CatalogMetadata)
    import_report: ImportReport | None = None
    object_kind: np.ndarray | None = None

    def __post_init__(self):
        arrays = {}
        for name in ("name", "ra_deg", "dec_deg", "vmag", "bv", "distance_pc"):
            value = np.array(getattr(self, name), dtype=str if name == "name" else float, copy=True)
            if value.ndim != 1:
                raise ValueError(f"{name} must be one-dimensional.")
            arrays[name] = value
        if len({len(a) for a in arrays.values()}) != 1:
            raise ValueError("Catalog columns must have equal lengths.")
        radec_to_unit(arrays["ra_deg"], arrays["dec_deg"])
        if not np.all(np.isfinite(arrays["vmag"])):
            raise ValueError("Catalog V magnitudes must be finite.")
        if np.any(np.isinf(arrays["bv"])):
            raise ValueError("B-V must be finite or NaN (unknown).")
        distance = arrays["distance_pc"]
        if np.any(np.isinf(distance)) or np.any(distance[np.isfinite(distance)] <= 0):
            raise ValueError("Distances must be positive parsecs or NaN (unknown).")
        arrays["ra_deg"] %= 360.
        kind = np.full(len(distance), "star", dtype="U24") if self.object_kind is None else np.array(self.object_kind, dtype=str, copy=True)
        if kind.shape != distance.shape:
            raise ValueError("object_kind must have one entry per catalog object.")
        arrays["object_kind"] = kind
        for name, value in arrays.items():
            value.flags.writeable = False
            object.__setattr__(self, name, value)

    @property
    def n(self):
        return len(self.name)

    @property
    def vectors(self):
        return radec_to_unit(self.ra_deg, self.dec_deg)

    def limited(self, maglim):
        mask = self.vmag <= finite_scalar(maglim, "rest-frame V magnitude limit")
        return StarCatalog(*(getattr(self, name)[mask] for name in
                             ("name", "ra_deg", "dec_deg", "vmag", "bv", "distance_pc")),
                           metadata=self.metadata, import_report=self.import_report,
                           object_kind=self.object_kind[mask])


class UnitRequiredError(ValueError):
    def __init__(self, keyword, choices, column):
        self.keyword, self.choices = keyword, choices
        super().__init__(f"Column '{column}' requires {keyword}={choices}. No units are inferred from values.")


class CatalogImportError(ValueError):
    def __init__(self, message, report):
        self.report = report
        super().__init__(message + "\n" + report.summary())


def load_csv(path, *, ra_unit=None, distance_unit=None, parallax_unit=None,
             coordinate_frame="unspecified equatorial frame", coordinate_epoch="unspecified"):
    """Read without sorting, deduplication, smoothing, or numerical unit guesses.

    ra_deg or ra_hours declare RA units. Generic ra/raj2000 require ra_unit
    'deg' or 'hour'. Declination columns are degrees by this schema. Distances
    use distance_pc or generic dist/distance with distance_unit='pc'. Parallax
    uses parallax_mas/parallax_arcsec or generic parallax with an explicit unit.
    Positive parallax is inverted geometrically; this is not a distance estimator
    with uncertainty treatment. Missing or invalid optional values remain NaN.
    """
    path = Path(path)
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")
    if any(not c.strip() for c in reader.fieldnames):
        raise ValueError("CSV column names must not be empty.")
    fields = {c.strip().lower(): c for c in reader.fieldnames}
    if len(fields) != len(reader.fieldnames):
        raise ValueError("CSV has duplicate column names after case/space normalization.")

    def column(*choices):
        found = [fields[c] for c in choices if c in fields]
        if len(found) > 1:
            raise ValueError(f"Ambiguous columns {found}; keep one explicit column per quantity.")
        return found[0] if found else None

    def unit(explicit, supplied, choices, keyword, col):
        if supplied is not None and supplied not in choices:
            raise ValueError(f"{keyword} must be one of {choices}.")
        if explicit is not None and supplied is not None and explicit != supplied:
            raise ValueError(f"{keyword} conflicts with explicit unit in '{col}'.")
        answer = explicit or supplied
        if answer is None:
            raise UnitRequiredError(keyword, choices, col)
        return answer

    ra_c = column("ra_deg", "ra_hours", "ra_h", "ra", "raj2000")
    dec_c = column("dec_deg", "dec", "dej2000")
    mag_c = column("mag", "vmag", "v_mag", "v")
    bv_c = column("bv", "b-v", "ci", "color_index")
    name_c = column("name", "proper", "hip", "id")
    dist_c = column("distance_pc", "dist", "distance")
    plx_c = column("parallax_mas", "parallax_arcsec", "parallax")
    if not ra_c or not dec_c or not mag_c:
        raise ValueError("CSV must contain RA, declination in degrees, and V magnitude columns.")
    if dist_c and plx_c:
        raise ValueError("Both distance and parallax are present; choose one column explicitly before import.")
    ra_key = ra_c.strip().lower()
    ra_units = unit("deg" if ra_key == "ra_deg" else "hour" if ra_key in ("ra_hours", "ra_h") else None,
                    ra_unit, ("deg", "hour"), "ra_unit", ra_c)
    if dist_c:
        unit("pc" if dist_c.strip().lower() == "distance_pc" else None, distance_unit,
             ("pc",), "distance_unit", dist_c)
    plx_units = None
    if plx_c:
        key = plx_c.strip().lower()
        plx_units = unit("mas" if key == "parallax_mas" else "arcsec" if key == "parallax_arcsec" else None,
                         parallax_unit, ("mas", "arcsec"), "parallax_unit", plx_c)

    rows, rejected = [], []
    total = missing_bv = unknown_distance = invalid_optional = wrapped = 0

    def optional(row, key):
        nonlocal invalid_optional
        if key is None or row.get(key) is None or not row[key].strip():
            return np.nan
        try:
            value = float(row[key])
            if not np.isfinite(value):
                raise ValueError
            return value
        except (TypeError, ValueError):
            invalid_optional += 1
            return np.nan

    for row in reader:
        total += 1
        try:
            if None in row or any(row.get(c) is None for c in (ra_c, dec_c, mag_c)):
                raise ValueError("row has missing or extra cells")
            ra, dec, mag = (float(row[c]) for c in (ra_c, dec_c, mag_c))
            if not np.all(np.isfinite([ra, dec, mag])):
                raise ValueError("RA, Dec, and magnitude must be finite")
            if not -90 <= dec <= 90:
                raise ValueError("declination outside [-90, 90] degrees")
        except (TypeError, ValueError) as exc:
            rejected.append(RowIssue(reader.line_num, str(exc)))
            continue
        ra *= 15. if ra_units == "hour" else 1.
        if not np.isfinite(ra):
            rejected.append(RowIssue(reader.line_num, "RA unit conversion overflow"))
            continue
        wrapped += int(not 0 <= ra < 360)
        bv = optional(row, bv_c)
        missing_bv += int(np.isnan(bv))
        distance = optional(row, dist_c or plx_c)
        if plx_c and np.isfinite(distance):
            if distance > 0:
                with np.errstate(over="ignore"):
                    distance = (1000. if plx_units == "mas" else 1.) / distance
                if not np.isfinite(distance):
                    invalid_optional += 1
                    distance = np.nan
            else:
                invalid_optional += 1
                distance = np.nan
        elif np.isfinite(distance) and distance <= 0:
            invalid_optional += 1
            distance = np.nan
        unknown_distance += int(np.isnan(distance))
        name = (row.get(name_c) or "").strip() if name_c else ""
        rows.append((name or f"star {total}", ra % 360., dec, mag, bv, distance))

    notes = [f"RA input: {ra_units}; output: degrees modulo 360; Dec: degrees.",
             f"{wrapped} accepted RA values wrapped modulo 360 degrees.",
             f"{missing_bv} accepted objects have unknown B-V; catalog stores NaN.",
             f"{unknown_distance} accepted objects have unknown distance (NaN).",
             f"{invalid_optional} invalid optional values marked unknown; required-column failures reject rows.",
             "Row order preserved; no deduplication; no uncertainty propagation or epoch propagation."]
    used = {c for c in (ra_c, dec_c, mag_c, bv_c, name_c, dist_c, plx_c) if c}
    ignored = [c for c in reader.fieldnames if c not in used]
    if ignored:
        notes.append(f"Unused columns (including any uncertainties) are not processed: {', '.join(ignored)}.")
    if plx_c:
        notes.append(f"Positive parallax ({plx_units}) inverted to parsecs; no parallax errors or distance prior used.")
    if dist_c:
        notes.append("Input distances interpreted as parsecs by explicit header or supplied unit.")
    report = ImportReport(total, len(rows), tuple(rejected), tuple(notes))
    if not rows:
        raise CatalogImportError("No usable rows found.", report)
    metadata = CatalogMetadata(source=str(path.resolve()), source_sha256=hashlib.sha256(raw).hexdigest(),
                               coordinate_frame=coordinate_frame, coordinate_epoch=coordinate_epoch,
                               notes=tuple(notes))
    return StarCatalog(*(np.array(c) for c in zip(*rows)), metadata=metadata, import_report=report)


def catalog_from_hipparcos_table(tab, max_vmag):
    """Adapt a fetched table; masked values stay unknown, never sentinel numbers."""
    def numeric(name):
        return np.ma.asarray(tab[name], dtype=float).filled(np.nan)
    ra, dec, mag, bv, plx = (numeric(k) for k in ("RAICRS", "DEICRS", "Vmag", "B-V", "Plx"))
    valid = np.isfinite(ra) & np.isfinite(dec) & (np.abs(dec) <= 90) & np.isfinite(mag)
    dist = np.full(len(plx), np.nan)
    np.divide(1000., plx, out=dist, where=np.isfinite(plx) & (plx > 0))
    dist[~np.isfinite(dist)] = np.nan
    names = np.array([f"HIP {h}" for h in tab["HIP"]])
    notes = ("Coordinates: ICRS, catalog epoch J1991.25; no proper motion propagation.",
             "Positive parallax inverted in mas to pc; no distance inference or uncertainty propagation.",
             "Unknown B-V and distance remain NaN; completeness is not certified.",
             "Live table is not cached by this adapter; save source separately for archival reproduction.")
    report = ImportReport(len(ra), int(valid.sum()), tuple(RowIssue(i + 1, "invalid required coordinate or magnitude")
                          for i in np.flatnonzero(~valid)), notes)
    if not valid.any():
        raise CatalogImportError("Hipparcos table has no usable rows.", report)
    metadata = CatalogMetadata(source="VizieR I/239/hip_main (ESA 1997)",
                               coordinate_frame="ICRS", coordinate_epoch="J1991.25 (TT)",
                               magnitude_system="Johnson V", retrieved_utc=datetime.now(timezone.utc).isoformat(),
                               selection=f"Vmag < {max_vmag}; server query limit, not apparent detection threshold",
                               notes=notes)
    return StarCatalog(names[valid], ra[valid], dec[valid], mag[valid], bv[valid], dist[valid],
                       metadata=metadata, import_report=report)


def fetch_hipparcos(max_vmag=8.):
    from astroquery.vizier import Vizier
    max_vmag = finite_scalar(max_vmag, "Hipparcos rest V magnitude limit")
    query = Vizier(columns=["HIP", "RAICRS", "DEICRS", "Vmag", "B-V", "Plx"], row_limit=-1)
    result = query.query_constraints(catalog="I/239/hip_main", Vmag=f"<{max_vmag}")
    if not result:
        raise RuntimeError("No Hipparcos result returned by VizieR.")
    return catalog_from_hipparcos_table(result[0], max_vmag)
