"""Render controlled application widgets; no other desktop content is captured."""
from pathlib import Path
import argparse
import json
import os
import sys
import numpy as np
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6 import QtWidgets as W,QtGui
from spaceship_viewer.qt_app import Viewer
from spaceship_viewer.session import load_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--hipparcos-scene',type=Path)
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=False)
    app=W.QApplication.instance() or W.QApplication([])
    app.setStyle('Fusion')
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
        path=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/name
        if path.exists():
            QtGui.QFontDatabase.addApplicationFont(str(path))
    from matplotlib.font_manager import findfont
    QtGui.QFontDatabase.addApplicationFont(findfont('DejaVu Sans'))
    viewer=Viewer()
    viewer.resize(1920,1080)
    viewer.inspector.show()
    viewer.show()
    def settle():
        app.processEvents()
        viewer.render_timer.stop()
        viewer.refresh()
        app.processEvents()
    try:
        viewer.set_beta(.9)
        row=viewer.catalog.name.tolist().index('Pollux')
        viewer.select_row(row)
        settle()
        viewer.grab().save(str(args.output_dir/'inspector_camera_only.png'))
        viewer.apply_preset(3)
        settle()
        viewer.grab().save(str(args.output_dir/'custom_pollux_heading.png'))
        before=viewer.last_scene.doppler.copy()
        viewer.focus_sky(True)
        settle()
        ax=viewer.panels[-1]['ax']
        assert abs(ax.bbox.width/ax.bbox.height-16/9)<1e-10
        assert np.array_equal(before,viewer.last_scene.doppler)
        viewer.grab().save(str(args.output_dir/'focus_16_9.png'))
        result={'status':'passed','capture':'own Qt widgets rendered offscreen; not a native desktop screenshot',
                'focus_axes_pixel_size':[ax.bbox.width,ax.bbox.height],
                'focus_fov_degrees':[viewer.view_state.hfov_deg,viewer.view_state.vfov_deg],
                'doppler_unchanged_by_focus':True}
        if args.hipparcos_scene:
            viewer.focus_sky(False)
            catalog,state,presentation,title=load_document(args.hipparcos_scene)
            viewer.apply_catalog(catalog,title)
            viewer.view_state=state
            settle()
            viewer.grab().save(str(args.output_dir/'live_hipparcos.png'))
            result.update(live_hipparcos_loaded=catalog.n,live_hipparcos_visible=viewer.last_scene.n_visible,
                          live_hipparcos_render_ms=viewer.last_render_ms)
        (args.output_dir/'widget_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        viewer.close()
        app.processEvents()


if __name__=='__main__':
    main()
