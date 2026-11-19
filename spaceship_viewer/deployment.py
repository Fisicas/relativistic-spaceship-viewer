"""Per-user versioned deployment; standard library only, no scientific/GUI imports.

Published updates are discovered exclusively from this project's GitHub stable
releases. GitHub API asset digests plus HTTPS identify downloads; the package
manifest verifies every extracted file. These are integrity checks, not a code
signature. The active pointer changes only after a successful package self-test.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zipfile

APP_ID = 'org.fisicas.relativistic-spaceship-viewer'
REPOSITORY = 'Fisicas/relativistic-spaceship-viewer'
API_URL = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
MAX_DOWNLOAD = 700 * 1024 * 1024
MAX_EXTRACTED = 2 * 1024 * 1024 * 1024
MARKER = '.viewer-install.json'


class DeploymentError(RuntimeError):
    pass


def version_tuple(version):
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', version):
        raise DeploymentError('A stable three-part version is required.')
    return tuple(map(int, version.split('.')))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, allow_nan=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def default_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'Programs/RelativisticSpaceshipViewer'


def data_root():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'RelativisticSpaceshipViewer'


def checked_root(root, *, initialize=False):
    root = Path(root).absolute()
    # Reject junction/symlink components rather than following user-controlled
    # paths while installing or removing application-owned files.
    for component in (root, *root.parents):
        if component.exists() and (component.is_symlink() or getattr(component, 'is_junction', lambda: False)()):
            raise DeploymentError('Install paths must not contain junctions or symbolic links.')
    if initialize and not root.exists():
        root.mkdir(parents=True)
    if not root.exists():
        raise DeploymentError('The viewer is not installed in this folder.')
    marker = root/MARKER
    if not marker.exists():
        if not initialize or any(root.iterdir()):
            raise DeploymentError('Refusing to reuse a nonempty folder without the viewer install marker.')
        atomic_json(marker, {'app_id':APP_ID, 'protocol':1, 'created_utc':utc_now()})
    if read_json(marker).get('app_id') != APP_ID:
        raise DeploymentError('Install folder belongs to another application.')
    return root.resolve()


class FileLock:
    def __init__(self, path):
        self.path, self.stream = Path(path), None

    def acquire(self):
        self.stream = self.path.open('a+b')
        # A Windows byte-range lock also forbids reading that byte from another
        # handle. Inspect file length without reading the locked region.
        self.stream.seek(0,os.SEEK_END)
        if self.stream.tell()==0:
            self.stream.write(b'0')
            self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.stream.close()
            self.stream = None
            raise DeploymentError('The viewer or another deployment operation is still running.') from exc
        return self

    def release(self):
        if self.stream:
            self.stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_UN)
            self.stream.close()
            self.stream = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *args):
        self.release()


def app_running(root):
    try:
        with FileLock(Path(root)/'.running.lock'):
            return False
    except DeploymentError:
        return True


@contextmanager
def application_session(root):
    root = checked_root(root)
    with FileLock(root/'.running.lock'):
        atomic_json(root/'running.json', {'pid':os.getpid(), 'started_utc':utc_now()})
        try:
            yield
        finally:
            if (root/'running.json').exists() and read_json(root/'running.json').get('pid') == os.getpid():
                (root/'running.json').unlink()


def safe_member(name):
    if not isinstance(name, str) or '\\' in name or ':' in name or '\x00' in name:
        raise DeploymentError('Unsafe package path.')
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(part in ('.','..') or part.endswith((' ','.')) for part in path.parts):
        raise DeploymentError('Unsafe package path.')
    reserved = {'CON','NUL','PRN','AUX',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
    if any(part.split('.')[0].upper() in reserved for part in path.parts):
        raise DeploymentError('Reserved Windows package path.')
    return path


def validate_manifest(manifest):
    if manifest.get('app_id') != APP_ID or manifest.get('protocol') != 1 or manifest.get('platform') != 'windows-x64':
        raise DeploymentError('Unsupported application, package protocol, or platform.')
    version_tuple(manifest.get('version'))
    files = manifest.get('files')
    if not isinstance(files, dict) or not files or len(files)>10000:
        raise DeploymentError('Invalid package file list.')
    names = set()
    for name, info in files.items():
        safe_member(name)
        if name.casefold() in names or not isinstance(info, dict) or not re.fullmatch(r'[0-9a-f]{64}', str(info.get('sha256',''))):
            raise DeploymentError('Duplicate path or invalid package digest.')
        if type(info.get('size')) is not int or info['size']<0:
            raise DeploymentError('Invalid package file size.')
        names.add(name.casefold())
    if manifest.get('entrypoint') != 'RelativisticSpaceshipViewer.exe' or manifest['entrypoint'] not in files:
        raise DeploymentError('Missing viewer executable.')
    return manifest


def inspect_archive(archive):
    with zipfile.ZipFile(archive) as package:
        infos = package.infolist()
        names = [entry.filename for entry in infos]
        if len(names)!=len(set(name.casefold() for name in names)) or len(infos)>10001:
            raise DeploymentError('Duplicate or excessive archive entries.')
        if sum(entry.file_size for entry in infos)>MAX_EXTRACTED:
            raise DeploymentError('Package is larger than the supported extraction limit.')
        for entry in infos:
            safe_member(entry.filename)
            if entry.is_dir() or stat.S_ISLNK(entry.external_attr>>16):
                raise DeploymentError('Only regular package file entries are permitted.')
        try:
            info=package.getinfo('package.manifest.json')
            if info.file_size>4*1024*1024:
                raise DeploymentError('Package manifest is too large.')
            manifest=validate_manifest(json.loads(package.read(info)))
        except KeyError as exc:
            raise DeploymentError('Package manifest is missing.') from exc
        if set(names)!=set(manifest['files'])|{'package.manifest.json'}:
            raise DeploymentError('Archive files do not match its manifest.')
        return manifest


def verify_folder(folder):
    folder=Path(folder).resolve()
    manifest=validate_manifest(read_json(folder/'package.manifest.json'))
    for name,info in manifest['files'].items():
        path=folder/str(safe_member(name))
        if not path.resolve().is_relative_to(folder) or path.is_symlink() or not path.is_file():
            raise DeploymentError('Package file escaped its version folder.')
        if path.stat().st_size!=info['size'] or sha256(path)!=info['sha256']:
            raise DeploymentError(f'Package file is missing or changed: {name}')
    return manifest


def stage_archive(root, archive, *, expected_sha256=None, self_test=None):
    root=checked_root(root, initialize=True)
    archive=Path(archive)
    digest=sha256(archive)
    if expected_sha256 is not None and digest!=expected_sha256:
        raise DeploymentError('Downloaded package SHA-256 does not match the release asset digest.')
    manifest=inspect_archive(archive)
    slot=f"{manifest['version']}-{digest[:16]}"
    destination=root/'versions'/slot
    with FileLock(root/'.operation.lock'):
        if destination.exists():
            verify_folder(destination)
            return slot
        versions=root/'versions'
        versions.mkdir(exist_ok=True)
        staging=versions/('.staging-'+uuid.uuid4().hex)
        staging.mkdir()
        # Do not remove a failed staging tree: retain it for diagnosis. Active
        # installation remains untouched and a later attempt uses another ID.
        with zipfile.ZipFile(archive) as package:
            for entry in package.infolist():
                target=staging/str(safe_member(entry.filename))
                assert target.resolve().is_relative_to(staging.resolve())
                target.parent.mkdir(parents=True,exist_ok=True)
                with package.open(entry) as source,target.open('xb') as out:
                    shutil.copyfileobj(source,out)
        verify_folder(staging)
        probe=self_test or run_self_test
        probe(staging,manifest['version'])
        atomic_json(staging/'.health.json',{'passed':True,'version':manifest['version'],'checked_utc':utc_now(),
                                           'archive_sha256':digest})
        staging.rename(destination)
        return slot


def run_self_test(folder, version):
    folder=Path(folder)
    result=folder/('.probe-'+uuid.uuid4().hex+'.json')
    env=os.environ.copy()
    env.pop('RSV_INSTALL_ROOT',None)
    env['QT_QPA_PLATFORM']='offscreen'
    run=subprocess.run([str(folder/'RelativisticSpaceshipViewer.exe'),'--self-test',str(result)],
                       cwd=folder,env=env,timeout=120,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if run.returncode or not result.exists() or read_json(result).get('status')!='passed' or read_json(result).get('version')!=version:
        raise DeploymentError('The staged viewer failed its startup/physics self-test; previous version retained.')
    result.unlink()


def slot_folder(root, slot):
    if not isinstance(slot,str) or not re.fullmatch(r'\d+\.\d+\.\d+-[0-9a-f]{16}',slot):
        raise DeploymentError('Invalid installed version slot.')
    path=Path(root)/'versions'/slot
    if not path.resolve().is_relative_to((Path(root)/'versions').resolve()):
        raise DeploymentError('Invalid version path.')
    return path


def active_state(root):
    root=checked_root(root)
    path=root/'active.json'
    return read_json(path) if path.exists() else {'active':None,'previous':None,'protocol':1}


def activate(root, slot):
    root=checked_root(root)
    with FileLock(root/'.operation.lock'):
        if app_running(root):
            raise DeploymentError('Close the viewer before activating a different version.')
        folder=slot_folder(root,slot)
        verify_folder(folder)
        health=read_json(folder/'.health.json')
        if not health.get('passed'):
            raise DeploymentError('The selected version has not passed its self-test.')
        previous=active_state(root)
        if previous['active']==slot:
            return previous
        state={'protocol':1,'active':slot,'previous':previous['active'],'switched_utc':utc_now()}
        atomic_json(root/'active.json',state)
        if (root/'pending.json').exists():
            (root/'pending.json').unlink()
        return state


def queue_activation(root, slot):
    root=checked_root(root)
    verify_folder(slot_folder(root,slot))
    with FileLock(root/'.operation.lock'):
        atomic_json(root/'pending.json',{'slot':slot,'queued_utc':utc_now()})


def activate_pending(root):
    root=checked_root(root)
    path=root/'pending.json'
    if path.exists():
        return activate(root,read_json(path)['slot'])
    return active_state(root)


def rollback(root):
    previous=active_state(root).get('previous')
    if not previous:
        raise DeploymentError('There is no previous installed build to restore.')
    return activate(root,previous)


def fetch_json(url):
    request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'RelativisticSpaceshipViewer'})
    with urllib.request.urlopen(request,timeout=12) as response:
        return json.loads(response.read(4*1024*1024))


def latest_release(current_version, *, reader=fetch_json):
    version_tuple(current_version)
    try:
        release=reader(API_URL)
    except urllib.error.HTTPError as exc:
        if exc.code==404:
            return None
        raise
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise DeploymentError('The update endpoint did not return a stable published release.')
    tag=release.get('tag_name','')
    if not re.fullmatch(r'v\d+\.\d+\.\d+',tag):
        raise DeploymentError('Unsupported release tag.')
    version=tag[1:]
    if version_tuple(version)<=version_tuple(current_version):
        return None
    filename=f'relativistic-spaceship-viewer-{version}-windows-x64.zip'
    assets=[asset for asset in release.get('assets',[]) if asset.get('name')==filename]
    if len(assets)!=1:
        raise DeploymentError('This release has no unique Windows x64 package.')
    asset=assets[0]
    expected=f'https://github.com/{REPOSITORY}/releases/download/{tag}/{filename}'
    digest=asset.get('digest','')
    if asset.get('browser_download_url')!=expected or not re.fullmatch(r'sha256:[0-9a-f]{64}',digest):
        raise DeploymentError('Release asset URL or GitHub SHA-256 digest is missing or invalid.')
    if type(asset.get('size')) is not int or not 0<asset['size']<=MAX_DOWNLOAD:
        raise DeploymentError('Release asset size is invalid.')
    return {'version':version,'url':expected,'sha256':digest[7:],'size':asset['size'],
            'notes':str(release.get('body','')),'release_url':f'https://github.com/{REPOSITORY}/releases/tag/{tag}'}


def download_release(root, release):
    root=checked_root(root)
    # Only use a validated official URL, even if this function is called directly.
    version_tuple(release['version'])
    expected=f"https://github.com/{REPOSITORY}/releases/download/v{release['version']}/relativistic-spaceship-viewer-{release['version']}-windows-x64.zip"
    if release['url']!=expected or not re.fullmatch(r'[0-9a-f]{64}',release['sha256']):
        raise DeploymentError('Untrusted update location or digest.')
    downloads=root/'downloads'
    downloads.mkdir(exist_ok=True)
    target=downloads/(release['version']+'-'+uuid.uuid4().hex+'.zip')
    count=0
    request=urllib.request.Request(expected,headers={'User-Agent':'RelativisticSpaceshipViewer'})
    with urllib.request.urlopen(request,timeout=30) as response,target.open('xb') as output:
        for block in iter(lambda:response.read(1024*1024),b''):
            count+=len(block)
            if count>MAX_DOWNLOAD or count>release['size']:
                raise DeploymentError('Download exceeded the declared asset size.')
            output.write(block)
    if count!=release['size'] or sha256(target)!=release['sha256']:
        raise DeploymentError('Downloaded asset failed its size/digest check.')
    return target


def prepare_update(root, release):
    archive=download_release(root,release)
    slot=stage_archive(root,archive,expected_sha256=release['sha256'])
    if read_json(slot_folder(root,slot)/'package.manifest.json')['version']!=release['version']:
        raise DeploymentError('Package version does not match its published release.')
    queue_activation(root,slot)
    return slot


def create_shortcut(destination, target, working_directory, icon=None):
    if os.name!='nt':
        raise DeploymentError('Windows shortcuts are only supported on Windows.')
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        raise DeploymentError('Shortcut already exists; refusing to replace a user-authored file.')
    env=os.environ.copy()
    env.update(RSV_SHORTCUT_PATH=str(destination),RSV_TARGET_PATH=str(target),RSV_WORKING_DIR=str(working_directory),
               RSV_ICON_PATH=str(icon or target))
    script="$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:RSV_SHORTCUT_PATH); $s.TargetPath=$env:RSV_TARGET_PATH; $s.WorkingDirectory=$env:RSV_WORKING_DIR; $s.IconLocation=$env:RSV_ICON_PATH; $s.Save()"
    subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-Command',script],env=env,check=True,
                   creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))


def launch_active(root):
    root=checked_root(root)
    if not app_running(root):
        try:
            activate_pending(root)
        except Exception as exc:
            atomic_json(root/'last_update_error.json',{'error':str(exc),'utc':utc_now()})
    state=active_state(root)
    if not state['active']:
        raise DeploymentError('No active viewer version is installed.')
    folder=slot_folder(root,state['active'])
    manifest=read_json(folder/'package.manifest.json')
    executable=folder/manifest['entrypoint']
    if sha256(executable)!=manifest['files'][manifest['entrypoint']]['sha256']:
        raise DeploymentError('The installed launcher target has changed; reinstall or roll back.')
    env=os.environ.copy()
    env['RSV_INSTALL_ROOT']=str(root)
    data_root().mkdir(parents=True,exist_ok=True)
    return subprocess.Popen([str(executable)],cwd=data_root(),env=env)
