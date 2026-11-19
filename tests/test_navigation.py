from dataclasses import replace
import unittest
import numpy as np
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.geometry import project_directions
from spaceship_viewer.navigation import center_object, widescreen_fov
from spaceship_viewer.relativity import aberrate
from spaceship_viewer.scene import compute_scene
from spaceship_viewer.state import ViewState


class NavigationTests(unittest.TestCase):
    def test_centering_preserves_boost_and_centers_apparent_direction(self):
        catalog = built_in_catalog()
        row = catalog.name.tolist().index('Sirius')
        for beta in (0., .9, .999999):
            state = ViewState(beta=beta)
            centered = center_object(catalog, state, row)
            self.assertFalse(centered.camera_locked)
            self.assertEqual(centered.beta, state.beta)
            np.testing.assert_array_equal(centered.velocity_direction, state.velocity_direction)
            np.testing.assert_array_equal(compute_scene(catalog, centered).doppler, compute_scene(catalog, state).doppler)
            apparent, _, _ = aberrate(catalog.vectors[row:row+1], state.velocity_direction, beta)
            x, y, visible = project_directions(apparent, centered.camera)
            np.testing.assert_allclose([x[0], y[0]], [0., 0.], atol=1e-11)
            self.assertTrue(visible[0])

    def test_centering_does_not_override_magnitude_filter(self):
        catalog = built_in_catalog()
        state = ViewState(rest_mag_limit=-5.)
        centered = center_object(catalog, state, 0)
        self.assertEqual(centered.rest_mag_limit, -5.)
        self.assertEqual(compute_scene(catalog, centered).n_visible, 0)
        for row in (-1, catalog.n, None):
            with self.assertRaises(ValueError):
                center_object(catalog, state, row)

    def test_widescreen_recomputes_visibility_without_changing_doppler(self):
        catalog = built_in_catalog()
        state = ViewState(beta=.5)
        horizontal, vertical = widescreen_fov(state.vfov_deg)
        self.assertEqual((horizontal, vertical), (80., 45.))
        wide = replace(state, hfov_deg=horizontal, vfov_deg=vertical)
        original, expanded = compute_scene(catalog, state), compute_scene(catalog, wide)
        np.testing.assert_array_equal(original.doppler, expanded.doppler)
        self.assertTrue(np.all(~original.visible | expanded.visible))
        self.assertGreater(expanded.n_visible, original.n_visible)

    def test_widescreen_limits_keep_exact_ratio(self):
        for vertical in (1., 5., 45., 90., 160.):
            h, v = widescreen_fov(vertical)
            self.assertAlmostEqual(h/v, 16/9)
            self.assertTrue(.001 <= v <= 90 and h <= 160)
        with self.assertRaises(ValueError):
            widescreen_fov(float('nan'))
