from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import unittest
import numpy as np
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.geometry import CameraPose
from spaceship_viewer.scene import compute_scene
from spaceship_viewer.state import ViewState


class StateTests(unittest.TestCase):
    def test_unlocked_camera_does_not_steer_ship(self):
        state = ViewState(beta=.87).with_lock(False)
        changed = state.with_camera(state.camera.rotated(30., 12.))
        np.testing.assert_array_equal(state.velocity_direction, changed.velocity_direction)
        a, b = compute_scene(built_in_catalog(), state), compute_scene(built_in_catalog(), changed)
        np.testing.assert_array_equal(a.apparent, b.apparent)
        np.testing.assert_array_equal(a.doppler, b.doppler)
        self.assertFalse(np.array_equal(a.x_deg, b.x_deg))

    def test_locked_camera_steers_ship_and_relock_aligns(self):
        state = ViewState()
        steered = state.with_camera(state.camera.rotated(20., 10.))
        np.testing.assert_allclose(steered.velocity_direction, steered.camera.forward, atol=1e-14)
        unlocked = steered.with_lock(False).with_camera(CameraPose.from_radec(0., 0.))
        relocked = unlocked.with_lock(True)
        np.testing.assert_allclose(relocked.camera.forward, steered.velocity_direction, atol=1e-14)

    def test_heading_change_does_not_move_unlocked_camera(self):
        state = ViewState().with_lock(False)
        changed = state.with_heading(10., 20.)
        self.assertEqual(changed.camera, state.camera)
        self.assertNotEqual(changed.heading_ra_deg, state.heading_ra_deg)

    def test_invalid_state_rejected(self):
        for kwargs in ({'beta': -0.1}, {'beta': 1.}, {'rest_mag_limit': np.nan}, {'hfov_deg': 180.},
                       {'heading_dec_deg': 91.}, {'camera': CameraPose.from_radec(0., 0.)}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ViewState(**kwargs)

    def test_locked_camera_across_pole(self):
        state = ViewState().with_heading(0., 89.)
        for _ in range(40):
            state = state.with_camera(state.camera.rotated(0., .1))
        np.testing.assert_allclose(state.camera.forward, state.velocity_direction, atol=1e-12)

    def test_locked_camera_extremely_close_to_pole(self):
        state = ViewState().with_heading(0., 89.)
        state = state.with_camera(state.camera.rotated(0., .99999))
        np.testing.assert_allclose(state.camera.forward, state.velocity_direction, atol=2e-14)


class SceneTests(unittest.TestCase):
    def test_zero_visible_objects_remains_well_shaped(self):
        state = ViewState(rest_mag_limit=-10.)
        scene = compute_scene(built_in_catalog(), state)
        self.assertEqual(scene.n_visible, 0)
        self.assertEqual(scene.rgb.shape, (0, 3))

    def test_display_toggles_do_not_change_geometry_or_doppler(self):
        a = compute_scene(built_in_catalog(), ViewState(beta=.87))
        b = compute_scene(built_in_catalog(), ViewState(beta=.87, illustrative_brightness=False, doppler_colors=False))
        for field in ('apparent', 'doppler', 'x_deg', 'y_deg', 'visible'):
            np.testing.assert_array_equal(getattr(a, field), getattr(b, field))
        self.assertFalse(np.array_equal(a.rgb, b.rgb))
        self.assertFalse(np.array_equal(a.display_magnitude, b.display_magnitude))

    def test_rest_filter_is_before_boost_and_preserves_order(self):
        state = ViewState(beta=.999, rest_mag_limit=1.)
        cat = built_in_catalog()
        scene = compute_scene(cat, state)
        np.testing.assert_array_equal(scene.candidates.name, cat.name[cat.vmag <= 1.])

    def test_core_and_compatibility_import_do_not_load_gui(self):
        code = "import sys; import spaceship_viewer.scene, relativistic_spaceship_viewer; assert 'tkinter' not in sys.modules; assert 'matplotlib.pyplot' not in sys.modules; assert 'matplotlib' not in sys.modules"
        subprocess.run([sys.executable, '-X', 'utf8', '-c', code], check=True,
                       cwd=Path(__file__).resolve().parents[1])


class BaselineTests(unittest.TestCase):
    def test_original_orion_reference_scenes(self):
        root = Path(__file__).parent / 'reference'
        for label, beta in (('beta_0', 0.), ('beta_0_30', .3), ('beta_0_87', .87), ('gamma_2', np.sqrt(3.)/2)):
            with self.subTest(label=label), np.load(root / f'{label}_original.npz', allow_pickle=False) as old:
                new = compute_scene(built_in_catalog(), ViewState(beta=beta))
                for field in old.files:
                    if field == 'visible':
                        np.testing.assert_array_equal(getattr(new, field), old[field])
                    else:
                        np.testing.assert_allclose(getattr(new, field), old[field], atol=2e-12, rtol=2e-12)


if __name__ == '__main__':
    unittest.main()
