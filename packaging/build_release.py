"""Build local Windows x64 release assets; this script never publishes anything."""
from pathlib import Path
import argparse
from datetime import datetime,timezone
from importlib import metadata
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from spaceship_viewer import __version__
from spaceship_viewer.deployment import APP_ID,sha256


def runtime_distributions():
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    todo=['numpy','matplotlib','PySide6','astroquery','astropy']
    found={}
    while todo:
        name=todo.pop()
        key=canonicalize_name(name)
        if key in found:
            continue
        dist=metadata.distribution(name)
        found[key]=dist
        for value in dist.requires or ():
            requirement=Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({'extra':''}):
                todo.append(requirement.name)
    return found


def write_notices(folder):
    folder.mkdir()
    shutil.copy2(ROOT/'LICENSE',folder/'PROJECT_LICENSE.txt')
    shutil.copytree(ROOT/'spaceship_viewer/data',folder/'cie1931')
    inventory=[]
    for key,dist in sorted(runtime_distributions().items()):
        sub=folder/key
        sub.mkdir()
        copied=[]
        for file in dist.files or ():
            value=str(file).lower()
            if any(word in value for word in ('license','copying','notice','copyright')) and (str(file).lower().endswith(('.txt','.md','.rst')) or Path(str(file)).name.lower().startswith(('license','copying','notice','copyright'))):
                source=Path(dist.locate_file(file))
                if source.is_file():
                    target=sub/(str(file).replace('/','_').replace('\\','_'))
                    shutil.copy2(source,target)
                    copied.append(target.name)
        record={'name':dist.metadata['Name'],'version':dist.version,'license_expression':dist.metadata.get('License-Expression'),
                'license_metadata':dist.metadata.get('License'),'project_urls':dist.metadata.get_all('Project-URL') or [],
                'pypi':f"https://pypi.org/project/{dist.metadata['Name']}/{dist.version}/",'license_files':copied}
        (sub/'package_notice.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
        inventory.append(record)
    (folder/'dependency_inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    (folder/'THIRD_PARTY_NOTICES.txt').write_text('''Relativistic Spaceship Viewer is MIT licensed.
Bundled CIE 1931 observer data are CC BY-SA 4.0; see cie1931 for attribution,
original metadata, and license. This is separate from the MIT code license.
Bundled Python, NumPy, Matplotlib, PySide6/Qt, Astropy/astroquery and other
dependencies retain their own licenses. Package notices and license texts are
included in the sibling directories. CPython license text is supplied with the
Python runtime and the release source package.

Qt/PySide libraries are dynamically linked in _internal and may be replaced with
compatible modified builds. This distribution does not restrict debugging or
reverse engineering for the purpose of modifying those libraries.
Qt/PySide source and build instructions:
https://code.qt.io/cgit/qt/qtbase.git/
https://code.qt.io/cgit/pyside/pyside-setup.git/
https://doc.qt.io/qtforpython-6/gettingstarted.html
The Qt/PySide runtime version is recorded in dependency_inventory.json.
The project source and build script are supplied with the release source ZIP.
PyInstaller bootloader uses its GPL exception; see its own license notice.
''',encoding='utf-8')
    for name in ('pyinstaller','python'):
        if name=='python':
            candidates=[Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/'LICENSE']
            for path in candidates:
                if path.is_file():
                    shutil.copy2(path,folder/'PYTHON_LICENSE.txt')
                    break
        else:
            dist=metadata.distribution(name)
            for file in dist.files or ():
                if 'copying' in str(file).lower() or 'license' in str(file).lower():
                    source=Path(dist.locate_file(file))
                    if source.is_file() and source.suffix.lower() in ('','.txt','.rst','.md'):
                        shutil.copy2(source,folder/('PYINSTALLER_'+source.name))
    return inventory


def write_source_archive(output):
    """Include inspectable source, tests, original examples, and build recipes."""
    selected=[]
    folders={'spaceship_viewer','tests','tools','docs','packaging','.github'}
    for file in ROOT.rglob('*'):
        if not file.is_file():
            continue
        relative=file.relative_to(ROOT)
        if any(part in {'__pycache__','.git','build','dist','.test-tmp'} or part.endswith('.egg-info')
               for part in relative.parts) or file.suffix in {'.pyc','.pyo'}:
            continue
        if len(relative.parts)==1 or relative.parts[0] in folders:
            selected.append(file)
    records={file.relative_to(ROOT).as_posix():{'size':file.stat().st_size,'sha256':sha256(file)}
             for file in sorted(selected)}
    fingerprint=hashlib.sha256(json.dumps(records,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    manifest={'version':__version__,'published':False,'source_fingerprint':fingerprint,'files':records}
    text=json.dumps(manifest,indent=2)
    (output/'source_manifest.json').write_text(text,encoding='utf-8')
    archive=output/f'relativistic-spaceship-viewer-{__version__}-source.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as package:
        for file in sorted(selected):
            package.write(file,file.relative_to(ROOT).as_posix())
        package.writestr('source_manifest.json',text)
    shutil.copy2(ROOT/f'RELEASE_NOTES_v{__version__}.md',output/f'RELEASE_NOTES_v{__version__}.md')
    return fingerprint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    parser.add_argument('--work-dir',required=True,type=Path)
    args=parser.parse_args()
    if sys.platform!='win32' or sys.maxsize<=2**32:
        raise SystemExit('Build this release on Windows x64.')
    output=args.output_dir.resolve()
    work=args.work_dir.resolve()
    output.mkdir(parents=True,exist_ok=False)
    work.mkdir(parents=True,exist_ok=False)
    log=output/'build.log'
    # DLL discovery must not use unrelated tools (for example Poppler's ICU)
    # from the desktop PATH. Qt expects Windows' ICU ABI on this target.
    import PySide6
    build_environment=os.environ.copy()
    windows=Path(os.environ.get('WINDIR',r'C:\Windows'))
    build_environment['PATH']=os.pathsep.join([str(Path(sys.executable).parent),str(Path(sys.base_prefix)),
        str(Path(sys.base_prefix)/'DLLs'),str(Path(PySide6.__file__).parent),str(windows/'System32'),str(windows)])
    def run(command):
        with log.open('a',encoding='utf-8') as stream:
            stream.write('\nCOMMAND '+subprocess.list2cmdline(command)+'\n')
            stream.flush()
            result=subprocess.run(command,cwd=ROOT,env=build_environment,stdout=stream,stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError(f'Build command failed; see {log}')
    notices=work/'licenses'
    inventory=write_notices(notices)
    icon=work/'viewer.ico'
    shutil.copy2(ROOT/'spaceship_viewer/assets/viewer.ico',icon)
    lock='\n'.join(sorted(f"{item['name']}=={item['version']}" for item in inventory))+'\n'
    (output/'requirements-runtime.lock').write_text(lock,encoding='utf-8')
    base=[sys.executable,'-X','utf8','-m','PyInstaller','--noconfirm','--noupx',
          '--paths',str(ROOT),'--additional-hooks-dir',str(ROOT/'packaging/hooks'),
          '--specpath',str(work/'specs'),'--workpath',str(work/'analysis'),'--icon',str(icon)]
    app_dist=work/'application'
    command=base+['--onedir','--windowed','--name','RelativisticSpaceshipViewer','--distpath',str(app_dist),
                   '--collect-data','astroquery','--collect-data','astropy','--collect-data','pyvo',
                   '--copy-metadata','astroquery','--copy-metadata','astropy','--copy-metadata','pyvo',
                   '--copy-metadata','keyring','--hidden-import','astroquery.vizier.core',
                   '--hidden-import','matplotlib.backends.backend_svg',
                   '--hidden-import','matplotlib.backends.backend_pdf',
                   '--exclude-module','astroquery.vizier.tests',
                   '--add-data',str(notices)+os.pathsep+'licenses',
                   '--add-data',str(ROOT/'spaceship_viewer/data')+os.pathsep+'spaceship_viewer/data',
                   '--add-data',str(ROOT/'spaceship_viewer/assets')+os.pathsep+'spaceship_viewer/assets']
    # Real .py bytes accompany the frozen .pyz so export provenance hashes and
    # inspectable source remain available without relying on a developer checkout.
    for file in (ROOT/'spaceship_viewer').glob('*.py'):
        command += ['--add-data',str(file)+os.pathsep+'spaceship_viewer']
    command += [str(ROOT/'packaging/runtime_entry.py')]
    run(command)
    application=app_dist/'RelativisticSpaceshipViewer'
    unexpected_icu=list(application.rglob('icuuc.dll'))
    if unexpected_icu:
        raise RuntimeError('Unexpected bundled ICU DLL; verify ABI before distribution: '+str(unexpected_icu))
    if any('virtualkeyboard' in file.name.lower() for file in application.rglob('*')):
        raise RuntimeError('Unused Qt Virtual Keyboard plugin must not be bundled.')
    files={file.relative_to(application).as_posix():{'size':file.stat().st_size,'sha256':sha256(file)}
           for file in sorted(application.rglob('*')) if file.is_file()}
    manifest={'app_id':APP_ID,'protocol':1,'platform':'windows-x64','version':__version__,
              'entrypoint':'RelativisticSpaceshipViewer.exe','files':files,
              'created_utc':datetime.now(timezone.utc).isoformat(),'source_status':'local release preparation; no publication'}
    (application/'package.manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=output/f'relativistic-spaceship-viewer-{__version__}-windows-x64.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as package:
        for file in sorted(application.rglob('*')):
            if file.is_file():
                package.write(file,file.relative_to(application).as_posix())
    helper_dist=work/'helper'
    # Explicit source bytes are collected as data only for the application;
    # these helper executables import solely the stdlib deployment module.
    run(base+['--onefile','--windowed','--name','ViewerLauncher','--distpath',str(helper_dist),
              str(ROOT/'packaging/windows_helper.py')])
    launcher=helper_dist/'ViewerLauncher.exe'
    setup_name=f'relativistic-spaceship-viewer-{__version__}-windows-x64-setup'
    setup_data=work/'setup_data'
    setup_data.mkdir()
    embedded=setup_data/'release_payload.zip'
    shutil.copy2(archive,embedded)
    run(base+['--onefile','--windowed','--name',setup_name,'--distpath',str(output),
              '--add-data',str(embedded)+os.pathsep+'.','--add-data',str(launcher)+os.pathsep+'.',
              str(ROOT/'packaging/windows_helper.py')])
    shutil.copy2(launcher,output/'ViewerLauncher.exe')
    run([sys.executable,'-X','utf8','-m','pip','wheel','--no-deps','--no-build-isolation','--no-index','--wheel-dir',str(output),'.'])
    fingerprint=write_source_archive(output)
    artifacts={file.name:{'size':file.stat().st_size,'sha256':sha256(file)} for file in sorted(output.iterdir())
               if file.is_file() and file.name!='build.log'}
    (output/'release_manifest.json').write_text(json.dumps({'version':__version__,'platform':'windows-x64',
               'published':False,'source_fingerprint':fingerprint,'artifacts':artifacts},indent=2),encoding='utf-8')
    (output/'SHA256SUMS.txt').write_text(''.join(f"{value['sha256']}  {name}\n" for name,value in artifacts.items()),encoding='utf-8')
    print(json.dumps({'output':str(output),'runtime_files':len(files),'artifacts':list(artifacts)},indent=2))


if __name__=='__main__':
    main()
