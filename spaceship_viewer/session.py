"""Portable JSON scenes: full catalog, exact camera triad, and display settings.

NaN optional catalog values are encoded as JSON null. No executable serialization
or network/source-path reads occur on load. The SHA-256 identifies the embedded
numeric catalog snapshot, distinct from a source CSV hash in its metadata.
"""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import numpy as np
from . import __version__
from .catalog import CatalogMetadata, ImportReport, RowIssue, StarCatalog
from .geometry import CameraPose
from .presentation import Presentation
from .state import ViewState
from .targets import ReferenceTarget
from .solar import SolarSettings

SCHEMA = 'relativistic-spaceship-viewer.scene/1'
NUMERIC_COLUMNS = ('ra_deg', 'dec_deg', 'vmag', 'bv', 'distance_pc')


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def catalog_payload(catalog):
    data = {name: [float(v) if np.isfinite(v) else None for v in getattr(catalog, name)] for name in NUMERIC_COLUMNS}
    data.update(name=catalog.name.tolist(), object_kind=catalog.object_kind.tolist())
    return {'columns': data, 'metadata': asdict(catalog.metadata),
            'import_report': asdict(catalog.import_report) if catalog.import_report else None}


def make_document(catalog, state, presentation, title='Saved catalog'):
    payload = catalog_payload(catalog)
    return {'schema': SCHEMA, 'application_version': __version__, 'catalog_title': str(title),
            'catalog_sha256': hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            'catalog': payload, 'view': asdict(state), 'presentation': asdict(presentation),
            'conventions': {'direction': 'observer_to_source', 'angles': 'degrees', 'distance': 'parsec',
                            'projection': 'independent_atan2_axes', 'screen_right': 'camera_west',
                            'filter': 'rest_frame_vmag_before_boost', 'uncertainty_propagation': False,
                            'radiometry': 'illustrative_BV_RGB_and_D3_marker_area'}}


def decode_document(document):
    if document.get('schema') != SCHEMA:
        raise ValueError('Unsupported scene schema.')
    payload = document['catalog']
    if hashlib.sha256(canonical_bytes(payload)).hexdigest() != document['catalog_sha256']:
        raise ValueError('Embedded catalog hash does not match; scene is incomplete or altered.')
    columns = payload['columns']
    metadata = dict(payload['metadata'])
    metadata['notes'] = tuple(metadata.get('notes', ()))
    report = payload.get('import_report')
    if report:
        report = ImportReport(report['total_rows'], report['accepted_rows'],
                              tuple(RowIssue(**r) for r in report['rejected']), tuple(report['notes']))
    catalog = StarCatalog(columns['name'], *(np.array(columns[key], dtype=float) for key in NUMERIC_COLUMNS),
                          metadata=CatalogMetadata(**metadata), import_report=report,
                          object_kind=columns['object_kind'])
    view = dict(document['view'])
    view['camera'] = CameraPose(**view['camera'])
    state = ViewState(**view)
    appearance = dict(document['presentation'])
    if appearance.get('solar') is not None:
        settings=dict(appearance['solar'])
        if 'radiometry_model' not in settings:
            # Preserve the neutral fill of 0.2.3 scenes until explicitly enabled.
            settings.setdefault('radiometry_enabled',False)
        appearance['solar'] = SolarSettings(**settings)
    if appearance.get('reference_target') is not None:
        appearance['reference_target'] = ReferenceTarget.from_dict(appearance['reference_target'])
    presentation = Presentation(**appearance)
    if presentation.selected_row is not None and presentation.selected_row >= catalog.n:
        raise ValueError('Selected object is outside the embedded catalog.')
    return catalog, state, presentation, str(document['catalog_title'])


def load_document(path):
    # Bound local JSON size to avoid accidentally treating a huge data file as a
    # scene. This is a usability limit, not a catalog scientific constraint.
    path = Path(path)
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError('Scene JSON exceeds the 100 MiB import limit.')
    document = json.loads(path.read_text(encoding='utf-8-sig'), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'Invalid JSON constant {x}')))
    return decode_document(document)


def save_document(path, catalog, state, presentation, title='Saved catalog'):
    document = make_document(catalog, state, presentation, title)
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
    return document
