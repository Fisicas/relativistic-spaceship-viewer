"""Small standalone setup/launcher; does not import Qt, NumPy, or Matplotlib."""
from pathlib import Path
import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
if not getattr(sys,'frozen',False):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spaceship_viewer import deployment as deploy


def message(text,title='Relativistic Spaceship Viewer',question=False):
    if os.name=='nt':
        return ctypes.windll.user32.MessageBoxW(None,str(text),title,0x24 if question else 0x40)
    if sys.stdout:
        print(text)
    return 6


def restore_running(root):
    if os.name!='nt' or not (root/'running.json').exists():
        return
    wanted=deploy.read_json(root/'running.json')['pid']
    from ctypes import wintypes
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    @callback_type
    def visit(hwnd,param):
        pid=wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==wanted and ctypes.windll.user32.IsWindowVisible(hwnd):
            ctypes.windll.user32.ShowWindow(hwnd,9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return False
        return True
    ctypes.windll.user32.EnumWindows(visit,0)


def launch_or_restore(root):
    root=deploy.checked_root(root)
    lock=deploy.FileLock(root/'.launch.lock')
    deadline=time.monotonic()+15
    while True:
        if deploy.app_running(root):
            restore_running(root)
            return {'already_running':True}
        try:
            lock.acquire()
            break
        except deploy.DeploymentError:
            if time.monotonic()>=deadline:
                raise
            time.sleep(.05)
    try:
        if deploy.app_running(root):
            restore_running(root)
            return {'already_running':True}
        process=deploy.launch_active(root)
        while process.poll() is None and not deploy.app_running(root) and time.monotonic()<deadline:
            time.sleep(.05)
        if process.poll() not in (None,0):
            raise deploy.DeploymentError('The viewer did not complete startup. The installed version was retained.')
        return {'pid':process.pid,'root':str(root)}
    finally:
        lock.release()


def install(root,package,launcher,shortcuts=True,shortcut_directory=None):
    root=deploy.checked_root(root,initialize=True)
    if deploy.app_running(root):
        raise deploy.DeploymentError('Close the viewer before installing. No active files were changed.')
    slot=deploy.stage_archive(root,package)
    with deploy.FileLock(root/'.operation.lock'):
        target=root/'ViewerLauncher.exe'
        if target.exists() and (root/'install-record.json').exists():
            record=deploy.read_json(root/'install-record.json')
            if deploy.sha256(target)!=record['launcher_sha256']:
                raise deploy.DeploymentError('Existing stable launcher was modified; refusing to replace it.')
        elif target.exists():
            raise deploy.DeploymentError('Unrecognized launcher already exists.')
        temporary=root/('ViewerLauncher.'+str(os.getpid())+'.new.exe')
        shutil.copy2(launcher,temporary)
        os.replace(temporary,target)
        deploy.atomic_json(root/'install-record.json',{'launcher_sha256':deploy.sha256(target),
                            'installed_utc':deploy.utc_now(),'shortcuts':[]})
    state=deploy.activate(root,slot)
    shortcut=None
    if shortcuts:
        folder=Path(shortcut_directory) if shortcut_directory else Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'
        shortcut=folder/'Relativistic Spaceship Viewer.lnk'
        if not shortcut.exists():
            deploy.create_shortcut(shortcut,target,deploy.data_root())
        else:
            # Do not replace unrelated shortcuts. Verify an existing one points
            # to this installation before accepting it as our own.
            env=os.environ.copy()
            env.update(RSV_SHORTCUT_PATH=str(shortcut),RSV_TARGET_PATH=str(target))
            cmd="$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:RSV_SHORTCUT_PATH); if($s.TargetPath -ne $env:RSV_TARGET_PATH){exit 7}"
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',cmd],env=env,check=True,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        record=deploy.read_json(root/'install-record.json')
        record['shortcuts']=[str(shortcut)]
        deploy.atomic_json(root/'install-record.json',record)
    return {'root':str(root),'active':state['active'],'shortcut':str(shortcut) if shortcut else None}


def register_install(root):
    import winreg
    location=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\RelativisticSpaceshipViewer'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,location) as key:
            previous=winreg.QueryValueEx(key,'InstallLocation')[0]
        if Path(previous).resolve()!=Path(root).resolve():
            raise deploy.DeploymentError('Another install location is already registered for this user.')
    except FileNotFoundError:
        pass
    active=deploy.active_state(root)['active']
    version=deploy.read_json(deploy.slot_folder(root,active)/'package.manifest.json')['version']
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,location) as key:
        for name,value in {'DisplayName':'Relativistic Spaceship Viewer','DisplayVersion':version,'Publisher':'Fisicas',
                           'InstallLocation':str(root),'DisplayIcon':str(root/'ViewerLauncher.exe'),
                           'UninstallString':subprocess.list2cmdline([str(root/'ViewerLauncher.exe'),'--uninstall'])}.items():
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
        winreg.SetValueEx(key,'NoModify',0,winreg.REG_DWORD,1)
        winreg.SetValueEx(key,'NoRepair',0,winreg.REG_DWORD,1)


