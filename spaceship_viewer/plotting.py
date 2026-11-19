"""Dark, annotated scientific views shared by the Qt viewport and exports.

The baseline renderer remains in rendering.py. This module only changes
presentation; compute_scene remains the validated numerical source of truth.
"""
from dataclasses import replace
import numpy as np
from matplotlib.transforms import Bbox
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Polygon
from .scene import compute_scene
from .relativity import lorentz_factor
from .relativity import aberrate
from .geometry import project_directions
from .solar import compute_view

BACKGROUND = '#080e19'
FOREGROUND = '#d7e3f1'
MUTED = '#7e93ad'
ACCENT = '#6dd8ed'


def draw_solar_disk(ax,state,geometry,labels):
    """Neutral silhouette: exact sampled limb, implicit-cap fallback at horizon.

    The fallback samples the displayed angular map on a 401×401 grid when the
    boundary crosses the camera horizon or the disk exceeds a hemisphere.
    """
    limb=geometry['limb']
    x,y,_=project_directions(limb,state.camera,state.hfov_deg,state.vfov_deg)
    if np.all(limb@state.camera.forward>0) and geometry['radius_rad']<np.pi/2:
        ax.add_patch(Polygon(np.column_stack((x,y)),closed=True,facecolor='#fff1c9',
                             edgecolor='#f4bd60',linewidth=.9,zorder=4))
    else:
        gx=np.linspace(-state.hfov_deg/2,state.hfov_deg/2,401)
        gy=np.linspace(-state.vfov_deg/2,state.vfov_deg/2,401)
        xx,yy=np.meshgrid(np.tan(np.deg2rad(gx)),np.tan(np.deg2rad(gy)))
        center=geometry['cap_center']
        score=(center@state.camera.forward-xx*(center@state.camera.east)+yy*(center@state.camera.north))/np.sqrt(1+xx*xx+yy*yy)
        inside=score>=np.cos(geometry['radius_rad'])
        if inside.all():
            ax.axhspan(-state.vfov_deg/2,state.vfov_deg/2,color='#fff1c9',zorder=4)
        elif inside.any():
            ax.contourf(gx,gy,inside.astype(float),levels=[.5,1.5],colors=['#fff1c9'],zorder=4)
            ax.contour(gx,gy,score,levels=[np.cos(geometry['radius_rad'])],colors=['#f4bd60'],linewidths=.9,zorder=4)
    cx,cy,visible=project_directions(geometry['central_ray'][None,:],state.camera,state.hfov_deg,state.vfov_deg)
    if visible[0]:
        ax.plot(cx,cy,marker='+',markersize=8,color='#bf8733',linestyle='none',zorder=6)
        if labels:
            ax.annotate('Sol · 1 AU model',(cx[0],cy[0]),xytext=(10,10),textcoords='offset points',
                        color=ACCENT,fontsize=8,zorder=6,annotation_clip=True,
                        bbox={'facecolor':BACKGROUND,'edgecolor':'none','alpha':.85,'pad':2})


