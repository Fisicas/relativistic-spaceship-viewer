"""Entry point shared by source, wheel, and self-contained Windows builds."""
from contextlib import nullcontext
from pathlib import Path
import json
import os
import subprocess
import sys
import traceback


def main():
    from . import __version__
    if '--version' in sys.argv:
        if sys.stdout:
            print(__version__)
        return 0
    if '--self-test' in sys.argv:
        position=sys.argv.index('--self-test')
        output=Path(sys.argv[position+1])
        try:
            from .runtime_check import run
            run(output)
            return 0
        except Exception as exc:
            output.write_text(json.dumps({'status':'failed','version':__version__,'error':str(exc),
                                          'traceback':traceback.format_exc()},indent=2),encoding='utf-8')
            return 1
    from .deployment import application_session
    root=os.environ.get('RSV_INSTALL_ROOT')
    context=application_session(root) if root else nullcontext()
    with context:
        from .qt_app import main as run
        code=run()
    # The old viewer has closed and its running lock is released before the
    # independent stable launcher can activate a queued, verified version.
    if root and (Path(root)/'pending.json').exists():
        launcher=Path(root)/'ViewerLauncher.exe'
        if launcher.is_file():
            subprocess.Popen([str(launcher),'--activate-pending'],cwd=root)
    return code
