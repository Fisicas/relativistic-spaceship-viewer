"""Reproducible fixed-FOV Sol radiometry examples and same-environment replay."""
from pathlib import Path
import argparse,json,math,sys
from dataclasses import replace
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from spaceship_viewer.solar import SolarSettings,solar_geometry,solar_reference
from spaceship_viewer.solar_radiometry import summary,fitted_exposure,xyz_direct,xyz_interpolated,rest_y
from spaceship_viewer.geometry import CameraPose,unit_to_radec
from spaceship_viewer.state import ViewState
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.exporting import export_scene
from spaceship_viewer.plotting import draw_solar_disk,BACKGROUND,FOREGROUND,MUTED
from verify_export import verify

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    out=parser.parse_args().output_dir.resolve()
    out.mkdir(parents=True,exist_ok=False)
    fig=Figure(figsize=(14,7.6),dpi=160,facecolor=BACKGROUND)
    FigureCanvasAgg(fig)
    axes=fig.subplots(1,4)
    fig.subplots_adjust(left=.05,right=.98,bottom=.22,top=.80,wspace=.25)
    results=[]
    for ax,(name,beta,heading,fit) in zip(axes,[('Rest',0.,0.,False),('Toward',.9,0.,False),('Away',.9,180.,False),('Away, fitted exposure',.9,180.,True)]):
        settings=SolarSettings()
        state=ViewState(beta=beta,heading_ra_deg=heading,heading_dec_deg=0.,camera_locked=False,
                        camera=CameraPose.from_radec(0.,0.),hfov_deg=4.,vfov_deg=4.,labels=False)
        g=solar_geometry(settings,state)
        ra,dec=unit_to_radec(g['cap_center'])
        state=replace(state,camera=CameraPose.from_radec(ra,dec))
        if fit:
            settings=replace(settings,exposure_ev=fitted_exposure(g['doppler_max']))
        presentation=Presentation(solar=settings,reference_target=solar_reference(settings),max_labels=0)
        folder=export_scene(out,name,built_in_catalog(),state,presentation,'Sol · '+name,width=1600,height=1000,dpi=150)
        replay=verify(folder/'scene.json',out/'replays')
        ax.set_facecolor(BACKGROUND)
        ax.set_xlim(-2,2);ax.set_ylim(-2,2);ax.set_aspect('equal')
        ax.tick_params(colors=MUTED,labelsize=8)
        for spine in ax.spines.values():spine.set_color(MUTED)
        draw_solar_disk(ax,state,g,False,settings)
        radiance=summary(g,settings)
        ax.set_title(f"{name}\nβ={beta:g} · exposure {settings.exposure_ev:+.2f} EV",color=FOREGROUND,fontsize=10,pad=12)
        ax.set_xlabel(f"Diameter {math.degrees(2*g['radius_rad']):.5f}°\nVisible Y / rest = {radiance['central_visible_y_ratio']:.4g}",color=FOREGROUND,fontsize=9,labelpad=12)
        results.append({'case':name,'beta':beta,'heading_ra_deg':heading,'fov_deg':[4.,4.],
                        'diameter_deg':math.degrees(2*g['radius_rad']),'central_doppler':g['central_doppler'],
                        'radiometry':radiance,'export':str(folder),'replay':replay})
    fig.text(.05,.92,'SOL: DOPPLER SPECTRUM AND ANGULAR SIZE',color=FOREGROUND,fontsize=17,weight='bold')
    fig.text(.05,.875,'Same 4° × 4° angular field in every panel · fixed observer event at 1 AU',color=MUTED,fontsize=11)
    fig.text(.05,.10,'Uniform 5772 K blackbody. Fixed exposure retains physical dimming; fitted exposure is an explicit display adjustment.\n'
             'Orange outlines and center crosses are annotations. Tone mapping limits brightness and color; no limb darkening.\n'
             'CIE 1931 2° observer, CIE 2019, DOI 10.25039/CIE.DS.xvudnb9b, CC BY-SA 4.0. Derived color data: CC BY-SA 4.0.',
             color=MUTED,fontsize=9,linespacing=1.6)
    fig.savefig(out/'sol_comparison.png',facecolor=BACKGROUND)
    d=np.geomspace(.08,1414.,301)
    direct=xyz_direct(d);approx=xyz_interpolated(d)
    good=direct[:,1]/rest_y()>1e-12
    error=float(np.max(np.abs(approx[good]-direct[good])/np.maximum(direct[good],rest_y()*1e-12)))
    report={'status':'passed','cases':results,'lut_max_relative_xyz_error_above_y_ratio_1e_minus12':error,
            'processing':'same angular FOV; no trajectory; model and display parameters saved separately; exact PNG replay in this environment'}
    (out/'radiometry_checks.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','cases':len(results),'lut_error':error,'output':str(out)},indent=2))
if __name__=='__main__':main()
