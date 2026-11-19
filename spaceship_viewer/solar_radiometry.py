"""Uniform 5772 K blackbody surface radiance, separate from solar geometry.

I_nu/nu^3 is invariant, hence B_nu(T)' = B_nu(D*T). Integrating that
spectrum already accounts for beaming; applying another D^4 would double count.
XYZ uses unmodified CIE 1931 2-degree data (CIE 2019, CC BY-SA 4.0),
DOI 10.25039/CIE.DS.xvudnb9b. See data/CIE_ATTRIBUTION.txt.
"""
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import numpy as np
from .relativity import MAX_BETA, lorentz_factor
from .geometry import project_directions

TEMPERATURE_K = 5772.
MODEL = 'planck-cie1931-srgb/1'
MIN_EV, MAX_EV = -40., 80.
CIE_SHA256 = 'fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1'
H, C, K = 6.62607015e-34, 299792458., 1.380649e-23
SIGMA = 2*math.pi**5*K**4/(15*H**3*C**2)
XYZ_TO_RGB = np.array([[3.2406255,-1.537208,-.4986286],
                       [-.9689307,1.8757561,.0415175],
                       [.0557101,-.2040211,1.0569959]])
RGB_Y = np.linalg.inv(XYZ_TO_RGB)[1]


@lru_cache(maxsize=1)
def cie_table():
    raw=(Path(__file__).parent/'data/CIE_xyz_1931_2deg.csv').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CIE_SHA256:
        raise ValueError('CIE observer data checksum mismatch.')
    from io import BytesIO
    data=np.loadtxt(BytesIO(raw),delimiter=',')
    if data.shape!=(471,4) or not np.array_equal(data[:,0],np.arange(360,831)):
        raise ValueError('Unexpected CIE wavelength sampling.')
    data.setflags(write=False)
    return data


def planck_lambda(wavelength_m, temperature_k):
    """Spectral surface radiance in W m^-2 sr^-1 m^-1; no limb darkening."""
    wavelength=np.asarray(wavelength_m,dtype=float)
    temperature=np.asarray(temperature_k,dtype=float)
    if np.any(~np.isfinite(temperature)) or np.any(temperature<=0) or np.any(~np.isfinite(wavelength)) or np.any(wavelength<=0):
        raise ValueError('Planck wavelengths and temperatures must be finite and positive.')
    x=H*C/(wavelength*K*temperature)
    with np.errstate(under='ignore'):
        reciprocal=np.exp(-x)/(-np.expm1(-x))
    return (2*H*C*C/wavelength**5)*reciprocal


def xyz_direct(doppler):
    """CIE XYZ radiance integrals, W m^-2 sr^-1 (Y times 683 is cd/m^2).

    Trapezoidal quadrature at the original 1 nm nodes, zero outside 360..830
    nm. No spectrum resampling or extra Doppler amplitude is applied.
    """
    d=np.asarray(doppler,dtype=float)
    if np.any(~np.isfinite(d)) or np.any(d<=0):
        raise ValueError('Doppler factors must be finite and positive.')
    table=cie_table()
    weights=np.ones(471)*1e-9
    weights[[0,-1]]*=.5
    weighted=table[:,1:]*weights[:,None]
    result=np.empty((d.size,3))
    flat=d.reshape(-1)
    for start in range(0,len(flat),512):
        radiance=planck_lambda(table[:,0][None,:]*1e-9,TEMPERATURE_K*flat[start:start+512,None])
        result[start:start+512]=radiance@weighted
    return result.reshape(d.shape+(3,))


@lru_cache(maxsize=1)
def xyz_lut():
    limit=math.atanh(MAX_BETA)
    log_d=np.linspace(-limit,limit,8193)
    xyz=xyz_direct(np.exp(log_d))
    log_d.setflags(write=False)
    xyz.setflags(write=False)
    return log_d,xyz


def xyz_interpolated(doppler):
    """Linear XYZ interpolation in log(D); 8193 nodes over supported beta."""
    d=np.asarray(doppler,dtype=float)
    grid,values=xyz_lut()
    if np.any(~np.isfinite(d)) or np.any(d<=0):
        raise ValueError('Doppler factors must be finite and positive.')
    log=np.log(d)
    if np.any(log<grid[0]-1e-8) or np.any(log>grid[-1]+1e-8):
        raise ValueError('Doppler factor outside the tested renderer domain.')
    return np.stack([np.interp(log,grid,values[:,i]) for i in range(3)],axis=-1)


@lru_cache(maxsize=1)
def rest_y():
    return float(xyz_direct(1.)[1])


