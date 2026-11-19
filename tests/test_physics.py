import math
import unittest
import numpy as np
from spaceship_viewer.geometry import CameraPose, basis_from_radec, project_directions, radec_to_unit, unit_to_radec
from spaceship_viewer.relativity import aberrate, lorentz_factor, rest_frame_half_angle, MAX_BETA


class RelativityTests(unittest.TestCase):
    def setUp(self):
        self.rng = np.random.default_rng(2030)
        self.vectors = self.rng.normal(size=(1000, 3))
        self.vectors /= np.linalg.norm(self.vectors, axis=1)[:, None]
        self.heading = radec_to_unit(217., -43.)[0]

    def test_rest_identity(self):
        apparent, d, mu = aberrate(self.vectors, self.heading, 0.)
        np.testing.assert_allclose(apparent, self.vectors, atol=4e-16, rtol=0)
        np.testing.assert_array_equal(d, np.ones(1000))

    def test_analytic_forward_backward_transverse(self):
        vectors = np.array([[1., 0., 0.], [-1., 0., 0.], [0., 1., 0.]])
        for beta in (0., .3, math.sqrt(3.)/2, .999, MAX_BETA):
            with self.subTest(beta=beta):
                result, d, _ = aberrate(vectors, [1., 0., 0.], beta)
                gamma = lorentz_factor(beta)
                np.testing.assert_allclose(result[:2], vectors[:2], atol=1e-12)
                np.testing.assert_allclose(result[2], [beta, 1/gamma, 0.], atol=2e-12)
                np.testing.assert_allclose(d, [gamma*(1+beta), gamma*(1-beta), gamma], rtol=3e-12)

    def test_independent_photon_four_momentum_boost(self):
        # Photon propagation k=-s, p=(1,k), c=1. Apply an independently
        # constructed 4x4 Lorentz matrix to every photon, then recover -p'/E'.
        for beta in (.3, .87, .999, MAX_BETA):
            with self.subTest(beta=beta):
                gamma = lorentz_factor(beta)
                boost = np.eye(4)
                boost[0, 0] = gamma
                boost[0, 1:] = boost[1:, 0] = -gamma * beta * self.heading
                boost[1:, 1:] += (gamma - 1) * np.outer(self.heading, self.heading)
                photons = np.column_stack((np.ones(len(self.vectors)), -self.vectors))
                shifted = photons @ boost.T
                apparent, d, _ = aberrate(self.vectors, self.heading, beta)
                np.testing.assert_allclose(d, shifted[:, 0], rtol=2e-12, atol=2e-12)
                np.testing.assert_allclose(apparent, -shifted[:, 1:] / shifted[:, :1], atol=2e-11, rtol=2e-11)
                np.testing.assert_allclose(shifted[:, 0]**2 - np.sum(shifted[:, 1:]**2, axis=1), 0., atol=2e-9)

    def test_inverse_boost_and_doppler_reciprocity(self):
        for beta in (.3, .87, .999, MAX_BETA):
            apparent, d, _ = aberrate(self.vectors, self.heading, beta)
            restored, inv_d, _ = aberrate(apparent, self.heading, -beta)
            tolerance = 3e-9 if beta == MAX_BETA else 3e-12
            np.testing.assert_allclose(restored, self.vectors, atol=tolerance, rtol=0)
            np.testing.assert_allclose(d * inv_d, 1., atol=tolerance, rtol=0)

    def test_rotation_covariance(self):
        q, _ = np.linalg.qr(self.rng.normal(size=(3, 3)))
        q[:, 0] *= np.linalg.det(q)
        a, d, _ = aberrate(self.vectors, self.heading, .87)
        b, e, _ = aberrate(self.vectors @ q.T, q @ self.heading, .87)
        np.testing.assert_allclose(b, a @ q.T, atol=3e-15)
        np.testing.assert_allclose(d, e, atol=3e-15)

    def test_half_angle_relation(self):
        theta = np.deg2rad(np.linspace(0, 179.9, 100))
        vectors = np.column_stack((np.cos(theta), np.sin(theta), np.zeros(len(theta))))
        for beta in (.3, .87, .999):
            result, _, _ = aberrate(vectors, [1., 0., 0.], beta)
            theta_prime = np.arctan2(result[:, 1], result[:, 0])
            expected = np.sqrt((1-beta)/(1+beta)) * np.tan(theta / 2)
            np.testing.assert_allclose(np.tan(theta_prime / 2), expected, atol=2e-10, rtol=2e-10)

    def test_cone_inverse(self):
        for beta in (0., .3, .87, .999, MAX_BETA):
            theta = math.radians(rest_frame_half_angle(22.5, beta))
            result, _, _ = aberrate([[math.cos(theta), math.sin(theta), 0.]], [1., 0., 0.], beta)
            np.testing.assert_allclose(math.degrees(math.atan2(result[0, 1], result[0, 0])), 22.5, atol=2e-8)

    def test_solid_angle_jacobian(self):
        # dOmega'/dOmega = dmu'/dmu = 1/D^2, independent finite difference.
        mu, step, beta = .2, 1e-5, .87
        angles = np.array([mu-step, mu, mu+step])
        vectors = np.column_stack((angles, np.sqrt(1-angles**2), np.zeros(3)))
        apparent, d, _ = aberrate(vectors, [1., 0., 0.], beta)
        derivative = (apparent[2, 0]-apparent[0, 0])/(2*step)
        self.assertAlmostEqual(derivative, 1/d[1]**2, places=9)

    def test_behind_can_be_blueshifted(self):
        _, d, _ = aberrate([[-.1, math.sqrt(.99), 0.]], [1., 0., 0.], math.sqrt(3.)/2)
        self.assertGreater(d[0], 1.)

    def test_reject_invalid_inputs_without_clipping(self):
        for beta in (1., -1., MAX_BETA+1e-8, float('nan'), float('inf')):
            with self.subTest(beta=beta), self.assertRaises(ValueError):
                aberrate(self.vectors, self.heading, beta)
        for vector in ([[2., 0., 0.]], [[np.nan, 0., 1.]], [1., 0., 0.]):
            with self.assertRaises(ValueError):
                aberrate(vector, self.heading, .3)
        with self.assertRaises(ValueError):
            aberrate(self.vectors, [0., 0., 0.], .3)

    def test_empty_catalog(self):
        result, d, mu = aberrate(np.empty((0, 3)), self.heading, .999)
        self.assertEqual(result.shape, (0, 3))
        self.assertEqual(d.size, 0)


