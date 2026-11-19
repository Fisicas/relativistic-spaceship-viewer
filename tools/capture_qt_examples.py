"""Render controlled Qt example windows and benchmark a labeled synthetic catalog.

These are widget-rendered screenshots of our own application, with no desktop
content, authentication, or external data. They are saved in a new directory.
"""
from pathlib import Path
import argparse
import json
import math
import os
import sys
import time
import numpy as np
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PySide6 import QtWidgets as W, QtGui
from spaceship_viewer.catalog import StarCatalog, CatalogMetadata
from spaceship_viewer import qt_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--write-docs', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    app = W.QApplication.instance() or W.QApplication([])
    app.setStyle('Fusion')
    # The offscreen QPA plugin does not populate the native Windows font DB.
    # Register fonts for widget-only documentation renders; normal desktop
    # windows use the Windows QPA plugin and its existing system font database.
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
        font = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / name
        if font.exists():
            QtGui.QFontDatabase.addApplicationFont(str(font))
    from matplotlib.font_manager import findfont
    QtGui.QFontDatabase.addApplicationFont(findfont('DejaVu Sans'))
    viewer = qt_app.Viewer()
    assert QtGui.QFontMetrics(viewer.object_name.font()).inFontUcs4(ord('A')), 'Offscreen font registration failed'
    viewer.resize(1600, 1000)
    viewer.inspector.show()
    viewer.inspect_button.setChecked(True)
    viewer.show()

    def settle():
        app.processEvents()
        viewer.render_timer.stop()
        viewer.refresh()
        app.processEvents()

    try:
        viewer.set_gamma(2.)
        viewer.select_row(0)
        settle()
        viewer.grab().save(str(args.output_dir / 'interface.png'))
        viewer.toggle_comparison(True)
        settle()
        viewer.grab().save(str(args.output_dir / 'comparison_interface.png'))
        viewer.focus_button.setChecked(True)
        viewer.focus_sky(True)
        settle()
        viewer.grab().save(str(args.output_dir / 'focus_interface.png'))

        rng = np.random.default_rng(2030)
        size = 10000
        catalog = StarCatalog(np.array([f'Synthetic {i}' for i in range(size)]), rng.uniform(0, 360, size),
                              np.rad2deg(np.arcsin(rng.uniform(-1, 1, size))), rng.uniform(0, 8, size),
                              rng.uniform(-.3, 1.8, size), np.full(size, np.nan),
                              metadata=CatalogMetadata(source='Synthetic uniform-sphere performance fixture; RNG seed 2030'))
        viewer.apply_catalog(catalog, 'Synthetic performance fixture · not observational data')
        durations = []
        for _ in range(3):
            start = time.perf_counter()
            settle()
            durations.append((time.perf_counter()-start)*1000)
        result = {'catalog': 'synthetic uniform sphere, seed 2030', 'objects': size,
                  'beta': viewer.view_state.beta, 'comparison': viewer.presentation.comparison,
                  'visible_moving': viewer.last_scene.n_visible, 'label_limit': viewer.presentation.max_labels,
                  'complete_refresh_ms': durations, 'median_refresh_ms': float(np.median(durations)),
                  'scope': 'offscreen Qt widget, same host only; no general FPS or cross-machine claim'}
        (args.output_dir / 'performance.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        if args.write_docs:
            for name in ('interface.png', 'comparison_interface.png', 'focus_interface.png'):
                path = ROOT / 'docs/images/v02' / name
                with path.open('xb') as stream:
                    stream.write((args.output_dir/name).read_bytes())
        print(json.dumps(result, indent=2))
    finally:
        viewer.close()
        app.processEvents()


if __name__ == '__main__':
    main()
