"""Verify an export's hashes and independently recompute its stored scene arrays."""
from pathlib import Path
import argparse
from dataclasses import replace
import hashlib
import json
import sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spaceship_viewer.exporting import export_scene
from spaceship_viewer.scene import compute_scene
from spaceship_viewer.session import load_document


def verify(path, rerender_parent=None):
    path = Path(path).resolve()
    document = json.loads(path.read_text(encoding='utf-8'))
    catalog, state, presentation, title = load_document(path)
    for name, digest in document['export']['artifacts_sha256'].items():
        artifact = (path.parent/name).resolve()
        if artifact.parent != path.parent or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Invalid artifact path or hash: {name}')
    fields = ('apparent', 'doppler', 'mu', 'x_deg', 'y_deg', 'visible', 'display_magnitude', 'marker_area_pt2', 'rgb')
    with np.load(path.parent/'scene_data.npz', allow_pickle=False) as arrays:
        for prefix, panel_state in [('moving', state)] + ([('rest', replace(state, beta=0.))] if presentation.comparison else []):
            computed = compute_scene(catalog, panel_state)
            for field in fields:
                np.testing.assert_allclose(arrays[prefix+'_'+field], getattr(computed, field), atol=2e-12, rtol=2e-12)
            np.testing.assert_array_equal(arrays[prefix+'_visible_catalog_rows'], np.flatnonzero(catalog.vmag <= state.rest_mag_limit)[computed.visible])
    result = {'status': 'passed', 'scene': str(path), 'catalog_sha256': document['catalog_sha256'],
              'scope': 'artifact hashes and scientific arrays; calibrated radiometry is not validated'}
    if rerender_parent:
        export = document['export']
        folder = export_scene(rerender_parent, 'reproduced', catalog, state, presentation, title,
                              width=export['width_px'], height=export['height_px'], dpi=export['dpi'], formats=('png',))
        from PIL import Image
        original = np.asarray(Image.open(path.parent/'scene.png'))
        rendered = np.asarray(Image.open(folder/'scene.png'))
        result.update(rerendered=str(folder), png_pixels_equal=bool(np.array_equal(original, rendered)))
        if not result['png_pixels_equal']:
            raise ValueError('Recomputed arrays match, but PNG pixels differ; inspect renderer/font/environment versions.')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene', type=Path)
    parser.add_argument('--rerender-parent', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.scene, args.rerender_parent), indent=2))
