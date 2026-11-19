"""Short offline self-test used before activating a packaged installation."""
from pathlib import Path
import json
import math
import os
import platform
import sys
import tempfile


def check_live_catalog(output):
    """Explicit opt-in diagnostic, separate from the network-blocked self-test."""
    from dataclasses import asdict
    import numpy as np
    from . import __version__
    from .catalog import fetch_hipparcos
    from .session import make_document,decode_document
    from .state import ViewState
    from .presentation import Presentation
    catalog=fetch_hipparcos(8.)
    document=make_document(catalog,ViewState(),Presentation(),'Live Hipparcos diagnostic')
    reopened,_,_,_=decode_document(json.loads(json.dumps(document,allow_nan=False)))
    if not np.array_equal(catalog.ra_deg,reopened.ra_deg) or not np.array_equal(catalog.bv,reopened.bv,equal_nan=True):
        raise AssertionError('Live catalog serialization changed values.')
    result={'status':'passed','version':__version__,'frozen':bool(getattr(sys,'frozen',False)),
            'live_network':True,'rows':catalog.n,'received':catalog.import_report.total_rows,
            'rejected':len(catalog.import_report.rejected),'metadata':asdict(catalog.metadata),
            'catalog_sha256':document['catalog_sha256'],'json_round_trip':'passed',
            'scope':'retrieval and serialization; not observational validation'}
    with Path(output).open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    return result


def run(output):
    # This entry point runs in a dedicated short-lived process. Fail on any
    # network attempt, including downloads triggered indirectly during imports.
    def reject_network(event,args):
        if event in {'socket.connect','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr'}:
            raise RuntimeError('Network access is forbidden during the offline installation check.')
    sys.addaudithook(reject_network)
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    import numpy as np
    import PySide6
    from PySide6 import QtGui,QtWidgets as W
    from matplotlib.font_manager import findfont
    from . import __version__
    from .demo_catalog import built_in_catalog
    from .exporting import export_scene
    from .presentation import Presentation
    from .relativity import aberrate
    from .scene import compute_scene
    from .session import load_document
    from .state import ViewState
    from .qt_app import Viewer
    checks=[]
    def check(condition,name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    catalog=built_in_catalog()
    check(compute_scene(catalog,ViewState()).n_visible==12,'rest Orion reference')
    state=ViewState(beta=math.sqrt(3)/2)
    check(compute_scene(catalog,state).n_visible==26,'gamma=2 Orion reference')
    _,d,_=aberrate([[1.,0.,0.],[-1.,0.,0.],[0.,1.,0.]],[1.,0.,0.],state.beta)
    check(np.allclose(d,[2*(1+state.beta),2*(1-state.beta),2]),'forward/back/transverse Doppler')
    app=W.QApplication.instance() or W.QApplication([])
    QtGui.QFontDatabase.addApplicationFont(findfont('DejaVu Sans'))
    viewer=Viewer()
    try:
        check(viewer.last_scene.n_visible==12,'Qt construction')
        viewer.set_gamma(2.)
        viewer.render_timer.stop()
        viewer.refresh()
        check(viewer.last_scene.n_visible==26,'Qt gamma control')
        old_heading=viewer.view_state.velocity_direction.copy()
        row=catalog.name.tolist().index('Sirius')
        viewer.select_row(row)
        viewer.refresh()
        check(not viewer.view_state.camera_locked and np.array_equal(old_heading,viewer.view_state.velocity_direction),
              'inspector centers camera without changing velocity')
        check(viewer.preset.itemText(3)=='Custom: Sirius','custom heading names inspector target')
        viewer.focus_sky(True)
        viewer.refresh()
        axes=viewer.panels[-1]['ax']
        check(abs(axes.bbox.width/axes.bbox.height-16/9)<1e-9,'focused viewport is 16:9')
        viewer.focus_sky(False)
        from .catalog import StarCatalog,CatalogMetadata
        fixture=StarCatalog(['HIP diagnostic fixture'],[1.],[0.],[2.],[np.nan],[np.nan],
                            metadata=CatalogMetadata(source='Synthetic offline installation fixture'))
        viewer.apply_catalog(fixture,'Offline catalog fixture')
        viewer.select_named_target(16)
        viewer.refresh()
        check(viewer.object_combo.count()==33 and viewer.object_name.text()=='Pollux',
              'named picker remains the original 33 with an external catalog')
        check(viewer.catalog.n==1 and viewer.presentation.reference_target.name=='Pollux',
              'reference target is separate from loaded measurements')
        with tempfile.TemporaryDirectory(prefix='rsv-selftest-') as directory:
            figure=export_scene(directory,'probe',catalog,state,Presentation(), 'Offline installation check',
                                width=960,height=720,dpi=100)
            restored,reopened,_,_=load_document(figure/'scene.json')
            check(np.array_equal(compute_scene(restored,reopened).doppler,compute_scene(catalog,state).doppler),
                  'portable export numerical round trip')
            check((figure/'scene.pdf').read_bytes().startswith(b'%PDF'),'PDF export')
            check((figure/'scene.svg').is_file(),'SVG export')
            reference=export_scene(directory,'reference',viewer.catalog,viewer.view_state,viewer.presentation,
                                   'Reference target diagnostic',width=960,height=720,dpi=100)
            background,_,appearance,_=load_document(reference/'scene.json')
            check(background.n==1 and appearance.reference_target.name=='Pollux',
                  'reference export preserves target and separate catalog')
        # The standalone distribution promises this optional feature without a
        # separate pip step. Import it here; do not issue a live catalog query.
        from astroquery.vizier import Vizier
        check(Vizier is not None,'bundled optional VizieR imports')
    finally:
        viewer.close()
        app.processEvents()
    result={'status':'passed','version':__version__,'checks':checks,'frozen':bool(getattr(sys,'frozen',False)),
            'executable':sys.executable,'python':platform.python_version(),'numpy':np.__version__,
            'pyside6':PySide6.__version__,'live_network':False,'network_policy':'Python socket audit hook rejects network attempts'}
    with Path(output).open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    return result
