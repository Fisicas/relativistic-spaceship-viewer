from dataclasses import replace
import gzip,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from spaceship_viewer import catalog_cache as cache
from spaceship_viewer.catalog import StarCatalog,CatalogMetadata
from spaceship_viewer.catalog_network import fetch_hipparcos

def fixture():
    return StarCatalog(['HIP 1','HIP 2'],[1.,2.],[0.,-1.],[2.,10.],[np.nan,.2],[np.nan,10.],
                       metadata=CatalogMetadata(source='Synthetic Hipparcos cache fixture',coordinate_epoch='J1991.25 (TT)'))

class CacheTests(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.test-tmp';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_roundtrip_preserves_values_missingness_order_and_metadata_offline(self):
        c=fixture();info=cache.save_cached(c,root=self.root)
        with patch('socket.socket',side_effect=AssertionError('network forbidden')):
            restored,loaded=cache.load_cached(root=self.root,minimum_limit=20.)
        for name in ('name','ra_deg','dec_deg','vmag','bv','distance_pc','object_kind'):
            np.testing.assert_array_equal(getattr(restored,name),getattr(c,name))
        self.assertEqual(restored.metadata,c.metadata);self.assertEqual(loaded,info)
    def test_subsets_do_not_claim_full_coverage(self):
        cache.save_cached(fixture(),root=self.root,server_vmag_limit=8.)
        with self.assertRaises(ValueError):cache.load_cached(root=self.root,minimum_limit=9.)
        self.assertEqual(cache.load_cached(root=self.root,minimum_limit=7.)[0].n,2)
    def test_corruption_is_rejected_and_previous_snapshot_remains(self):
        first=cache.save_cached(fixture(),root=self.root)
        new=replace(fixture(),metadata=replace(fixture().metadata,source='Second fixture'))
        second=cache.save_cached(new,root=self.root)
        self.assertTrue((self.root/first['file']).exists())
        (self.root/second['file']).write_bytes(b'corrupt')
        with self.assertRaises(ValueError):cache.load_cached(root=self.root)
        self.assertTrue((self.root/first['file']).exists())
    def test_failed_pointer_write_preserves_active_snapshot(self):
        first=cache.save_cached(fixture(),root=self.root)
        new=replace(fixture(),metadata=replace(fixture().metadata,source='Second fixture'))
        with patch.object(cache,'atomic_json',side_effect=OSError('Controlled write failure')):
            with self.assertRaises(OSError):cache.save_cached(new,root=self.root)
        self.assertEqual(cache.load_cached(root=self.root)[1],first)
    def test_pointer_traversal_and_unknown_schema_are_rejected(self):
        for info in ({'schema':cache.SCHEMA,'file':'../other.json.gz'}, {'schema':'unknown','file':'hipparcos-'+'a'*64+'.json.gz'}):
            (self.root/'latest.json').write_text(json.dumps(info))
            with self.assertRaises(ValueError):cache.load_cached(root=self.root)
    def test_preferences_are_separate_and_invalid_choices_return_ask(self):
        with patch.object(cache,'data_root',return_value=self.root):
            self.assertEqual(cache.startup_choice(),'ask')
            cache.set_startup_choice('hipparcos');self.assertEqual(cache.startup_choice(),'hipparcos')
            (self.root/'catalog-settings.json').write_text('bad JSON')
            self.assertEqual(cache.startup_choice(),'ask')
            with self.assertRaises(ValueError):cache.set_startup_choice('download without asking')
    def test_full_catalog_query_has_no_server_magnitude_filter(self):
        from types import ModuleType
        from unittest.mock import Mock
        table={'HIP':[1,2],'RAICRS':[1.,2.],'DEICRS':[0.,1.], 'Vmag':[2.,10.],'B-V':[.5,np.nan],'Plx':[100.,np.nan]}
        client=Mock();client.query_constraints.return_value=[table]
        module=ModuleType('astroquery.vizier');module.Vizier=Mock(return_value=client)
        with patch.dict('sys.modules',{'astroquery.vizier':module}):result=fetch_hipparcos(None)
        client.query_constraints.assert_called_once_with(catalog='I/239/hip_main',cache=False)
        self.assertEqual(result.n,2);self.assertIn('no server magnitude cut',result.metadata.selection)
