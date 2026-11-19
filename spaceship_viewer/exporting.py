"""Versioned PNG/SVG/PDF exports with portable, hash-identified JSON scenes."""
from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import sys
import matplotlib
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
import numpy as np
from . import __version__
from .plotting import draw_figure
from .session import make_document
from .solar_radiometry import solar_image, summary as solar_summary


def versioned_directory(parent, stem):
    parent = Path(parent)
    parent.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r'[^\w .-]', '_', str(stem)).strip(' .')[:100] or 'scene'
    if stem.upper().split('.')[0] in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        stem = 'scene_' + stem
    for version in range(1, 100000):
        folder = parent / f'{stem}_v{version:02d}'
        try:
            folder.mkdir()
            return folder
        except FileExistsError:
            continue
    raise FileExistsError('Could not allocate a new export version.')


def export_scene(parent, stem, catalog, state, presentation, title, *, width=3840, height=2160,
                 dpi=240, formats=('png', 'svg', 'pdf')):
    """No existing result is replaced. Raster dimensions are exact, without tight cropping."""
    if type(width) is not int or type(height) is not int or not (640 <= width <= 7680 and 480 <= height <= 7680):
        raise ValueError('Export width/height must be integers in 640..7680 / 480..7680 pixels.')
    if not 72 <= dpi <= 600:
        raise ValueError('Export DPI must be in [72, 600].')
    if not formats or len(set(formats)) != len(formats) or set(formats) - {'png', 'svg', 'pdf'}:
        raise ValueError('Choose unique PNG, SVG, and/or PDF formats.')
    # Validate the complete saved state before allocating output files.
    document = make_document(catalog, state, presentation, title)
    folder = versioned_directory(parent, stem)
    (folder / 'INCOMPLETE.txt').write_text('Export in progress.\n', encoding='utf-8')
    with matplotlib.rc_context({'font.family': 'DejaVu Sans', 'svg.fonttype': 'none', 'pdf.fonttype': 42,
                                'path.simplify': False, 'svg.hashsalt': 'relativistic-spaceship-viewer-v2'}):
        fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi, facecolor='#080e19')
        FigureCanvasAgg(fig)
        panels = draw_figure(fig, catalog, state, presentation, title, for_export=True)
        fig.canvas.draw()
        for fmt in formats:
            fig.savefig(folder / f'scene.{fmt}', format=fmt, dpi=dpi, facecolor=fig.get_facecolor())
        numerical = {}
        for index, panel in enumerate(panels):
            prefix = 'rest' if presentation.comparison and index == 0 else 'moving'
            scene = panel['scene']
            for field in ('apparent', 'doppler', 'mu', 'x_deg', 'y_deg', 'visible', 'display_magnitude', 'marker_area_pt2', 'rgb'):
                numerical[prefix + '_' + field] = getattr(scene, field)
            numerical[prefix + '_visible_catalog_rows'] = panel['rows']
            if panel['solar'] is not None:
                sun=panel['solar']
                numerical[prefix+'_solar_occulted']=panel['solar_occulted']
                for field in ('rest_center','rest_limb','limb','limb_doppler','cap_center','central_ray',
                              'rest_radius_rad','radius_rad','solid_angle_sr','central_doppler','doppler_min','doppler_max'):
                    numerical[prefix+'_solar_'+field]=sun[field]
                if presentation.solar.radiometry_enabled:
                    image=solar_image(panel['state'],sun,presentation.solar)
                    if image is not None:
                        for field in ('x_deg','y_deg','inside','doppler','xyz_w_m2_sr','rgb'):
                            numerical[prefix+'_solar_image_'+field]=image[field]
        np.savez_compressed(folder / 'scene_data.npz', **numerical)
    fingerprints = {}
    for name in ('__init__.py', 'catalog.py', 'geometry.py', 'relativity.py', 'state.py', 'scene.py', 'solar.py', 'solar_radiometry.py', 'data/CIE_xyz_1931_2deg.csv', 'display.py', 'presentation.py', 'targets.py', 'plotting.py', 'session.py', 'exporting.py'):
        source = Path(__file__).parent / name
        fingerprints[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    artifacts = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in sorted(folder.iterdir()) if file.name != 'INCOMPLETE.txt'}
    document['export'] = {'created_utc': datetime.now(timezone.utc).isoformat(), 'application_version': __version__,
                          'width_px': width, 'height_px': height, 'dpi': dpi, 'formats': list(formats),
                          'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__,
                          'matplotlib': matplotlib.__version__, 'font': 'DejaVu Sans',
                          'svg_text': 'editable text; font availability may change appearance',
                          'pdf_fonts': 'TrueType embedded', 'source_sha256': fingerprints, 'artifacts_sha256': artifacts,
                          'label_layout': 'deterministic screen-space avoidance; brightest candidate budget max(24,min(64,2*max_labels)); selected object first; omitted labels do not exclude stars',
                          'labels_drawn_per_panel': [len(panel['labels']) for panel in panels],
                          'solar_radiometry_per_panel': [solar_summary(panel['solar'],presentation.solar) if panel['solar'] is not None else None for panel in panels],
                          'processing': 'rest V cut; optional fixed-1-AU solar disk ray occultation; 720 limb samples; horizon/large-cap display uses 401x401 angular mask; no stellar smoothing, interpolation, resampling, or uncertainty propagation'}
    if presentation.solar is not None:
        document['export']['solar_texture']='257x257 angular texture for front-facing disk, otherwise 401x401; XYZ interpolated in log(D); display bilinear sampling; geometric clipping independent of exposure. Outside image_inside mask values are computational padding.'
        # Accompany CIE-derived numeric/color results with their attribution.
        import shutil
        for name in ('CIE_ATTRIBUTION.txt','CC_BY_SA_4_0.html'):
            shutil.copyfile(Path(__file__).parent/'data'/name,folder/name)
            document['export']['artifacts_sha256'][name]=hashlib.sha256((folder/name).read_bytes()).hexdigest()
    with (folder / 'scene.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2)
    (folder / 'INCOMPLETE.txt').unlink()  # only this export's own fixed marker file
    return folder
