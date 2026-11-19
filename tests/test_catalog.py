from pathlib import Path
import tempfile
import unittest
import numpy as np
from spaceship_viewer.catalog import (CatalogImportError, CatalogMetadata, StarCatalog,
                                      UnitRequiredError, catalog_from_hipparcos_table, load_csv)
from spaceship_viewer.demo_catalog import built_in_catalog


class CSVTests(unittest.TestCase):
    def setUp(self):
        temp_root = Path(__file__).resolve().parents[1] / '.test-tmp'
        temp_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.path = Path(self.temp.name) / 'input.csv'

    def tearDown(self):
        assert Path(self.temp.name).resolve().is_relative_to(Path(__file__).resolve().parents[1] / '.test-tmp')
        self.temp.cleanup()

    def load(self, text, **kwargs):
        self.path.write_text(text, encoding='utf-8-sig')
        return load_csv(self.path, **kwargs)

    def test_explicit_degrees_below_24_are_not_hours(self):
        cat = self.load('ra_deg,dec_deg,vmag\n12,0,1\n20,4,2\n')
        np.testing.assert_array_equal(cat.ra_deg, [12., 20.])
        self.assertEqual(cat.import_report.accepted_rows, 2)
        self.assertEqual(len(cat.metadata.source_sha256), 64)

    def test_generic_ra_requires_units_even_above_24(self):
        for ra in (12, 250):
            with self.subTest(ra=ra), self.assertRaises(UnitRequiredError):
                self.load(f'ra,dec,mag\n{ra},0,1\n')

    def test_explicit_hours_and_wrap(self):
        cat = self.load('ra_hours,dec,mag\n12,0,1\n25,0,1\n')
        np.testing.assert_array_equal(cat.ra_deg, [180., 15.])
        self.assertIn('1 accepted RA values wrapped', cat.import_report.summary())

    def test_conflicting_unit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            self.load('ra_deg,dec,mag\n12,0,1\n', ra_unit='hour')

    def test_hyg_style_requires_both_units(self):
        text = 'ra,dec,mag,ci,proper,dist\n12,0,1,.3,A,2\n'
        with self.assertRaises(UnitRequiredError):
            self.load(text, ra_unit='hour')
        cat = self.load(text, ra_unit='hour', distance_unit='pc')
        self.assertEqual(cat.ra_deg[0], 180.)
        self.assertEqual(cat.distance_pc[0], 2.)

    def test_parallax_mas_and_arcsec(self):
        for header, value in (('parallax_mas', '100'), ('parallax_arcsec', '.1')):
            with self.subTest(header=header):
                cat = self.load(f'ra_deg,dec,mag,{header}\n12,0,1,{value}\n')
                self.assertAlmostEqual(cat.distance_pc[0], 10.)

    def test_generic_parallax_needs_unit(self):
        text = 'ra_deg,dec,mag,parallax\n12,0,1,100\n'
        with self.assertRaises(UnitRequiredError):
            self.load(text)
        self.assertAlmostEqual(self.load(text, parallax_unit='mas').distance_pc[0], 10.)

    def test_invalid_parallax_is_unknown(self):
        cat = self.load('ra_deg,dec,mag,parallax_mas\n0,0,1,-5\n1,0,1,0\n2,0,1,\n')
        self.assertTrue(np.isnan(cat.distance_pc).all())
        self.assertEqual(cat.n, 3)
        self.assertIn('2 invalid optional values', cat.import_report.summary())

    def test_distance_and_parallax_conflict(self):
        with self.assertRaisesRegex(ValueError, 'Both distance and parallax'):
            self.load('ra_deg,dec,mag,distance_pc,parallax_mas\n1,0,1,10,100\n')

    def test_invalid_required_rows_reported_with_lines(self):
        cat = self.load('ra_deg,dec,mag\n1,0,1\n2,91,2\nnan,0,2\n3,0,inf\n4,0\n')
        self.assertEqual(cat.n, 1)
        self.assertEqual(cat.import_report.total_rows, 5)
        self.assertEqual([r.line for r in cat.import_report.rejected], [3, 4, 5, 6])

    def test_all_invalid_exposes_report(self):
        with self.assertRaises(CatalogImportError) as caught:
            self.load('ra_deg,dec,mag\nwrong,0,1\n')
        self.assertEqual(caught.exception.report.accepted_rows, 0)
        self.assertEqual(caught.exception.report.rejected[0].line, 2)

    def test_optional_missing_and_invalid_not_solar_catalog_values(self):
        cat = self.load('ra_deg,dec,mag,bv,distance_pc\n1,0,1,,\n2,0,1,bad,-2\n')
        self.assertTrue(np.isnan(cat.bv).all())
        self.assertTrue(np.isnan(cat.distance_pc).all())
        self.assertIn('2 invalid optional values', cat.import_report.summary())

    def test_order_duplicates_and_ra_wrap_preserved(self):
        cat = self.load('name,ra_deg,dec,mag\nB,370,0,2\nA,-10,0,1\nA,-10,0,1\n')
        np.testing.assert_array_equal(cat.name, ['B', 'A', 'A'])
        np.testing.assert_array_equal(cat.ra_deg, [10, 350, 350])
        np.testing.assert_array_equal(cat.limited(1.).name, ['A', 'A'])

    def test_ambiguous_or_duplicate_columns_rejected(self):
        for header in ('ra_deg,RA_DEG,dec,mag', 'ra_deg,ra_hours,dec,mag'):
            with self.subTest(header=header), self.assertRaises(ValueError):
                self.load(header+'\n1,2,0,1\n')

    def test_no_header_or_missing_magnitude(self):
        for text in ('', 'ra_deg,dec\n1,2\n'):
            with self.assertRaises(ValueError):
                self.load(text)

    def test_unused_uncertainty_column_is_reported_not_propagated(self):
        cat = self.load('ra_deg,dec,mag,sigma_mag\n1,0,1,.05\n')
        self.assertIn('sigma_mag', cat.import_report.summary())
        self.assertIn('not processed', cat.import_report.summary())


