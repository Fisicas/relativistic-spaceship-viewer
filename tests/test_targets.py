from dataclasses import replace
import json
import unittest
import numpy as np
from spaceship_viewer.catalog import StarCatalog,CatalogMetadata
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.targets import ReferenceTarget
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.session import make_document,decode_document
from spaceship_viewer.state import ViewState
from spaceship_viewer.scene import compute_scene


class ReferenceTests(unittest.TestCase):
    def test_reference_round_trip_keeps_original_data_and_background_separate(self):
        target=ReferenceTarget.from_catalog(built_in_catalog(),16)
        sky=StarCatalog(['HIP fixture'],[1.],[2.],[3.],[np.nan],[np.nan],
                        metadata=CatalogMetadata(source='Synthetic background; not observational data'))
        state=ViewState(beta=.9)
        appearance=Presentation(reference_target=target)
        document=json.loads(json.dumps(make_document(sky,state,appearance),allow_nan=False))
        reopened,restored,settings,_=decode_document(document)
        self.assertEqual(settings.reference_target,target)
        self.assertEqual(settings.reference_target.name,'Pollux')
        self.assertEqual(reopened.n,1)
        self.assertEqual(reopened.name[0],'HIP fixture')
        self.assertEqual(settings.reference_target.metadata.coordinate_epoch,'unspecified')
        np.testing.assert_array_equal(compute_scene(reopened,restored).doppler,compute_scene(sky,state).doppler)

    def test_legacy_scene_without_reference_field_loads(self):
        document=make_document(built_in_catalog(),ViewState(),Presentation(selected_row=0))
        document['presentation'].pop('reference_target')
        _,_,settings,_=decode_document(document)
        self.assertEqual(settings.selected_row,0)
        self.assertIsNone(settings.reference_target)

    def test_reference_validation_and_exclusive_selection(self):
        target=ReferenceTarget.from_catalog(built_in_catalog(),8)
        self.assertEqual(target.object_kind,'extended_demo')
        with self.assertRaises(ValueError):
            Presentation(selected_row=0,reference_target=target)
        with self.assertRaises(ValueError):
            replace(target,dec_deg=91.)
