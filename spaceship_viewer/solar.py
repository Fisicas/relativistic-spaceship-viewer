"""Finite solar silhouette at a fixed 1 AU observer event; no orbit or voyage.

IAU nominal radius (2015 B3): 6.957e8 m; AU (2012 B2): 149597870700 m.
The editable direction is a teaching reference in the catalog rest-frame axes,
not an ephemeris. Radiometry settings never enter the geometric transformation.
"""
from dataclasses import dataclass, replace
import math
import numpy as np
from .geometry import CameraPose, finite_scalar, radec_to_unit
from .relativity import aberrate, lorentz_factor

AU_M = 149597870700.
SOLAR_RADIUS_M = 6.957e8
REST_RADIUS_RAD = math.asin(SOLAR_RADIUS_M / AU_M)
LIMB_SAMPLES = 720


@dataclass(frozen=True)
class SolarSettings:
    ra_deg: float = 0.
    dec_deg: float = 0.
    enabled: bool = True
    track_center: bool = True
    observer_distance_m: float = AU_M
    nominal_radius_m: float = SOLAR_RADIUS_M
    model: str = 'fixed-1au-static-photosphere/1'
    radiometry_enabled: bool = True
    exposure_ev: float = 0.
    show_outline: bool = True
    rest_temperature_k: float = 5772.
    radiometry_model: str = 'planck-cie1931-srgb/1'

    def __post_init__(self):
        object.__setattr__(self, 'ra_deg', finite_scalar(self.ra_deg,'solar RA') % 360.)
        object.__setattr__(self, 'dec_deg', finite_scalar(self.dec_deg,'solar Dec'))
        radec_to_unit(self.ra_deg,self.dec_deg)
        if type(self.enabled) is not bool or type(self.track_center) is not bool:
            raise ValueError('Solar visibility/tracking settings must be boolean.')
        if self.observer_distance_m!=AU_M or self.nominal_radius_m!=SOLAR_RADIUS_M or self.model!='fixed-1au-static-photosphere/1':
            raise ValueError('Unsupported solar geometry constants or model version.')
        if type(self.radiometry_enabled) is not bool or type(self.show_outline) is not bool:
            raise ValueError('Solar rendering switches must be boolean.')
        object.__setattr__(self,'exposure_ev',finite_scalar(self.exposure_ev,'solar exposure EV'))
        if not -40.<=self.exposure_ev<=80. or self.rest_temperature_k!=5772. or self.radiometry_model!='planck-cie1931-srgb/1':
            raise ValueError('Unsupported solar radiometry settings or model version.')

    @property
    def direction(self):
        return radec_to_unit(self.ra_deg,self.dec_deg)[0]


def solar_reference(settings):
    from .targets import ReferenceTarget
    from .catalog import CatalogMetadata
    return ReferenceTarget('Sol',settings.ra_deg,settings.dec_deg,None,None,math.pi/648000.,'solar_disk',
        CatalogMetadata(source='Analytic Sol model: IAU nominal radius, fixed 1 AU observer event',
            coordinate_frame='User-defined direction in the catalog rest-frame equatorial axes',
            coordinate_epoch='Fixed teaching setup; no ephemeris or proper motion',
            magnitude_system='Ideal 5772 K blackbody radiance; no measured solar V magnitude',
            notes=('Nominal solar radius 695700000 m; observer distance 149597870700 m (1 AU).',
                   'RA/Dec default to 0/0 degrees and are editable independently of velocity.',
                   'Uniform ideal blackbody; per-ray Doppler spectrum; no limb darkening or solar absorption lines.',
                   'CIE 1931 2-degree observer (CIE 2019), DOI 10.25039/CIE.DS.xvudnb9b; CC BY-SA 4.0.')))


def rest_limb(settings, samples=LIMB_SAMPLES):
    if type(samples) is not int or samples<16:
        raise ValueError('At least 16 limb samples are required.')
    camera=CameraPose.from_radec(settings.ra_deg,settings.dec_deg)
    phi=np.linspace(0.,2*math.pi,samples,endpoint=False)
    return (math.cos(REST_RADIUS_RAD)*np.asarray(camera.forward)[None,:]
            +math.sin(REST_RADIUS_RAD)*(np.cos(phi)[:,None]*camera.east+np.sin(phi)[:,None]*camera.north))


def solar_geometry(settings,state):
    """Exact aberrated spherical-cap center/radius plus sampled limb rays.

    For c.s >= cos(alpha), inverse aberration gives A.s' >= k,
    A=c_perp/gamma+(c.h+beta*cos(alpha))*h; k=cos(alpha)+beta*c.h.
    Radius is atan2(sin(alpha)/gamma,k), including caps larger than a hemisphere.
    The aberrated central ray and apparent limb-circle center need not coincide.
    """
    c=settings.direction
    h=state.velocity_direction
    beta=state.beta
    gamma=lorentz_factor(beta)
    mu=float(np.clip(c@h,-1.,1.))
    ca,sa=math.cos(REST_RADIUS_RAD),math.sin(REST_RADIUS_RAD)
    vector=(c-mu*h)/gamma+(mu+beta*ca)*h
    cap_center=vector/np.linalg.norm(vector)
    radius=math.atan2(sa/gamma,ca+beta*mu)
    central,d,_=aberrate(c[None,:],h,beta)
    limb=rest_limb(settings)
    apparent,limb_d,_=aberrate(limb,h,beta)
    theta=math.acos(mu)
    mu_max=1. if theta<=REST_RADIUS_RAD else math.cos(theta-REST_RADIUS_RAD)
    mu_min=-1. if math.pi-theta<=REST_RADIUS_RAD else math.cos(theta+REST_RADIUS_RAD)
    omega=4*math.pi*math.sin(radius/2)**2
    rest_omega=4*math.pi*math.sin(REST_RADIUS_RAD/2)**2
    return {'rest_center':c,'rest_radius_rad':REST_RADIUS_RAD,'rest_limb':limb,
            'central_ray':central[0],'central_doppler':float(d[0]),'cap_center':cap_center,
            'radius_rad':radius,'solid_angle_sr':omega,'rest_solid_angle_sr':rest_omega,
            'solid_angle_ratio':omega/rest_omega,'limb':apparent,'limb_doppler':limb_d,
            'doppler_min':gamma*(1+beta*mu_min),'doppler_max':gamma*(1+beta*mu_max)}


def occulted_by_sol(vectors,settings):
    """Distant-background ray membership; invariant under a common boost."""
    return np.asarray(vectors)@settings.direction >= math.cos(REST_RADIUS_RAD)


def compute_view(catalog,state,presentation):
    """Extend the unchanged stellar core with explicit solar ray occultation."""
    from .scene import compute_scene
    scene=compute_scene(catalog,state)
    settings=presentation.solar
    occulted=np.zeros(scene.candidates.n,dtype=bool)
    if settings is None or not settings.enabled:
        return scene,None,occulted
    geometry=solar_geometry(settings,state)
    occulted=occulted_by_sol(scene.candidates.vectors,settings)
    draw=~occulted[scene.visible]
    scene=replace(scene,visible=scene.visible & ~occulted,
                  display_magnitude=scene.display_magnitude[draw],
                  marker_area_pt2=scene.marker_area_pt2[draw],rgb=scene.rgb[draw])
    return scene,geometry,occulted
