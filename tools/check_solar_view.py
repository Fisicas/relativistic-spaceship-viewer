"""Versioned solar examples with model parameters, numeric exports, and UI captures."""
from pathlib import Path
import argparse
from dataclasses import replace
import json
import math
import os
import sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from PySide6 import QtWidgets as W,QtGui
from spaceship_viewer.qt_app import Viewer
from spaceship_viewer.exporting import export_scene
from spaceship_viewer.solar import solar_geometry
from verify_export import verify


def main():
    parser=argparse.ArgumentParser(description=__doc__)
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
    viewer.resize(1800,1100)
    viewer.inspector.show()
    viewer.show()
    def settle():
        app.processEvents()
        viewer.render_timer.stop()
        viewer.refresh()
        app.processEvents()
    results=[]
    try:
        viewer.select_named_target(33)
        viewer.set_beta(0.)
        viewer.solar_heading('toward')
        viewer.frame_solar_disk()
        settle()
        viewer.grab().save(str(args.output_dir/'sol_inspector.png'))
        viewer.change(hfov_deg=4.,vfov_deg=4.)
        for label,beta,direction in (('rest',0.,'toward'),('toward_090',.9,'toward'),
                                     ('away_090',.9,'away'),('transverse_090',.9,'transverse')):
            viewer.set_beta(beta)
            viewer.solar_heading(direction)
            settle()
            g=solar_geometry(viewer.presentation.solar,viewer.view_state)
            folder=export_scene(args.output_dir,label,viewer.catalog,viewer.view_state,viewer.presentation,
                                'Sol at 1 AU · '+label,width=1600,height=1000,dpi=150)
            replay=verify(folder/'scene.json')
            results.append({'case':label,'beta':beta,'heading':direction,
                            'cap_diameter_deg':math.degrees(2*g['radius_rad']),
                            'center_doppler':g['central_doppler'],'solid_angle_sr':g['solid_angle_sr'],
                            'export':str(folder),'replay':replay['status']})
            if label=='away_090':
                viewer.grab().save(str(args.output_dir/'sol_away_090.png'))
        viewer.set_beta(.999999)
        viewer.solar_heading('away')
        viewer.frame_solar_disk()
        settle()
        viewer.grab().save(str(args.output_dir/'sol_large_cap.png'))
        g=solar_geometry(viewer.presentation.solar,viewer.view_state)
        assert g['radius_rad']>math.pi/2
        result={'status':'passed','setup':'fixed 1 AU, initial Sun RA=0 deg Dec=0 deg, no ephemeris',
                'normal_examples_fov_deg':[4.,4.],'limb_samples':720,'horizon_mask_grid':[401,401],
                'cases':results,'large_cap_half_angle_deg':math.degrees(g['radius_rad']),
                'capture':'own Qt widgets rendered offscreen'}
        (args.output_dir/'solar_checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2))
    finally:
        viewer.close()
        app.processEvents()


if __name__=='__main__':
    main()
