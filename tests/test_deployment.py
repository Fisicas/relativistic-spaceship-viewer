import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile
from spaceship_viewer import deployment as d


def make_package(path,version='0.2.0',extra=b'first',bad_hash=False,extra_name=None):
    files={'RelativisticSpaceshipViewer.exe':b'controlled fixture, not an executable','notes.txt':extra}
    manifest={'app_id':d.APP_ID,'protocol':1,'platform':'windows-x64','version':version,
              'entrypoint':'RelativisticSpaceshipViewer.exe',
              'files':{name:{'size':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in files.items()}}
    if bad_hash:
        manifest['files']['notes.txt']['sha256']='0'*64
    with zipfile.ZipFile(path,'x') as package:
        for name,value in files.items():
            package.writestr(name,value)
        package.writestr('package.manifest.json',json.dumps(manifest))
        if extra_name:
            package.writestr(extra_name,b'extra')
    return path


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.test-tmp'
        parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent)
        self.base=Path(self.temp.name)
        self.root=self.base/'Install folder with spaces'
        self.good=make_package(self.base/'good.zip')
        self.probe=lambda folder,version:None

    def tearDown(self):
        assert self.base.resolve().is_relative_to(Path(__file__).resolve().parents[1]/'.test-tmp')
        self.temp.cleanup()

    def stage(self,package=None,**kwargs):
        return d.stage_archive(self.root,package or self.good,self_test=self.probe,**kwargs)

    def test_clean_install_and_active_pointer(self):
        slot=self.stage()
        state=d.activate(self.root,slot)
        self.assertEqual(state['active'],slot)
        self.assertIsNone(state['previous'])
        self.assertEqual(d.verify_folder(d.slot_folder(self.root,slot))['version'],'0.2.0')

    def test_failed_self_test_preserves_current(self):
        first=self.stage()
        d.activate(self.root,first)
        next_package=make_package(self.base/'next.zip','0.2.1')
        def fail(folder,version):
            raise d.DeploymentError('controlled startup failure')
        with self.assertRaises(d.DeploymentError):
            d.stage_archive(self.root,next_package,self_test=fail)
        self.assertEqual(d.active_state(self.root)['active'],first)

    def test_update_and_rollback_keep_prior_build(self):
        first=self.stage()
        d.activate(self.root,first)
        second=self.stage(make_package(self.base/'next.zip','0.2.1'))
        d.queue_activation(self.root,second)
        self.assertEqual(d.active_state(self.root)['active'],first)
        state=d.activate_pending(self.root)
        self.assertEqual(state['previous'],first)
        self.assertEqual(d.rollback(self.root)['active'],first)
        self.assertTrue(d.slot_folder(self.root,second).exists())

    def test_activation_blocked_while_application_runs(self):
        first=self.stage()
        d.activate(self.root,first)
        second=self.stage(make_package(self.base/'next.zip','0.2.1'))
        with d.application_session(self.root):
            self.assertTrue(d.app_running(self.root))
            d.queue_activation(self.root,second)
            with self.assertRaises(d.DeploymentError):
                d.activate_pending(self.root)
        self.assertEqual(d.activate_pending(self.root)['active'],second)

    def test_corrupt_package_cannot_switch_active(self):
        first=self.stage()
        d.activate(self.root,first)
        bad=make_package(self.base/'bad.zip','0.2.1',bad_hash=True)
        with self.assertRaises(d.DeploymentError):
            self.stage(bad)
        self.assertEqual(d.active_state(self.root)['active'],first)

    def test_archive_digest_mismatch_rejected(self):
        with self.assertRaises(d.DeploymentError):
            self.stage(expected_sha256='0'*64)

    def test_path_traversal_and_unlisted_files_rejected(self):
        for i,name in enumerate(('../escape.txt','extra.txt','C:/escape.txt','a\\b.txt')):
            with self.subTest(name=name),self.assertRaises(d.DeploymentError):
                self.stage(make_package(self.base/f'bad{i}.zip',extra_name=name))
        self.assertFalse((self.base/'escape.txt').exists())

    def test_case_duplicate_rejected(self):
        archive=self.base/'duplicate.zip'
        with zipfile.ZipFile(archive,'x') as package:
            package.writestr('A.txt',b'a')
            package.writestr('a.txt',b'a')
        with self.assertRaises(d.DeploymentError):
            d.inspect_archive(archive)

    def test_occupied_non_application_directory_preserved(self):
        self.root.mkdir()
        raw=self.root/'original-spectrum.txt'
        raw.write_text('user data',encoding='utf-8')
        with self.assertRaises(d.DeploymentError):
            self.stage()
        self.assertEqual(raw.read_text(encoding='utf-8'),'user data')

    def test_repeated_package_reuses_verified_slot(self):
        first=self.stage()
        self.assertEqual(self.stage(),first)
        self.assertEqual(len([p for p in (self.root/'versions').iterdir() if not p.name.startswith('.')]),1)

    def test_staged_file_change_prevents_activation(self):
        slot=self.stage()
        (d.slot_folder(self.root,slot)/'notes.txt').write_text('modified',encoding='utf-8')
        with self.assertRaises(d.DeploymentError):
            d.activate(self.root,slot)

    def test_invalid_slot_and_reserved_paths(self):
        for name in ('../x','C:/x','versions/../x','CON','nul.txt','a/trailing.','a\\b'):
            with self.subTest(name=name),self.assertRaises(d.DeploymentError):
                d.safe_member(name)
        with self.assertRaises(d.DeploymentError):
            d.slot_folder(self.root,'../../x')

    def test_two_operations_cannot_hold_same_lock(self):
        root=d.checked_root(self.root,initialize=True)
        with d.FileLock(root/'.operation.lock'):
            with self.assertRaises(d.DeploymentError):
                with d.FileLock(root/'.operation.lock'):
                    pass


