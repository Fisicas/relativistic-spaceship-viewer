"""Run local Tk integration checks with controlled dialogs and no live requests.

Invoke from the repository root with --output pointing to a new JSON file.
The test window is withdrawn and always closed; no user settings are written.
"""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spaceship_viewer import app as module
from spaceship_viewer.demo_catalog import built_in_catalog


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    errors, checks = [], []
    viewer = module.Viewer()
    viewer.withdraw()
    viewer.report_callback_exception = lambda exc, value, tb: errors.append(str(value))

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    def wait_for_fetch():
        deadline = time.monotonic() + 5
        while viewer._fetching and time.monotonic() < deadline:
            viewer.update()
            time.sleep(.01)
        check(not viewer._fetching, 'fetch result delivered on Tk event loop')

    temp_root = ROOT / '.test-tmp'
    temp_root.mkdir(exist_ok=True)
    try:
        viewer.update()
        check(viewer.last_scene.n_visible == 12, 'initial Orion scene')
        viewer.beta_var.set(.87)
        viewer.update_plot()
        check(viewer.last_scene.n_visible == 26, 'high-speed scene')
        viewer.lock_var.set(False)
        viewer.toggle_lock()
        heading = viewer.view_state.velocity_direction.copy()
        original_d = viewer.last_scene.doppler.copy()
        viewer.on_mouse_press(SimpleNamespace(inaxes=viewer.ax, button=1, x=100., y=100.))
        viewer.on_mouse_motion(SimpleNamespace(x=180., y=120.))
        viewer.on_mouse_release(None)
        check(np.array_equal(heading, viewer.view_state.velocity_direction), 'unlocked drag preserves heading')
        check(np.array_equal(original_d, viewer.last_scene.doppler), 'unlocked drag preserves Doppler factors')
        viewer.lock_var.set(True)
        viewer.toggle_lock()
        check(np.allclose(viewer.view_state.camera.forward, heading), 'relock aligns camera')
        with patch.object(module.messagebox, 'showerror') as error:
            viewer.dec_var.set(91.)
            viewer.apply_heading()
            check(error.call_count == 1, 'invalid declination reports error')
            check(viewer.view_state.heading_dec_deg == -1., 'invalid heading preserves state')
        viewer.set_target(84., -1.)
        viewer.maglim_var.set(-10.)
        viewer.update_plot()
        check(viewer.last_scene.n_visible == 0, 'empty scene renders without exception')
        viewer.maglim_var.set(8.)
        viewer.update_plot()
        with tempfile.TemporaryDirectory(dir=temp_root) as folder:
            assert Path(folder).resolve().is_relative_to(temp_root.resolve())
            csv_path = Path(folder) / 'synthetic_import.csv'
            csv_path.write_text('name,ra,dec,mag,bv\nSynthetic,1,0,1,\nBad,2,100,2,.3\n', encoding='utf-8')
            with patch.object(module.filedialog, 'askopenfilename', return_value=str(csv_path)), \
                 patch.object(module.simpledialog, 'askstring', return_value='hour'), \
                 patch.object(module.messagebox, 'askyesno', return_value=False):
                previous = viewer.catalog
                viewer.load_csv_dialog()
                check(viewer.catalog is previous, 'canceling import preview preserves catalog')
            with patch.object(module.filedialog, 'askopenfilename', return_value=str(csv_path)), \
                 patch.object(module.simpledialog, 'askstring', return_value='hour'), \
                 patch.object(module.messagebox, 'askyesno', return_value=True):
                viewer.load_csv_dialog()
                check(viewer.catalog.n == 1 and viewer.catalog.ra_deg[0] == 15., 'accepted import uses declared RA hours')
                check(len(viewer.catalog.import_report.rejected) == 1, 'import preview retains rejected-row report')
        with patch.object(module, 'fetch_hipparcos', side_effect=RuntimeError('controlled offline failure')), \
             patch.object(module.messagebox, 'showerror') as error:
            previous = viewer.catalog
            viewer.fetch_hipparcos_dialog()
            wait_for_fetch()
            check(error.call_count == 1, 'fetch failure reaches error dialog')
            check(viewer.catalog is previous, 'fetch failure preserves catalog')
        with patch.object(module, 'fetch_hipparcos', return_value=built_in_catalog()):
            viewer.fetch_hipparcos_dialog()
            wait_for_fetch()
            check(viewer.catalog.n == 33, 'fetch success applies controlled result')
        check(not errors, 'no asynchronous Tk callback exceptions')
        result = {'status': 'passed', 'checks': checks, 'callback_errors': errors,
                  'tk_version': module.tk.TkVersion, 'live_vizier_request': False,
                  'window': 'withdrawn local Tk integration test'}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result, indent=2))
    finally:
        viewer.close()


if __name__ == '__main__':
    main()