class GeometryTests(unittest.TestCase):
    def test_round_trip_and_ra_wrap(self):
        for ra, dec in ((0., 0.), (359.999, 12.), (-1., -55.), (84., 89.99999), (19., -90.), (19., 90.)):
            vector = radec_to_unit(ra, dec)[0]
            recovered = radec_to_unit(*unit_to_radec(vector))[0]
            np.testing.assert_allclose(vector, recovered, atol=2e-14, rtol=0)

    def test_camera_is_orthonormal_at_poles(self):
        for dec in (-90., -89.99999, 0., 89.99999, 90.):
            f, e, n = basis_from_radec(81., dec)
            basis = np.array([f, e, n])
            np.testing.assert_allclose(basis @ basis.T, np.eye(3), atol=1e-14)
            np.testing.assert_allclose(np.cross(f, e), n, atol=1e-14)

    def test_continuous_camera_triad_across_pole(self):
        camera = CameraPose.from_radec(0., 89.)
        previous = np.array(camera.forward)
        for _ in range(40):
            camera = camera.rotated(0., .1)
            self.assertGreater(np.dot(previous, camera.forward), .99999)
            previous = np.array(camera.forward)
        np.testing.assert_allclose(camera.forward, radec_to_unit(180., 87.)[0], atol=1e-14)

    def test_projection_orientation_and_back_hemisphere(self):
        camera = CameraPose.from_radec(0., 0.)
        vectors = radec_to_unit([0., 10., -10., 0., 180.], [0., 0., 0., 10., 0.])
        x, y, visible = project_directions(vectors, camera)
        np.testing.assert_allclose(x[:3], [0., -10., 10.], atol=1e-12)
        self.assertAlmostEqual(y[3], 10.)
        np.testing.assert_array_equal(visible, [True, True, True, True, False])

    def test_invalid_coordinates_and_fov(self):
        for ra, dec in ((0., 91.), (float('nan'), 0.), (0., float('inf'))):
            with self.assertRaises(ValueError):
                radec_to_unit(ra, dec)
        for hfov in (0., -5., 180., float('nan')):
            with self.assertRaises(ValueError):
                project_directions([[1., 0., 0.]], CameraPose.from_radec(0., 0.), hfov)


if __name__ == '__main__':
    unittest.main()
