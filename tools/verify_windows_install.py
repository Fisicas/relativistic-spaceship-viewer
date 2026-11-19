"""Exercise a prepared setup in an isolated per-user-like folder on Windows.

This uses real frozen executables with a PATH containing only Windows tools.
The same-version repair package is a local test fixture, never a release asset.
No registry entry or actual Start menu shortcut is created by this test.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from spaceship_viewer import deployment as deploy
from spaceship_viewer import __version__


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets',required=True,type=Path)
    parser.add_argument('--work-dir',required=True,type=Path)
    parser.add_argument('--report',required=True,type=Path)
    args=parser.parse_args()
    args.work_dir.mkdir(parents=True,exist_ok=False)
    assert not args.report.exists()
    work=args.work_dir.resolve()
    assets=args.assets.resolve()
    root=work/'Installation with spaces'
    env=os.environ.copy()
    windows=Path(os.environ.get('WINDIR',r'C:\Windows'))
    env['PATH']=os.pathsep.join(str(p) for p in (windows/'System32',windows,windows/'System32/WindowsPowerShell/v1.0'))
    env.pop('PYTHONPATH',None)
    env.pop('PYTHONHOME',None)
    env['LOCALAPPDATA']=str(work/'Local app data')
    env['APPDATA']=str(work/'Roaming app data')
    settings=Path(env['LOCALAPPDATA'])/'RelativisticSpaceshipViewer'
    settings.mkdir(parents=True)
    deploy.atomic_json(settings/'update-settings.json',{'check_on_startup':False})
    original=settings/'synthetic-user-data.txt'
    original.write_text('Synthetic preservation fixture; no measured spectrum.\n',encoding='utf-8')
    original_hash=deploy.sha256(original)
    checks=[]
    def check(condition,name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    def run(command,timeout=180):
        result=subprocess.run(list(map(str,command)),cwd=work,env=env,timeout=timeout)
        if result.returncode:
            raise RuntimeError(f'Command failed ({result.returncode}): {command}')
    def terminate_viewer(pid):
        # Stop only the process launched by this fixture. This intentionally
        # tests OS-lock release and next-launch recovery after a process exit.
        if os.name!='nt':
            raise RuntimeError('Windows-only fixture')
        subprocess.run([str(windows/'System32/taskkill.exe'),'/PID',str(pid),'/F'],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+10
        while deploy.app_running(root) and time.monotonic()<deadline:
            time.sleep(.05)
        check(not deploy.app_running(root),'owned test process exits and releases running lock')
    def launched(result_name):
        path=work/result_name
        run([root/'ViewerLauncher.exe','--quiet','--result',path])
        result=json.loads(path.read_text(encoding='utf-8'))
        check(result['status']=='passed','stable launcher starts without Python/Git PATH')
        return deploy.read_json(root/'running.json')['pid']

    setup=next(assets.glob('*-windows-x64-setup.exe'))
    install_result=work/'install-result.json'
    run([setup,'--quiet','--no-registration','--install-root',root,'--shortcut-directory',work/'Synthetic Start menu',
         '--result',install_result])
    check(json.loads(install_result.read_text(encoding='utf-8'))['status']=='passed','setup installs into an empty path with spaces')
    first=deploy.active_state(root)['active']
    shortcut=work/'Synthetic Start menu/Relativistic Spaceship Viewer.lnk'
    check(shortcut.exists(),'Start menu shortcut creation')
    check(deploy.verify_folder(deploy.slot_folder(root,first))['version']==__version__,'installed files verify against manifest')
    first_pid=launched('launch-first.json')
    duplicate=work/'duplicate.json'
    run([root/'ViewerLauncher.exe','--quiet','--result',duplicate])
    check(json.loads(duplicate.read_text())['result'].get('already_running') is True,'second launch restores existing instance')
    check(deploy.read_json(root/'running.json')['pid']==first_pid,'second launch does not create a second viewer')

    # A metadata-labeled repair build exercises actual staging/activation using
    # the real same-version binary. Version ordering is tested independently
    # with controlled 0.2.1 API/package fixtures in the unit suite.
    package=next(assets.glob('*-windows-x64.zip'))
    repair=work/'TEST_FIXTURE_same_version_repair.zip'
    with zipfile.ZipFile(package) as source,zipfile.ZipFile(repair,'x',zipfile.ZIP_DEFLATED) as target:
        manifest=json.loads(source.read('package.manifest.json'))
        marker=b'Local same-version repair/update fixture. Not a published release.\n'
        manifest['test_fixture']='same-version repair; do not publish'
        manifest['files']['REPAIR_TEST_FIXTURE.txt']={'size':len(marker),'sha256':hashlib.sha256(marker).hexdigest()}
        for item in source.infolist():
            if item.filename!='package.manifest.json':
                target.writestr(item,source.read(item))
        target.writestr('REPAIR_TEST_FIXTURE.txt',marker)
        target.writestr('package.manifest.json',json.dumps(manifest,indent=2))
    with_env=dict(os.environ)
    # Staged self-tests inherit these isolated settings but never fetch a release.
    os.environ.update({key:env[key] for key in ('PATH','LOCALAPPDATA','APPDATA')})
    try:
        second=deploy.stage_archive(root,repair)
        deploy.queue_activation(root,second)
        try:
            deploy.activate_pending(root)
        except deploy.DeploymentError:
            checks.append('running app blocks mid-session activation')
        else:
            raise AssertionError('activation should be blocked')
        try:
            deploy.stage_archive(root,package,expected_sha256='0'*64)
        except deploy.DeploymentError:
            checks.append('corrupt archive digest rejected without changing active build')
        else:
            raise AssertionError('bad digest should fail')
    finally:
        os.environ.clear()
        os.environ.update(with_env)
    check(deploy.active_state(root)['active']==first,'staging leaves current build active')
    terminate_viewer(first_pid)
    second_pid=launched('launch-after-update.json')
    state=deploy.active_state(root)
    check(state['active']==second and state['previous']==first,'next launch activates verified repair and retains previous build')
    terminate_viewer(second_pid)
    run([root/'ViewerLauncher.exe','--rollback','--quiet','--result',work/'rollback.json'])
    check(deploy.active_state(root)['active']==first,'rollback restores the previous healthy build')
    check(deploy.sha256(original)==original_hash,'settings/data fixture unchanged by update and rollback')

    user_added=deploy.slot_folder(root,first)/'synthetic-user-added-spectrum.txt'
    user_added.write_text('User-added preservation fixture; no measured data.\n',encoding='utf-8')
    uninstall_result=work/'uninstall.json'
    run([root/'ViewerLauncher.exe','--uninstall','--quiet','--result',uninstall_result])
    deadline=time.monotonic()+60
    while not uninstall_result.exists() and time.monotonic()<deadline:
        time.sleep(.1)
    check(uninstall_result.exists() and json.loads(uninstall_result.read_text())['status']=='passed','uninstall completes outside the running helper executable')
    check(user_added.exists() and deploy.sha256(original)==original_hash,'uninstall preserves user-added files and external data')
    check(not shortcut.exists(),'uninstall removes its own shortcut')
    result={'status':'passed','checks':checks,'work_dir':str(work),'assets':str(assets),
            'network':'not used','registry':'not modified','platform':'same Windows user and host; isolated folders',
            'update_fixture':'actual frozen binary in a clearly labeled same-version repair package; not a real future release',
            'limitations':['not a clean second Windows machine','not a published GitHub download/update test']}
    with args.report.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