def uninstall(root):
    root=deploy.checked_root(root)
    if deploy.app_running(root):
        raise deploy.DeploymentError('Close the viewer before uninstalling.')
    record=deploy.read_json(root/'install-record.json')
    with deploy.FileLock(root/'.operation.lock'):
        for shortcut in record.get('shortcuts',[]):
            env=os.environ.copy()
            env.update(RSV_SHORTCUT_PATH=shortcut,RSV_TARGET_PATH=str(root/'ViewerLauncher.exe'))
            cmd="if(Test-Path -LiteralPath $env:RSV_SHORTCUT_PATH){$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:RSV_SHORTCUT_PATH); if($s.TargetPath -eq $env:RSV_TARGET_PATH){Remove-Item -LiteralPath $env:RSV_SHORTCUT_PATH}}"
            subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',cmd],env=env,check=True,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        versions=root/'versions'
        for folder in versions.iterdir() if versions.exists() else ():
            manifest_file=folder/'package.manifest.json'
            if not manifest_file.is_file() or not folder.resolve().is_relative_to(versions.resolve()):
                continue
            manifest=deploy.validate_manifest(deploy.read_json(manifest_file))
            parents=set()
            for name in list(manifest['files'])+['package.manifest.json','.health.json']:
                path=folder/str(deploy.safe_member(name))
                if not path.resolve().is_relative_to(folder.resolve()):
                    raise deploy.DeploymentError('Refusing to remove a file outside its application version.')
                if path.is_file():
                    path.unlink()
                parents.update(p for p in path.parents if p.is_relative_to(folder))
            for parent in sorted(parents,key=lambda p:len(p.parts),reverse=True):
                try:
                    parent.rmdir()
                except OSError:
                    pass  # user-added files are preserved
        try:
            versions.rmdir()
        except OSError:
            pass
        for name in ('ViewerLauncher.exe','active.json','pending.json','running.json','last_update_error.json','install-record.json'):
            path=root/name
            if path.is_file():
                for attempt in range(30):
                    try:
                        path.unlink()
                        break
                    except PermissionError:
                        if attempt==29:
                            raise
                        time.sleep(.1)
    for name in ('.operation.lock','.running.lock','.launch.lock',deploy.MARKER):
        path=root/name
        if path.is_file():
            path.unlink()
    import winreg
    registry=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\RelativisticSpaceshipViewer'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,registry) as key:
            owned=Path(winreg.QueryValueEx(key,'InstallLocation')[0]).resolve()==root
        if owned:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER,registry)
    except FileNotFoundError:
        pass
    try:
        root.rmdir()
    except OSError:
        pass
    return {'uninstalled':True,'remaining_folder':str(root) if root.exists() else None,
            'user_data_preserved':str(deploy.data_root())}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install-root',type=Path)
    parser.add_argument('--package',type=Path)
    parser.add_argument('--launcher',type=Path)
    parser.add_argument('--quiet',action='store_true')
    parser.add_argument('--no-shortcuts',action='store_true')
    parser.add_argument('--shortcut-directory',type=Path)
    parser.add_argument('--result',type=Path)
    parser.add_argument('--activate-pending',action='store_true')
    parser.add_argument('--rollback',action='store_true')
    parser.add_argument('--status',action='store_true')
    parser.add_argument('--uninstall',action='store_true')
    parser.add_argument('--no-registration',action='store_true')
    args=parser.parse_args()
    bundled=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))
    is_setup=(bundled/'release_payload.zip').exists()
    root=args.install_root or (deploy.default_root() if is_setup else Path(sys.executable).parent)
    try:
        if is_setup or args.package:
            package=args.package or bundled/'release_payload.zip'
            launcher=args.launcher or bundled/'ViewerLauncher.exe'
            if not args.quiet and message('Install Relativistic Spaceship Viewer for this Windows user?\n\n'+str(root)+
                                        '\n\nPython and Git are not required. A Start menu shortcut will be created.',question=True)!=6:
                return 0
            result=install(root,package,launcher,not args.no_shortcuts,args.shortcut_directory)
            if not args.no_registration:
                register_install(Path(result['root']))
            if not args.quiet:
                message('Installation complete. Open Relativistic Spaceship Viewer from the Start menu.')
        elif args.uninstall:
            if not args.quiet and message('Remove the installed viewer?\nSaved scenes, exports, and app data are preserved.',question=True)!=6:
                return 0
            if Path(sys.executable).resolve().is_relative_to(Path(root).resolve()):
                temporary=Path(tempfile.mkdtemp(prefix='rsv-uninstall-'))/'ViewerUninstall.exe'
                shutil.copy2(sys.executable,temporary)
                command=[str(temporary),'--uninstall','--quiet','--install-root',str(root)]
                if args.result:
                    command+=['--result',str(args.result)]
                subprocess.Popen(command,cwd=temporary.parent)
                return 0
            result=uninstall(root)
            if not args.quiet:
                message('Viewer removed. Your saved scenes, exports, and app data were preserved.')
        elif args.status:
            result=deploy.active_state(root)
        elif args.rollback:
            result=deploy.rollback(root)
            if not args.quiet:
                message('The previous installed build has been restored.')
        elif args.activate_pending:
            result=deploy.activate_pending(root)
        else:
            result=launch_or_restore(root)
        if args.result:
            with args.result.open('x',encoding='utf-8') as stream:
                json.dump({'status':'passed','result':result},stream,indent=2)
        return 0
    except Exception as exc:
        if args.result:
            args.result.write_text(json.dumps({'status':'failed','error':str(exc)},indent=2),encoding='utf-8')
        if not args.quiet:
            message(str(exc),'Viewer setup / launcher')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