def draw_view(ax, scene, state, presentation, original_rows, selected=None, solar=None):
    ax.set_facecolor(BACKGROUND)
    for spine in ax.spines.values():
        spine.set_color('#243247')
    ax.tick_params(colors=MUTED, labelsize=8, length=3)
    ax.set_xlim(-state.hfov_deg / 2, state.hfov_deg / 2)
    ax.set_ylim(-state.vfov_deg / 2, state.vfov_deg / 2)
    ax.set_aspect('equal', adjustable='box')
    ax.set_axisbelow(True)
    if presentation.grid:
        ax.grid(color='#263447', linewidth=.55, alpha=.6)
    ax.set_xlabel('Horizontal angle (°)  ·  right = camera west', color=MUTED, fontsize=8, labelpad=9)
    ax.set_ylabel('Vertical angle (°)', color=MUTED, fontsize=8, labelpad=8)
    ax.axhline(0, color='#39506b', lw=.6, alpha=.5)
    ax.axvline(0, color='#39506b', lw=.6, alpha=.5)
    x, y = scene.x_deg[scene.visible], scene.y_deg[scene.visible]
    areas = scene.marker_area_pt2 * presentation.marker_scale
    if state.glow:
        ax.scatter(x, y, s=np.clip(areas * 4.5, 2, 900), c=scene.rgb, alpha=.08, linewidths=0, zorder=2)
        ax.scatter(x, y, s=np.clip(areas * 2., 1, 500), c=scene.rgb, alpha=.13, linewidths=0, zorder=2)
    points = ax.scatter(x, y, s=areas, c=scene.rgb, alpha=.97, linewidths=0, zorder=3)
    if solar is not None:
        draw_solar_disk(ax,state,solar,state.labels)
    if presentation.reference_target is not None and presentation.reference_target.object_kind!='solar_disk':
        target = presentation.reference_target
        apparent, _, _ = aberrate(target.as_catalog().vectors, state.velocity_direction, state.beta)
        tx, ty, inside = project_directions(apparent, state.camera, state.hfov_deg, state.vfov_deg)
        if inside[0]:
            # Navigation annotation, not another measured source or detection.
            ax.plot(tx, ty, marker='+', markersize=14, color=ACCENT, linestyle='none', zorder=6)
            if state.labels:
                ax.annotate(target.name+' · reference', (tx[0], ty[0]), xytext=(9, 10),
                            textcoords='offset points', color=ACCENT, fontsize=8, annotation_clip=True, zorder=6)
    hit = np.flatnonzero(original_rows == selected) if selected is not None else []
    if len(hit):
        i = hit[0]
        ax.scatter([x[i]], [y[i]], s=max(areas[i] * 1.8, 100), facecolors='none', edgecolors=ACCENT, lw=1., zorder=4)
    if not len(x) and solar is None:
        ax.text(.5, .5, 'No catalog objects in this view', transform=ax.transAxes,
                ha='center', va='center', color=MUTED, fontsize=10)
    return points


def add_labels(ax, scene, state, presentation, original_rows):
    """Deterministic screen-space collision avoidance; omit labels, never stars."""
    if not state.labels or presentation.max_labels == 0:
        return []
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    x, y = scene.x_deg[scene.visible], scene.y_deg[scene.visible]
    positions = ax.transData.transform(np.column_stack((x, y)))
    areas = scene.marker_area_pt2 * presentation.marker_scale
    radii = np.maximum(np.sqrt(areas / np.pi) * fig.dpi / 72., 2.)
    # Vectorized marker bounds keep dense catalogs out of a Python O(N*labels)
    # overlap loop. Budget label candidates so a crowded sky cannot scan every
    # source trying to find impossible text placements. No stars are excluded.
    marker_boxes = np.column_stack((positions[:, 0]-radii, positions[:, 1]-radii,
                                    positions[:, 0]+radii, positions[:, 1]+radii))
    occupied = []
    order = list(np.argsort(scene.display_magnitude, kind='stable'))
    if presentation.selected_row in original_rows:
        selected = int(np.flatnonzero(original_rows == presentation.selected_row)[0])
        order.remove(selected)
        order.insert(0, selected)
    labels = []
    names = scene.candidates.name[scene.visible]
    font = FontProperties(family='DejaVu Sans', size=8)
    # Measure once per candidate, rather than constructing/removing an Artist
    # for every rejected location in a crowded panel.
    base_height = renderer.get_text_width_height_descent('lp', font, False)[1]
    budget = min(len(order), max(24, min(64, presentation.max_labels * 2)))
    for i in order[:budget]:
        if len(labels) >= presentation.max_labels:
            break
        if areas[i] < 1. and original_rows[i] != presentation.selected_row:
            continue
        offset = radii[i] * 72. / fig.dpi + 5.
        text = str(names[i])
        width, height, descent = renderer.get_text_width_height_descent(text, font, False)
        height = max(height+descent, base_height) + 2 * fig.dpi / 72.
        for dx, dy, ha, va in ((offset, 4, 'left', 'bottom'), (-offset, 4, 'right', 'bottom'),
                               (offset, -4, 'left', 'top'), (-offset, -4, 'right', 'top'),
                               (0, offset, 'center', 'bottom'), (0, -offset, 'center', 'top')):
            px, py = positions[i] + np.array([dx, dy]) * fig.dpi / 72.
            left = px if ha == 'left' else px-width if ha == 'right' else px-width/2
            bottom = py if va == 'bottom' else py-height if va == 'top' else py-height/2
            box = Bbox.from_bounds(left, bottom, width, height).expanded(1.07, 1.12)
            inside = ax.bbox.contains(box.x0, box.y0) and ax.bbox.contains(box.x1, box.y1)
            marker_collision = np.any((box.x0 < marker_boxes[:, 2]) & (box.x1 > marker_boxes[:, 0]) &
                                      (box.y0 < marker_boxes[:, 3]) & (box.y1 > marker_boxes[:, 1]))
            if inside and not marker_collision and not any(box.overlaps(other) for other in occupied):
                label = ax.annotate(text, (x[i], y[i]), xytext=(dx, dy), textcoords='offset points',
                                    color=ACCENT if original_rows[i] == presentation.selected_row else '#bbc9dc',
                                    fontsize=8, fontfamily='DejaVu Sans', ha=ha, va=va, zorder=5, annotation_clip=True)
                occupied.append(box)
                labels.append(label)
                break
    return labels


