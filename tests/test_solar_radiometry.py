from dataclasses import replace
import math
import unittest
import numpy as np
from spaceship_viewer.solar import SolarSettings,solar_geometry,solar_reference,compute_view
from spaceship_viewer.solar_radiometry import (planck_lambda,xyz_direct,xyz_interpolated,display_rgb,
    fitted_exposure,rest_y,solar_image,summary,TEMPERATURE_K,SIGMA,cie_table,RGB_Y)
from spaceship_viewer.geometry import CameraPose
from spaceship_viewer.state import ViewState
from spaceship_viewer.relativity import aberrate
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.session import make_document,decode_document


class SolarRadiometryTests(unittest.TestCase):
    def test_planck_doppler_identity_no_double_counting(self):
        wavelengths=np.geomspace(1e-8,1e-3,120)
        for d in (.22941573387056174,1.,4.358898943540674):
            np.testing.assert_allclose(planck_lambda(wavelengths,d*TEMPERATURE_K),
                d**5*planck_lambda(d*wavelengths,TEMPERATURE_K),rtol=3e-13,atol=1e-280)

    def test_bolometric_integral_and_fourth_power(self):
        wavelength=np.geomspace(1e-10,1.,60000)
        def integral(temperature):
            y=planck_lambda(wavelength,temperature)
            return np.sum((y[1:]+y[:-1])*.5*np.diff(wavelength))
        rest=integral(TEMPERATURE_K)
        self.assertAlmostEqual(rest/(SIGMA/math.pi*TEMPERATURE_K**4),1.,delta=3e-8)
        for d in (.23,4.36):
            shifted=integral(TEMPERATURE_K*d)
            self.assertAlmostEqual(shifted/rest/d**4,1.,delta=3e-8)

    def test_official_cie_and_lut_accuracy(self):
        self.assertEqual(cie_table().shape,(471,4)) # loading validates official SHA
        d=np.geomspace(.08,1414.,301)
        direct=xyz_direct(d)
        approximate=xyz_interpolated(d)
        meaningful=direct[:,1]/rest_y()>1e-12
        error=np.max(np.abs(approximate[meaningful]-direct[meaningful])/np.maximum(direct[meaningful],rest_y()*1e-12))
        self.assertLess(error,.001)

    def test_fixed_exposure_retains_dimming_and_explicit_fit(self):
        d=np.array([.22941573387056174,1.,4.358898943540674])
        xyz=xyz_direct(d)
        rgb=display_rgb(xyz)
        def linear(v):
            return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
        luminance=linear(rgb)@RGB_Y
        self.assertTrue(np.all(np.diff(luminance)>0))
        self.assertLess(luminance[0],.001*luminance[1])
        self.assertGreater(luminance[2],luminance[1])
        fitted=display_rgb(xyz[0],fitted_exposure(d[0]))
        self.assertAlmostEqual(float(linear(fitted)@RGB_Y),.3,places=10)
        np.testing.assert_array_equal(display_rgb(xyz_direct(.0008)),[0.,0.,0.])
        self.assertFalse(np.allclose(xyz[:,1]/rest_y(),d**4))

    def test_exposure_and_render_switch_never_change_geometry_or_occultation(self):
        settings=SolarSettings(ra_deg=25.,dec_deg=-30.)
        state=ViewState(beta=.9999,heading_ra_deg=195.,heading_dec_deg=20.,camera_locked=False)
        baseline=solar_geometry(settings,state)
        p=Presentation(solar=settings)
        scene,_,mask=compute_view(built_in_catalog(),state,p)
        for s in (replace(settings,exposure_ev=38.),replace(settings,radiometry_enabled=False,show_outline=False)):
            g=solar_geometry(s,state)
            for key in baseline:
                np.testing.assert_array_equal(g[key],baseline[key])
            changed,_,new_mask=compute_view(built_in_catalog(),state,replace(p,solar=s))
            np.testing.assert_array_equal(mask,new_mask)
            np.testing.assert_array_equal(scene.visible,changed.visible)

    def test_per_ray_inverse_doppler_and_surface_gradient(self):
        settings=SolarSettings()
        s=ViewState(beta=.999999,heading_ra_deg=179.7,heading_dec_deg=0.,camera_locked=False,
                    camera=CameraPose.from_radec(90.,0.),hfov_deg=120.,vfov_deg=120.)
        geometry=solar_geometry(settings,s)
        image=solar_image(s,geometry,settings)
        gx,gy=np.meshgrid(image['x_deg'],image['y_deg'])
        ray=(s.camera.forward-np.tan(np.deg2rad(gx))[...,None]*s.camera.east+np.tan(np.deg2rad(gy))[...,None]*s.camera.north)
        ray/=np.linalg.norm(ray,axis=-1)[...,None]
        rest,_,_=aberrate(ray.reshape(-1,3),s.velocity_direction,-s.beta)
        _,d,_=aberrate(rest,s.velocity_direction,s.beta)
        np.testing.assert_allclose(image['doppler'].reshape(-1),d,rtol=2e-9)
        inside=image['inside']
        self.assertTrue(inside.any())
        self.assertGreater(image['doppler'][inside].max()/image['doppler'][inside].min(),2.)

    def test_legacy_scene_preserves_neutral_fill_and_reference_provenance(self):
        settings=SolarSettings()
        p=Presentation(solar=settings,reference_target=solar_reference(settings))
        document=make_document(built_in_catalog(),ViewState(),p)
        for key in ('radiometry_enabled','exposure_ev','show_outline','rest_temperature_k','radiometry_model'):
            document['presentation']['solar'].pop(key)
        document['presentation']['reference_target']['metadata']['magnitude_system']='Solar photometry is not modeled'
        _,_,restored,_=decode_document(document)
        self.assertFalse(restored.solar.radiometry_enabled)
        self.assertEqual(restored.reference_target.metadata.magnitude_system,'Solar photometry is not modeled')

    def test_validation_and_opaque_black_domain(self):
        for kw in ({'exposure_ev':float('nan')},{'exposure_ev':81.},{'rest_temperature_k':5000.},{'radiometry_enabled':1}):
            with self.assertRaises(ValueError):
                SolarSettings(**kw)
        settings=SolarSettings()
        s=ViewState(beta=.999999,heading_ra_deg=180.,heading_dec_deg=0.,camera_locked=False,
                    camera=CameraPose.from_radec(0.,0.),hfov_deg=120.,vfov_deg=120.)
        g=solar_geometry(settings,s)
        image=solar_image(s,g,settings)
        self.assertTrue(image['inside'].all())
        self.assertEqual(image['rgb'].shape[-1],3) # RGB, no transparent dimming
        self.assertLess(summary(g,settings)['central_visible_y_ratio'],1e-250)
