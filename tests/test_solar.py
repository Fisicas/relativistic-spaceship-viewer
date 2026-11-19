from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest
import numpy as np
from spaceship_viewer.catalog import StarCatalog
from spaceship_viewer.geometry import CameraPose
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.solar import (SolarSettings,solar_geometry,solar_reference,compute_view,
                                    REST_RADIUS_RAD,AU_M,SOLAR_RADIUS_M)
from spaceship_viewer.state import ViewState
from spaceship_viewer.session import make_document,decode_document
from spaceship_viewer.relativity import aberrate


def state(beta,heading=0.):
    return ViewState(beta=beta,heading_ra_deg=heading,heading_dec_deg=0.,camera=CameraPose.from_radec(heading,0.))


class SolarTests(unittest.TestCase):
    def test_nominal_rest_diameter_and_constants(self):
        self.assertEqual(AU_M,149597870700.)
        self.assertEqual(SOLAR_RADIUS_M,695700000.)
        self.assertAlmostEqual(math.degrees(2*REST_RADIUS_RAD),.5329062144923112,places=12)
        g=solar_geometry(SolarSettings(),state(0.))
        self.assertAlmostEqual(g['radius_rad'],REST_RADIUS_RAD,places=14)
        self.assertAlmostEqual(g['solid_angle_ratio'],1.,places=12)
        self.assertEqual(g['central_doppler'],1.)

    def test_axial_radii_against_independent_half_angle_formula(self):
        for beta in (.3,.9,.999999):
            factor=math.sqrt((1-beta)/(1+beta))
            toward=solar_geometry(SolarSettings(),state(beta,0.))
            away=solar_geometry(SolarSettings(),state(beta,180.))
            self.assertAlmostEqual(toward['radius_rad'],2*math.atan(factor*math.tan(REST_RADIUS_RAD/2)),delta=2e-12)
            self.assertAlmostEqual(away['radius_rad'],2*math.atan(math.tan(REST_RADIUS_RAD/2)/factor),delta=3e-11)
            self.assertLess(toward['radius_rad'],REST_RADIUS_RAD)
            self.assertGreater(away['radius_rad'],REST_RADIUS_RAD)
        self.assertGreater(away['radius_rad'],math.pi/2)

    def test_every_transformed_limb_ray_lies_on_analytic_circle(self):
        for settings in (SolarSettings(),SolarSettings(137.,78.),SolarSettings(0.,90.)):
            for beta in (0.,.9,.999999):
                for heading in (0.,75.,179.8,180.):
                    g=solar_geometry(settings,state(beta,heading))
                    angle=np.arctan2(np.linalg.norm(np.cross(g['limb'],g['cap_center']),axis=1),g['limb']@g['cap_center'])
                    np.testing.assert_allclose(angle,g['radius_rad'],atol=3e-9,rtol=0.)
                    self.assertTrue(np.all(g['limb_doppler']>=g['doppler_min']-2e-10))
                    self.assertTrue(np.all(g['limb_doppler']<=g['doppler_max']+2e-10))

    def test_solid_angle_against_independent_jacobian_quadrature(self):
        # dOmega' = dOmega / D^2; integrate uniformly in rest-frame mu.
        nodes,weights=np.polynomial.legendre.leggauss(80)
        ca=math.cos(REST_RADIUS_RAD)
        mu=(1+ca)/2+nodes*(1-ca)/2
        phi=np.linspace(0,2*math.pi,128,endpoint=False)
        rr=np.sqrt((1-mu)*(1+mu))
        rays=np.stack(np.broadcast_arrays(mu[:,None],rr[:,None]*np.cos(phi),rr[:,None]*np.sin(phi)),axis=-1).reshape(-1,3)
        for beta,heading in ((.9,75.),(.999999,180.)):
            s=state(beta,heading)
            _,d,_=aberrate(rays,s.velocity_direction,beta)
            area=(1-ca)/2*2*math.pi*np.sum(weights*np.mean(1/d.reshape(80,128)**2,axis=1))
            expected=solar_geometry(SolarSettings(),s)['solid_angle_sr']
            self.assertAlmostEqual(area/expected,1.,delta=2e-7)

    def test_occultation_alignment_and_boost_invariance(self):
        catalog=StarCatalog(['Behind Sun','Outside'],[0.,2.],[0.,0.],[1.,1.],[.5,.5],[10.,10.])
        presentation=Presentation(solar=SolarSettings())
        for beta in (0.,.9,.999999):
            scene,_,occulted=compute_view(catalog,state(beta),presentation)
            np.testing.assert_array_equal(occulted,[True,False])
            self.assertFalse(scene.visible[0])
            self.assertEqual(len(scene.rgb),scene.n_visible)
            self.assertEqual(len(scene.marker_area_pt2),scene.n_visible)
        unblocked,_,_=compute_view(catalog,state(0.),replace(presentation,solar=SolarSettings(enabled=False)))
        self.assertEqual(unblocked.n_visible,2)

    def test_solar_settings_and_target_round_trip(self):
        settings=SolarSettings(ra_deg=117.,dec_deg=-20.)
        p=Presentation(solar=settings,reference_target=solar_reference(settings))
        catalog=StarCatalog(['Synthetic'],[10.],[20.],[1.],[np.nan],[np.nan])
        document=json.loads(json.dumps(make_document(catalog,ViewState(),p),allow_nan=False))
        _,_,restored,_=decode_document(document)
        self.assertEqual(restored,p)
        self.assertIsNone(restored.reference_target.vmag)
        self.assertEqual(restored.solar.observer_distance_m,AU_M)
        with self.assertRaises(ValueError):
            SolarSettings(nominal_radius_m=1.)
        with self.assertRaises(ValueError):
            SolarSettings(dec_deg=91.)

    def test_export_keeps_input_rows_and_records_positive_occultation(self):
        from spaceship_viewer.exporting import export_scene
        from spaceship_viewer.session import load_document
        from tools.verify_export import verify
        catalog=StarCatalog(['Behind Sun','Outside'],[0.,1.],[0.,0.],[1.,1.],[.5,.5],[10.,10.])
        settings=SolarSettings()
        p=Presentation(solar=settings,reference_target=solar_reference(settings))
        view=replace(state(0.),hfov_deg=4.,vfov_deg=4.)
        parent=Path(__file__).resolve().parents[1]/'.test-tmp'
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            assert Path(directory).resolve().is_relative_to(parent.resolve())
            folder=export_scene(directory,'occultation',catalog,view,p,'Synthetic solar fixture',
                                width=800,height=600,dpi=100,formats=('png',))
            with np.load(folder/'scene_data.npz',allow_pickle=False) as arrays:
                np.testing.assert_array_equal(arrays['moving_solar_occulted'],[True,False])
                np.testing.assert_array_equal(arrays['moving_visible_catalog_rows'],[1])
            reopened,_,_,_=load_document(folder/'scene.json')
            self.assertEqual(reopened.name.tolist(),['Behind Sun','Outside'])
            self.assertEqual(verify(folder/'scene.json')['status'],'passed')
