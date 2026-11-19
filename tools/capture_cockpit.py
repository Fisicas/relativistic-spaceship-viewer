"""Capture this app's own Qt widgets; no other desktop content is captured."""
from pathlib import Path
import argparse,json,math,os,sys
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6 import QtCore,QtGui,QtWidgets as W
from spaceship_viewer import qt_app as module

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',required=True,type=Path)
    p.add_argument('--catalog-cache',type=Path);args=p.parse_args()
    out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=False)
    app=W.QApplication.instance() or W.QApplication([]);app.setStyle('Fusion')
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
        QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/name))
    from matplotlib.font_manager import findfont
    QtGui.QFontDatabase.addApplicationFont(findfont('DejaVu Sans'))
    v=module.Viewer();v.resize(1450,900);v.show();v.set_gamma(2.)
    records=[]
    def capture(name):
        app.processEvents();v.render_timer.stop();v.refresh();app.processEvents()
        assert v.grab().save(str(out/(name+'.png')))
        ax=v.panels[-1]['ax']
        renderer=v.figure.canvas.get_renderer()
        for item in (ax._left_title,ax.xaxis.label):
            box=item.get_window_extent(renderer)
            assert box.x0>=-1 and box.y0>=-1 and box.x1<=v.figure.bbox.width+1 and box.y1<=v.figure.bbox.height+1, (name,item.get_text(),box)
        records.append({'name':name,'window':[v.width(),v.height()],
            'canvas':[v.canvas.width(),v.canvas.height()],'axes_ratio':ax.bbox.width/ax.bbox.height,
            'fov_deg':[v.view_state.hfov_deg,v.view_state.vfov_deg],
            'side_pods':not v.left_pod.isHidden(),'wide_slider_px':v.cockpit_speed_slider.width(),
            'sidebar_slider_px':v.speed_slider.width(),'catalog_rows':v.catalog.n})
    try:
        capture('charcoal_standard')
        v.resize(1920,1080);v.focus_sky(True);capture('charcoal_focus_cockpit')
        if args.catalog_cache:
            cache_path=args.catalog_cache.resolve()
            with patch.object(module.catalog_cache,'cache_root',side_effect=lambda root=None:Path(root) if root is not None else cache_path):
                v.load_hipparcos_library();capture('charcoal_cached_hipparcos')
                def capture_dialog():
                    d=app.activeModalWidget()
                    if d:
                        assert d.grab().save(str(out/'catalog_startup.png'))
                        d.reject()
                QtCore.QTimer.singleShot(50,capture_dialog)
                v.catalog_startup_dialog()
        v.focus_sky(False);v.resize(1060,700);v.inspector.show()
        v.select_named_target(33);v.set_beta(.9);v.solar_heading('away');v.frame_solar_disk();v.fit_solar_exposure()
        capture('charcoal_laptop_sol')
        record={'status':'passed','capture':'Own widgets, Qt offscreen with explicit fonts','layouts':records,
                'native_monitor_dpi_tested':False,'startup_choice_changed':False}
        (out/'capture_checks.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        print(json.dumps(record,indent=2))
    finally:v.close();app.processEvents()
if __name__=='__main__':main()