def draw_figure(figure, catalog, state, presentation, title, *, for_export=False):
    """Return panels with scenes and original catalog row IDs for picking."""
    figure.clear()
    figure.set_facecolor(BACKGROUND)
    count = 2 if presentation.comparison else 1
    axes = figure.subplots(1, count, squeeze=False)[0]
    figure.subplots_adjust(left=.085 if count == 1 else .065, right=.975, bottom=.16 if for_export else .13,
                           top=.77 if for_export else .90, wspace=.24)
    panels = []
    for i, ax in enumerate(axes):
        panel_state = replace(state, beta=0.) if count == 2 and i == 0 else state
        scene, solar, occulted = compute_view(catalog,panel_state,presentation)
        rows = np.flatnonzero(catalog.vmag <= state.rest_mag_limit)[scene.visible]
        draw_view(ax, scene, panel_state, presentation, rows, presentation.selected_row,solar)
        moving = not (count == 2 and i == 0)
        heading = 'MOVING OBSERVER' if moving else 'REST FRAME'
        dop = scene.doppler[scene.visible]
        subtitle = f'β {panel_state.beta:.6g}   ·   γ {lorentz_factor(panel_state.beta):.5g}   ·   {scene.n_visible} catalog objects'
        if solar is not None:
            subtitle += ' · Sol model'
        ax.set_title(heading + '\n' + subtitle, loc='left', color=FOREGROUND, fontsize=9, pad=13, linespacing=1.8)
        panels.append({'ax': ax, 'scene': scene, 'state': panel_state, 'rows': rows,
                       'solar':solar,'solar_occulted':occulted})
    if for_export:
        figure.text(.065, .947, 'RELATIVISTIC SPACESHIP VIEWER', color=ACCENT, fontsize=10, weight='bold')
        figure.text(.065, .900, title, color=FOREGROUND, fontsize=16, weight='bold')
        ra, dec = state.camera.radec
        figure.text(.065, .861, f'Heading RA {state.heading_ra_deg:.4f}° / Dec {state.heading_dec_deg:.4f}°   |   '
                    f'Camera RA {ra:.4f}° / Dec {dec:.4f}°   |   FOV {state.hfov_deg:g}° × {state.vfov_deg:g}°',
                    color=MUTED, fontsize=8)
        notes = (f'Rest V ≤ {state.rest_mag_limit:g}; completeness unknown.  '
                 f'Colors: {"approximate Doppler RGB" if state.doppler_colors else "rest B−V RGB proxy"}.  '
                 f'Brightness: {"illustrative D³ marker area" if state.illustrative_brightness else "rest-magnitude marker area"}.')
        renderer = figure.canvas.get_renderer()
        font = FontProperties(family='DejaVu Sans', size=7)
        width_limit = figure.bbox.width * .91
        lines, current = [], ''
        for paragraph in (notes, 'Instantaneous directions only. No travel, calibrated photometry, or uncertainty propagation.',
                           'M42, when present, is an extended-object point placeholder.'):
            for word in paragraph.split():
                proposed = (current+' '+word).strip()
                if current and renderer.get_text_width_height_descent(proposed, font, False)[0] > width_limit:
                    lines.append(current)
                    current = word
                else:
                    current = proposed
            lines.append(current)
            current = ''
        figure.text(.065, .092, '\n'.join(lines), va='top', color=MUTED, fontsize=7,
                    fontfamily='DejaVu Sans', linespacing=1.35)
    figure.canvas.draw()
    for panel in panels:
        panel['labels'] = add_labels(panel['ax'], panel['scene'], panel['state'], presentation, panel['rows'])
    return panels