def display_rgb(xyz,exposure_ev=0.):
    """Fixed-exposure Reinhard luminance map and D65 sRGB, not photometry.

    Negative RGB is clipped, then Y is restored. Above-gamut colors are mixed
    with a neutral gray at fixed mapped Y. This makes extreme brightness tend
    toward white without normalizing away physical dimming. Zero visible
    radiance stays opaque black. Exposure never enters geometry or radiance.
    """
    if not math.isfinite(exposure_ev) or not MIN_EV<=exposure_ev<=MAX_EV:
        raise ValueError('Solar exposure is outside the supported EV range.')
    xyz=np.asarray(xyz,dtype=float)/rest_y()
    y=xyz[...,1]
    linear=np.maximum(xyz@XYZ_TO_RGB.T,0.)
    actual_y=linear@RGB_Y
    linear*=np.divide(y,actual_y,out=np.zeros_like(y),where=actual_y>0)[...,None]
    exposed=.5*2.**exposure_ev*y
    mapped=exposed/(1+exposed)
    linear*=np.divide(mapped,y,out=np.zeros_like(y),where=y>0)[...,None]
    peak=linear.max(axis=-1)
    gray=mapped/np.sum(RGB_Y)
    mix=np.minimum(1.,np.divide(1-gray,peak-gray,out=np.ones_like(y),where=peak>1.))
    linear=gray[...,None]+mix[...,None]*(linear-gray[...,None])
    linear=np.clip(linear,0.,1.)
    return np.where(linear<=.0031308,12.92*linear,1.055*linear**(1/2.4)-.055)


def fitted_exposure(doppler_max):
    """Manual one-shot fit: map the disk's brightest model ray to Y=.3."""
    ratio=float(xyz_direct(doppler_max)[1])/rest_y()
    if ratio==0:
        return MAX_EV
    return float(np.clip(math.log2((.3/.7)/(.5*ratio)),MIN_EV,MAX_EV))


def summary(geometry,settings):
    d=geometry['central_doppler']
    xyz=xyz_direct(d)
    return {'model':MODEL,'temperature_k':TEMPERATURE_K,'shifted_temperature_k':d*TEMPERATURE_K,
            'central_bolometric_radiance_w_m2_sr':SIGMA/math.pi*(d*TEMPERATURE_K)**4,
            'central_bolometric_radiance_ratio':d**4,
            'central_luminance_cd_m2':float(xyz[1])*683.,
            'central_visible_y_ratio':float(xyz[1])/rest_y(),
            'exposure_ev':settings.exposure_ev,'enabled':settings.radiometry_enabled,
            'cie_sha256':CIE_SHA256,'cie_doi':'10.25039/CIE.DS.xvudnb9b',
            'data_license':'CC BY-SA 4.0','radiance_scope':'surface radiance per ray, not disk-integrated flux',
            'display':'fixed exposure; Reinhard Y; D65 sRGB; negative-channel clipping and Y-preserving gamut compression',
            'processing':'CIE 360..830 nm, 1 nm trapezoids; XYZ interpolation in log(D), 8193 nodes; no limb darkening'}


def solar_image(state,geometry,settings):
    """Deterministic angular raster; cap membership is independent of color.

    Small front-facing disks use a 257-square texture clipped by the original
    720-ray limb polygon. Horizon/large caps retain the 401-square angular mask.
    Arrays outside `inside` are computational padding, not solar measurements.
    """
    limb=geometry['limb']
    front=bool(np.all(limb@state.camera.forward>0) and geometry['radius_rad']<np.pi/2)
    x,y,_=project_directions(limb,state.camera,state.hfov_deg,state.vfov_deg)
    left,right=-state.hfov_deg/2,state.hfov_deg/2
    bottom,top=-state.vfov_deg/2,state.vfov_deg/2
    if front:
        left,right=max(left,float(x.min())),min(right,float(x.max()))
        bottom,top=max(bottom,float(y.min())),min(top,float(y.max()))
    if left>=right or bottom>=top:
        return None
    n=257 if front else 401
    gx,gy=np.linspace(left,right,n),np.linspace(bottom,top,n)
    xx,yy=np.meshgrid(np.tan(np.deg2rad(gx)),np.tan(np.deg2rad(gy)))
    rays=(state.camera.forward-xx[...,None]*state.camera.east+yy[...,None]*state.camera.north)
    rays/=np.sqrt(1+xx*xx+yy*yy)[...,None]
    score=rays@geometry['cap_center']
    inside=score>=math.cos(geometry['radius_rad'])
    d=1/(lorentz_factor(state.beta)*(1-state.beta*np.clip(rays@state.velocity_direction,-1.,1.)))
    xyz=xyz_interpolated(d)
    return {'x_deg':gx,'y_deg':gy,'inside':inside,'doppler':d,'xyz_w_m2_sr':xyz,
            'rgb':display_rgb(xyz,settings.exposure_ev),'front_polygon':front}
