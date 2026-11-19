"""Render our own offscreen widgets against an existing full catalog snapshot."""
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
from spaceship_viewer.session import load_document,save_document


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog-scene',required=True,type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
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
    viewer.resize(1600,1000)
    viewer.inspector.show()
    viewer.show()
    def settle():
        app.processEvents()
        viewer.render_timer.stop()
        viewer.refresh()
        app.processEvents()
    try:
        catalog,state,_,title=load_document(args.catalog_scene)
        viewer.apply_catalog(catalog,title)
        viewer.set_beta(.9)
        settle()
        before=viewer.last_scene.doppler.copy()
        viewer.object_combo.activated.emit(16)
        settle()
        assert viewer.object_combo.count()==33 and viewer.object_name.text()=='Pollux'
        assert viewer.catalog.n==catalog.n and viewer.presentation.reference_target.name=='Pollux'
        np.testing.assert_array_equal(before,viewer.last_scene.doppler)
        viewer.grab().save(str(args.output_dir/'hipparcos_named_targets.png'))
        viewer.object_combo.showPopup()
        app.processEvents()
        viewer.object_combo.view().window().grab().save(str(args.output_dir/'named_picker.png'))
        viewer.object_combo.hidePopup()
        snapshot=args.output_dir/'named_reference_scene.json'
        save_document(snapshot,viewer.catalog,viewer.view_state,viewer.presentation,viewer.catalog_title)
        reopened,_,appearance,_=load_document(snapshot)
        assert reopened.n==catalog.n and appearance.reference_target.name=='Pollux'
        result={'status':'passed','loaded_objects':catalog.n,'named_picker_count':viewer.object_combo.count(),
                'named_picker_entries':[viewer.object_combo.itemText(i) for i in range(viewer.object_combo.count())],
                'selected_reference':'Pollux','doppler_unchanged':True,'scene_round_trip':True,
                'capture':'own widgets rendered offscreen; no other desktop content'}
        (args.output_dir/'checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        viewer.close()
        app.processEvents()


if __name__=='__main__':
    main()
