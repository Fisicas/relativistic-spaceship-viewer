"""Offscreen Qt integration checks; controlled dialogs and no live VizieR call."""
from pathlib import Path
import argparse
from dataclasses import replace
import json
import math
import os
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from PySide6 import QtWidgets as W, QtGui
from spaceship_viewer import qt_app as module
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.session import load_document, save_document


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    app = W.QApplication.instance() or W.QApplication([])
    app.setStyle('Fusion')
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf'):
        font = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / name
        if font.exists():
            QtGui.QFontDatabase.addApplicationFont(str(font))
    from matplotlib.font_manager import findfont
    QtGui.QFontDatabase.addApplicationFont(findfont('DejaVu Sans'))
    viewer = module.Viewer()
    checks = []

    def check(value, name):
        assert value, name
        checks.append(name)

    def settle():
        viewer.render_timer.stop()
        viewer.refresh()
        app.processEvents()

    try:
        viewer.resize(1450, 900)
        viewer.show()
        app.processEvents()
        settle()
        check(viewer.last_scene.n_visible == 12, 'initial Orion scene')
        viewer.set_gamma(2.)
        settle()
        check(abs(viewer.view_state.beta - math.sqrt(3)/2) < 1e-15, 'exact gamma=2 speed retained')
        check(viewer.last_scene.n_visible == 26, 'gamma=2 reference visibility')
        viewer.set_lock(False)
        heading = viewer.view_state.velocity_direction.copy()
        d = viewer.last_scene.doppler.copy()
        viewer.turn(12., 5.)
        settle()
        check(np.array_equal(heading, viewer.view_state.velocity_direction), 'unlocked camera does not steer velocity')
        check(np.array_equal(d, viewer.last_scene.doppler), 'camera rotation does not change Doppler factors')
        viewer.set_lock(True)
        settle()
        check(np.allclose(viewer.view_state.camera.forward, heading), 'relock points camera along velocity')
        viewer.toggle_comparison(True)
        settle()
        check(len(viewer.panels) == 2 and viewer.panels[0]['state'].beta == 0., 'rest/moving comparison')
        check(viewer.panels[0]['state'].camera == viewer.panels[1]['state'].camera, 'comparison camera synchronized')
        viewer.select_row(0)
        settle()
        check(viewer.object_name.text() == 'Betelgeuse', 'object inspector selects by catalog row')
        check('550' in viewer.object_details.toPlainText(), 'wavelength example is labeled')
        old_heading = viewer.view_state.velocity_direction.copy()
        old_doppler = viewer.last_scene.doppler.copy()
        row = viewer.catalog.name.tolist().index('Sirius')
        viewer.object_combo.setCurrentIndex(row)
        viewer.object_combo.activated.emit(row)
        settle()
        check(viewer.preset.itemText(3) == 'Custom: Sirius', 'custom target label follows inspector object')
        check(not viewer.view_state.camera_locked and np.array_equal(old_heading,viewer.view_state.velocity_direction),
              'inspector centering unlocks camera without steering velocity')
        check(np.array_equal(old_doppler,viewer.last_scene.doppler), 'inspector centering preserves Doppler factors')
        target = int(np.flatnonzero(viewer.panels[-1]['rows'] == row)[0])
        scene = viewer.last_scene
        check(abs(scene.x_deg[scene.visible][target]) < 1e-9 and abs(scene.y_deg[scene.visible][target]) < 1e-9,
              'inspector selection centers apparent direction in moving viewport')
        viewer.preset.setCurrentIndex(3)
        viewer.preset.activated.emit(3)
        settle()
        check(viewer.view_state.camera_locked and abs(viewer.view_state.heading_ra_deg-viewer.catalog.ra_deg[row]) < 1e-9,
              'custom object heading explicitly steers and locks camera')
        check([viewer.preset.itemText(i) for i in range(3)] == ['Orion','Galactic Center','Tau Ceti'],
              'original heading presets retained')
        viewer.change(rest_mag_limit=-5.)
        settle()
        check(viewer.last_scene.n_visible == 0, 'empty scene renders')
        viewer.reset()
        settle()
        temp_root = ROOT / '.test-tmp'
        temp_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            assert Path(directory).resolve().is_relative_to(temp_root.resolve())
            csv = Path(directory) / 'synthetic.csv'
            csv.write_text('name,ra,dec,mag,bv\nSynthetic,1,0,1,\nBad,2,100,2,.3\n', encoding='utf-8')
            old = viewer.catalog
            with patch.object(module.W.QFileDialog, 'getOpenFileName', return_value=(str(csv), '')), \
                 patch.object(module.W.QInputDialog, 'getItem', return_value=('hour', True)), \
                 patch.object(module.W.QMessageBox, 'question', return_value=module.W.QMessageBox.StandardButton.No):
                viewer.import_csv()
            check(viewer.catalog is old, 'canceling CSV preview preserves catalog')
            with patch.object(module.W.QFileDialog, 'getOpenFileName', return_value=(str(csv), '')), \
                 patch.object(module.W.QInputDialog, 'getItem', return_value=('hour', True)), \
                 patch.object(module.W.QMessageBox, 'question', return_value=module.W.QMessageBox.StandardButton.Yes):
                viewer.import_csv()
            check(viewer.catalog.n == 1 and viewer.catalog.ra_deg[0] == 15., 'CSV declared units and row rejection reach GUI')
            saved = Path(directory) / 'saved.json'
            with patch.object(module.W.QFileDialog, 'getSaveFileName', return_value=(str(saved), '')):
                viewer.save_scene()
            viewer.restore_demo()
            with patch.object(module.W.QFileDialog, 'getOpenFileName', return_value=(str(saved), '')):
                viewer.open_scene()
            check(viewer.catalog.n == 1 and viewer.catalog.name[0] == 'Synthetic', 'saved scene reopens with embedded catalog')
        viewer.restore_demo()
        settle()
        from spaceship_viewer.catalog import StarCatalog,CatalogMetadata
        from spaceship_viewer.demo_catalog import built_in_catalog
        from spaceship_viewer.session import make_document,decode_document
        background = StarCatalog(['HIP fixture'],[200.],[0.],[2.],[np.nan],[np.nan],
            metadata=CatalogMetadata(source='Synthetic Hipparcos-like background; not observational data'))
        viewer.apply_catalog(background,'Synthetic catalog fixture')
        settle()
        expected = built_in_catalog().name.tolist()+['Sol']
        check(viewer.object_combo.count()==34 and [viewer.object_combo.itemText(i) for i in range(34)]==expected,
              'loaded catalog retains the original 33 named targets plus Sol')
        row=expected.index('Pollux')
        heading=viewer.view_state.velocity_direction.copy()
        viewer.object_combo.activated.emit(row)
        settle()
        check(viewer.object_name.text()=='Pollux' and viewer.presentation.reference_target is not None,
              'named target remains selectable without a matching loaded catalog row')
        check(viewer.catalog is background and viewer.catalog.n==1 and viewer.presentation.selected_row is None,
              'reference selection never appends or relabels catalog measurements')
        check(np.array_equal(heading,viewer.view_state.velocity_direction) and not viewer.view_state.camera_locked,
              'named reference centers without changing velocity')
        check('NAMED REFERENCE' in viewer.object_details.toPlainText() and viewer.preset.itemText(3)=='Custom: Pollux',
              'reference provenance and custom heading are explicit')
        document=make_document(viewer.catalog,viewer.view_state,viewer.presentation)
        _,_,saved,_=decode_document(json.loads(json.dumps(document,allow_nan=False)))
        check(saved.reference_target.name=='Pollux','reference selection survives portable scene round trip')
        viewer.apply_preset(3)
        settle()
        check(abs(viewer.view_state.heading_ra_deg-116.329)<1e-9,'named reference custom heading steers to original coordinates')
        viewer.select_row(0)
        settle()
        check(viewer.object_name.text()=='HIP fixture' and viewer.presentation.reference_target is None
              and viewer.object_combo.currentIndex()==-1 and viewer.object_combo.count()==34,
              'clicked catalog object remains inspectable without enlarging named picker')
        viewer.restore_demo()
        viewer.reset()
        settle()
        with patch.object(module, 'fetch_hipparcos', side_effect=RuntimeError('controlled offline failure')), \
             patch.object(viewer, 'error') as error:
            old = viewer.catalog
            viewer.start_fetch()
            deadline = time.monotonic()+3
            while viewer._fetching and time.monotonic() < deadline:
                viewer.poll_fetch()
                app.processEvents()
                time.sleep(.01)
            check(not viewer._fetching and error.call_count == 1, 'fetch errors reach GUI thread')
            check(viewer.catalog is old, 'fetch failure retains catalog')
        with patch.object(module, 'fetch_hipparcos', return_value=built_in_catalog()):
            viewer.start_fetch()
            deadline = time.monotonic()+3
            while viewer._fetching and time.monotonic() < deadline:
                viewer.poll_fetch()
                app.processEvents()
                time.sleep(.01)
            check(not viewer._fetching and viewer.catalog.n == 33, 'controlled fetch result applied')
        settle()
        previous_revision = viewer._catalog_revision
        viewer.restore_demo()
        newer = viewer.catalog
        viewer._messages.put((True, built_in_catalog(), 8., previous_revision))
        viewer.poll_fetch()
        check(viewer.catalog is newer, 'stale fetch cannot replace a newer catalog')
        from spaceship_viewer import deployment
        with patch.object(deployment,'latest_release',return_value=None):
            viewer.check_updates(automatic=True)
            deadline=time.monotonic()+3
            while viewer._checking_update and time.monotonic()<deadline:
                viewer.poll_updates()
                app.processEvents()
                time.sleep(.01)
            check(not viewer._checking_update,'offline/no-new-release check leaves viewer usable')
        release={'version':'0.2.1','notes':'Controlled fixture; not a published release'}
        viewer._update_messages.put(('check',release,None,True))
        viewer.poll_updates()
        check(not viewer.update_notice.isHidden(),'new release is offered without a startup modal')
        with patch.object(viewer,'error') as error:
            previous=viewer.catalog
            viewer._downloading_update=True
            viewer._update_messages.put(('download',None,'controlled digest failure',False))
            viewer.poll_updates()
            check(error.call_count==1 and viewer.catalog is previous and not viewer._downloading_update,
                  'failed update preserves catalog and resets update state')
        # Same Qt widget hierarchy at common laptop/desktop logical sizes.
        layouts = []
        for width, height in ((1060, 700), (1450, 900), (1920, 1080)):
            viewer.inspector.setVisible(width >= 1400)
            viewer.resize(width, height)
            app.processEvents()
            settle()
            layouts.append({'requested': [width, height], 'actual': [viewer.width(), viewer.height()],
                            'canvas': [viewer.canvas.width(), viewer.canvas.height()]})
            check(viewer.canvas.width() >= 320 and viewer.canvas.height() >= 330, f'viewport remains usable at {width}x{height}')
        viewer.focus_sky(True)
        settle()
        check(viewer.controls_scroll.isHidden() and viewer.inspector.isHidden(), 'focus mode expands viewport')
        original_doppler = viewer.last_scene.doppler.copy()
        ax = viewer.panels[-1]['ax']
        check(abs(ax.bbox.width/ax.bbox.height-16/9) < 1e-10, 'focused sky axes are 16:9')
        scale = ax.transData.transform([[0.,0.],[1.,0.],[0.,1.]])
        check(abs((scale[1,0]-scale[0,0])-(scale[2,1]-scale[0,1])) < 1e-9,
              'focus keeps equal pixels per degree instead of stretching')
        viewer.on_scroll(SimpleNamespace(inaxes=ax,step=2))
        settle()
        check(abs(viewer.view_state.hfov_deg/viewer.view_state.vfov_deg-16/9) < 1e-12,
              'focus zoom retains angular aspect ratio')
        check(np.array_equal(original_doppler,viewer.last_scene.doppler), 'focus and zoom preserve Doppler factors')
        viewer.focus_sky(False)
        settle()
        check(not viewer.controls_scroll.isHidden(), 'focus mode restores controls')
        check(viewer.view_state.hfov_deg == 45. and viewer.view_state.vfov_deg == 45.,
              'leaving focus restores previous field of view')
        viewer.select_named_target(33)
        settle()
        check(viewer.presentation.solar is not None and viewer.object_name.text()=='Sol · our Sun',
              'Sol is available as a finite disk inspector entry')
        from spaceship_viewer.solar import solar_geometry,REST_RADIUS_RAD
        viewer.set_beta(.9)
        viewer.solar_heading('toward')
        settle()
        toward=solar_geometry(viewer.presentation.solar,viewer.view_state)['radius_rad']
        heading=viewer.view_state.velocity_direction.copy()
        viewer.frame_solar_disk()
        settle()
        check(np.array_equal(heading,viewer.view_state.velocity_direction) and not viewer.view_state.camera_locked,
              'framing solar disk preserves velocity and unlocks camera')
        field=viewer.view_state.hfov_deg
        viewer.solar_heading('away')
        settle()
        away=solar_geometry(viewer.presentation.solar,viewer.view_state)['radius_rad']
        check(toward<REST_RADIUS_RAD<away,'toward shrinks and away enlarges the solar disk')
        check(viewer.view_state.hfov_deg==field,'solar tracking does not autozoom away angular-size changes')
        g=solar_geometry(viewer.presentation.solar,viewer.view_state)
        check(np.allclose(viewer.view_state.camera.forward,g['cap_center']), 'solar tracking follows apparent disk without steering')
        viewer.solar_ra_spin.setValue(90.)
        viewer.solar_dec_spin.setValue(10.)
        viewer.apply_solar_direction()
        settle()
        check(viewer.presentation.solar.ra_deg==90. and viewer.presentation.reference_target.ra_deg==90.,
              'solar teaching direction is editable and saved with target')
        viewer.set_beta(.999999)
        viewer.solar_heading('toward')
        viewer.frame_solar_disk()
        settle()
        check(viewer.view_state.vfov_deg<.01,'solar framing supports sub-degree high-speed disks')
        viewer.solar_heading('away')
        viewer.frame_solar_disk()
        settle()
        check('half the sky' in viewer.object_details.toPlainText(), 'large solar cap is rendered and clearly labeled')
        result = {'status': 'passed', 'checks': checks, 'logical_layouts': layouts,
                  'live_vizier_request': False, 'mode': 'Qt offscreen integration test'}
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
        print(json.dumps(result, indent=2))
    finally:
        viewer.close()
        app.processEvents()


if __name__ == '__main__':
    main()
