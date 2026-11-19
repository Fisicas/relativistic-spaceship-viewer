from dataclasses import replace
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from spaceship_viewer.catalog import StarCatalog
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.exporting import export_scene, versioned_directory
from spaceship_viewer.geometry import CameraPose
from spaceship_viewer.inspection import inspect_object
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.scene import compute_scene
from spaceship_viewer.session import make_document, decode_document, save_document, load_document
from spaceship_viewer.state import ViewState


class SessionTests(unittest.TestCase):
    def test_portable_round_trip_preserves_triads_and_numerics(self):
        catalog = built_in_catalog()
        state = ViewState(beta=math.sqrt(3)/2).with_lock(False).with_camera(CameraPose.from_radec(21., 89.).rotated(5., 3.))
        presentation = Presentation(comparison=True, selected_row=8, max_labels=17, marker_scale=.67)
        document = make_document(catalog, state, presentation, 'Example')
        recovered = decode_document(json.loads(json.dumps(document, allow_nan=False)))
        cat, view, appearance, title = recovered
        self.assertEqual(view, state)
        self.assertEqual(appearance, presentation)
        self.assertEqual(title, 'Example')
        a, b = compute_scene(catalog, state), compute_scene(cat, view)
        for field in ('apparent', 'doppler', 'visible', 'x_deg', 'y_deg', 'rgb'):
            np.testing.assert_array_equal(getattr(a, field), getattr(b, field))

    def test_unknown_values_are_json_null_not_imputed(self):
        catalog = StarCatalog(['A', 'A'], [1., 1.], [0., 0.], [1., 1.], [np.nan, .2], [np.nan, 10.])
        document = make_document(catalog, ViewState(), Presentation())
        self.assertIsNone(document['catalog']['columns']['bv'][0])
        restored, *_ = decode_document(document)
        self.assertTrue(np.isnan(restored.bv[0]))
        np.testing.assert_array_equal(restored.name, ['A', 'A'])

    def test_tampered_catalog_hash_rejected(self):
        document = make_document(built_in_catalog(), ViewState(), Presentation())
        document['catalog']['columns']['ra_deg'][0] += 1.
        with self.assertRaisesRegex(ValueError, 'hash'):
            decode_document(document)

    def test_invalid_schema_speed_and_selection_rejected(self):
        document = make_document(built_in_catalog(), ViewState(), Presentation())
        for modify in (lambda d: d.update(schema='future/99'), lambda d: d['view'].update(beta=1.),
                       lambda d: d['presentation'].update(selected_row=1000)):
            broken = copy.deepcopy(document)
            modify(broken)
            with self.assertRaises(ValueError):
                decode_document(broken)


class ExportTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / '.test-tmp'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.directory = Path(self.temp.name)

    def tearDown(self):
        assert self.directory.resolve().is_relative_to(Path(__file__).resolve().parents[1] / '.test-tmp')
        self.temp.cleanup()

    def test_scene_file_is_exclusive_and_self_contained(self):
        path = self.directory / 'scene.json'
        save_document(path, built_in_catalog(), ViewState(), Presentation())
        cat, view, appearance, title = load_document(path)
        self.assertEqual(cat.n, 33)
        with self.assertRaises(FileExistsError):
            save_document(path, cat, view, appearance)

    def test_export_all_formats_exact_dimensions_and_recomputed_arrays(self):
        catalog, state, presentation = built_in_catalog(), ViewState(beta=math.sqrt(3)/2), Presentation(comparison=True)
        folder = export_scene(self.directory, 'Orion', catalog, state, presentation, 'Orion comparison', width=1280, height=900, dpi=100)
        with Image.open(folder/'scene.png') as image:
            self.assertEqual(image.size, (1280, 900))
        self.assertEqual((folder/'scene.pdf').read_bytes()[:4], b'%PDF')
        ET.parse(folder/'scene.svg')
        self.assertFalse((folder/'INCOMPLETE.txt').exists())
        cat, view, appearance, title = load_document(folder/'scene.json')
        with np.load(folder/'scene_data.npz', allow_pickle=False) as data:
            np.testing.assert_array_equal(data['moving_doppler'], compute_scene(cat, view).doppler)
            np.testing.assert_array_equal(data['rest_doppler'], np.ones(33))
        document = json.loads((folder/'scene.json').read_text(encoding='utf-8'))
        for name, digest in document['export']['artifacts_sha256'].items():
            self.assertEqual(hashlib.sha256((folder/name).read_bytes()).hexdigest(), digest)
        self.assertEqual(document['export']['width_px'], 1280)

    def test_repeated_exports_never_overwrite_prior_result(self):
        folder = export_scene(self.directory, 'Orion', built_in_catalog(), ViewState(), Presentation(), 'Orion', width=800, height=600, dpi=100, formats=('png',))
        previous = (folder/'scene.png').read_bytes()
        next_folder = export_scene(self.directory, 'Orion', built_in_catalog(), ViewState(beta=.3), Presentation(), 'Orion', width=800, height=600, dpi=100, formats=('png',))
        self.assertNotEqual(folder, next_folder)
        self.assertEqual((folder/'scene.png').read_bytes(), previous)

    def test_unsupported_formats_and_dimensions_rejected_before_output(self):
        for kwargs in ({'width': 0}, {'height': 10000}, {'formats': ('exe',)}, {'formats': ('png', 'png')}):
            with self.assertRaises(ValueError):
                export_scene(self.directory, 'bad', built_in_catalog(), ViewState(), Presentation(), 'bad', **kwargs)
        self.assertFalse(any(self.directory.iterdir()))

    def test_windows_reserved_name_sanitized(self):
        folder = versioned_directory(self.directory, 'CON')
        self.assertEqual(folder.name, 'scene_CON_v01')


class InspectorTests(unittest.TestCase):
    def test_reference_wavelength_and_angles_use_same_boost(self):
        catalog = built_in_catalog()
        state = ViewState(beta=math.sqrt(3)/2)
        info = inspect_object(catalog, state, 0)
        scene = compute_scene(catalog, state)
        self.assertEqual(info['doppler_factor'], scene.doppler[0])
        self.assertAlmostEqual(info['shifted_wavelength_nm'] * info['doppler_factor'], 550.)
        self.assertLess(info['apparent_heading_angle_deg'], info['rest_heading_angle_deg'])

    def test_m42_identified_as_extended_placeholder(self):
        info = inspect_object(built_in_catalog(), ViewState(), 8)
        self.assertEqual(info['kind'], 'extended_demo')

    def test_unknown_optional_values_remain_unknown(self):
        catalog = StarCatalog(['A'], [1.], [0.], [1.], [np.nan], [np.nan])
        info = inspect_object(catalog, ViewState(), 0)
        self.assertIsNone(info['bv'])
        self.assertIsNone(info['distance_pc'])


if __name__ == '__main__':
    unittest.main()
