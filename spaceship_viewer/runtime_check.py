"""Short offline self-test used before activating a packaged installation."""
from pathlib import Path
import json
import math
import os
import platform
import sys
import tempfile


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
        with tempfile.TemporaryDirectory(prefix='rsv-selftest-') as directory:
            figure=export_scene(directory,'probe',catalog,state,Presentation(), 'Offline installation check',
                                width=960,height=720,dpi=100)
            restored,reopened,_,_=load_document(figure/'scene.json')
            check(np.array_equal(compute_scene(restored,reopened).doppler,compute_scene(catalog,state).doppler),
                  'portable export numerical round trip')
            check((figure/'scene.pdf').read_bytes().startswith(b'%PDF'),'PDF export')
            check((figure/'scene.svg').is_file(),'SVG export')
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