class ReleaseDiscoveryTests(unittest.TestCase):
    def release(self,version='0.2.1'):
        name=f'relativistic-spaceship-viewer-{version}-windows-x64.zip'
        return {'draft':False,'prerelease':False,'tag_name':'v'+version,'body':'Release notes',
                'assets':[{'name':name,'size':100,'digest':'sha256:'+'a'*64,
                           'browser_download_url':f'https://github.com/{d.REPOSITORY}/releases/download/v{version}/{name}'}]}

    def test_only_newer_stable_release_is_offered(self):
        result=d.latest_release('0.2.0',reader=lambda url:self.release())
        self.assertEqual(result['version'],'0.2.1')
        self.assertIsNone(d.latest_release('0.2.1',reader=lambda url:self.release()))
        self.assertIsNone(d.latest_release('0.3.0',reader=lambda url:self.release()))

    def test_no_published_release_is_normal(self):
        def absent(url):
            raise urllib.error.HTTPError(url,404,'Not found',{},None)
        self.assertIsNone(d.latest_release('0.2.0',reader=absent))

    def test_draft_prerelease_and_nonstandard_tag_rejected(self):
        for update in ({'draft':True},{'prerelease':True},{'tag_name':'main'},{'tag_name':'v0.2.1rc1'}):
            payload=self.release()
            payload.update(update)
            with self.assertRaises(d.DeploymentError):
                d.latest_release('0.2.0',reader=lambda url:payload)

    def test_missing_digest_wrong_host_and_duplicate_asset_rejected(self):
        for modify in (lambda x:x['assets'][0].update(digest=''),
                       lambda x:x['assets'][0].update(browser_download_url='https://example.com/app.zip'),
                       lambda x:x['assets'].append(x['assets'][0])):
            payload=self.release()
            modify(payload)
            with self.assertRaises(d.DeploymentError):
                d.latest_release('0.2.0',reader=lambda url:payload)

    def test_version_ordering_is_numeric(self):
        self.assertGreater(d.version_tuple('0.10.0'),d.version_tuple('0.9.9'))
        for version in ('v0.2.0','0.2.0.dev2','0.2','01.2.3'):
            with self.assertRaises(d.DeploymentError):
                d.version_tuple(version)


if __name__=='__main__':
    unittest.main()