class CatalogTests(unittest.TestCase):
    def test_demo_data_and_extended_placeholder(self):
        cat = built_in_catalog()
        self.assertEqual(cat.n, 33)
        self.assertEqual(cat.object_kind[8], 'extended_demo')
        self.assertEqual(cat.metadata.coordinate_epoch, 'unspecified')
        self.assertIn('original measurement citations', cat.metadata.notes[0])

    def test_columns_are_copied_and_read_only(self):
        ra = np.array([1.])
        cat = StarCatalog(['A'], ra, [0.], [1.], [np.nan], [np.nan])
        ra[0] = 5.
        self.assertEqual(cat.ra_deg[0], 1.)
        with self.assertRaises(ValueError):
            cat.ra_deg[0] = 3.

    def test_metadata_preserved_after_filter(self):
        cat = built_in_catalog()
        limited = cat.limited(1.)
        self.assertIs(limited.metadata, cat.metadata)
        self.assertLess(limited.n, cat.n)

    def test_invalid_direct_catalog_rejected(self):
        for ra, dec, mag, dist in (([1., 2.], [0.], [1.], [np.nan]),
                                    ([1.], [91.], [1.], [np.nan]),
                                    ([1.], [0.], [np.nan], [np.nan]),
                                    ([1.], [0.], [1.], [-1.])):
            with self.assertRaises(ValueError):
                StarCatalog(['A'], ra, dec, mag, [np.nan], dist)

    def test_masked_hipparcos_optional_values(self):
        tab = {'HIP': [1, 2, 3], 'RAICRS': [1., 2., 3.], 'DEICRS': [0., 1., 91.],
               'Vmag': [1., 2., 3.], 'B-V': np.ma.array([.4, 999., .2], mask=[False, True, False]),
               'Plx': np.ma.array([100., 999., 2.], mask=[False, True, False])}
        cat = catalog_from_hipparcos_table(tab, 8.)
        self.assertEqual(cat.n, 2)
        self.assertTrue(np.isnan(cat.bv[1]))
        self.assertTrue(np.isnan(cat.distance_pc[1]))
        self.assertEqual(cat.distance_pc[0], 10.)
        self.assertEqual(cat.metadata.coordinate_frame, 'ICRS')
        self.assertEqual(cat.metadata.coordinate_epoch, 'J1991.25 (TT)')
        self.assertEqual(len(cat.import_report.rejected), 1)


if __name__ == '__main__':
    unittest.main()
