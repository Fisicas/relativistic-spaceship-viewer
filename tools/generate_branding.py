"""Render selected vector branding and a real simulated sky; no generated sky art."""
from pathlib import Path
from dataclasses import asdict
import argparse,hashlib,json,math,os,sys
from xml.sax.saxutils import escape
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from PySide6 import QtCore,QtGui,QtWidgets,QtSvg
from PIL import Image
from spaceship_viewer.branding import MARK
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.state import ViewState
from spaceship_viewer.scene import compute_scene

def render_svg(source,target,width,height):
    image=QtGui.QImage(width,height,QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.GlobalColor.transparent)
    painter=QtGui.QPainter(image);painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    renderer=QtSvg.QSvgRenderer(str(source));assert renderer.isValid()
    renderer.render(painter);painter.end();assert image.save(str(target))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    out=parser.parse_args().output_dir;out.mkdir(parents=True,exist_ok=False)
    app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
        QtGui.QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'/name))
    mark=MARK.read_text(encoding='utf-8')
    mono=out/'viewer_mark_monochrome.svg'
    mono.write_text(mark.replace('#79d8ea','#e8e8e8').replace('#e6aa58','#e8e8e8'),encoding='utf-8')
    render_svg(MARK,out/'viewer_mark_256.png',256,256)
    image=Image.open(out/'viewer_mark_256.png')
    image.save(out/'viewer.ico',sizes=[(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(128,128),(256,256)])
    # All sampled coordinates/colors come from the unchanged numerical core.
    width,height=1280,640
    px,py,pw,ph=64.,226.,1152.,304.
    state=ViewState(beta=math.sqrt(3)/2,hfov_deg=80.,vfov_deg=80*ph/pw)
    catalog=built_in_catalog();scene=compute_scene(catalog,state)
    rows=np.flatnonzero(catalog.vmag<=state.rest_mag_limit)[scene.visible]
    pieces=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<title>Relativistic Spaceship Viewer</title>',
            '<desc>Actual gamma=2 inherited demo sky, rectangular angular map. Point colors and brightness are illustrative.</desc>',
            '<rect width="1280" height="640" fill="#191919"/>',
            '<g font-family="Segoe UI,Arial,sans-serif" fill="#eeeeee">',
            '<text x="64" y="84" font-size="46" font-weight="600">RELATIVISTIC</text>',
            '<text x="64" y="143" font-size="46" font-weight="600">SPACESHIP VIEWER</text>',
            '<text x="66" y="188" font-size="21" fill="#b4b4b4">An instantaneous sky, transformed.</text>','</g>',
            '<g transform="translate(1100 45) scale(.116)">'+mark.split('>',1)[1].rsplit('</svg>',1)[0]+'</g>',
            f'<rect x="{px-2}" y="{py-2}" width="{pw+4}" height="{ph+4}" rx="8" fill="#121212" stroke="#555555"/>']
    sx=lambda x:px+(float(x)/state.hfov_deg+.5)*pw
    sy=lambda y:py+(.5-float(y)/state.vfov_deg)*ph
    for x in range(-40,41,10):pieces.append(f'<path d="M{sx(x)} {py}V{py+ph}" stroke="#303030" stroke-width=".7"/>')
    for y in range(-10,11,5):pieces.append(f'<path d="M{px} {sy(y)}H{px+pw}" stroke="#303030" stroke-width=".7"/>')
    label_boxes=[];drawn=[]
    for i,(x,y,area,rgb,row) in enumerate(zip(scene.x_deg[scene.visible],scene.y_deg[scene.visible],scene.marker_area_pt2,scene.rgb,rows)):
        xx,yy=sx(x),sy(y);radius=float(np.clip(math.sqrt(area/math.pi)*.72,1.8,8.))
        color='#'+''.join(f'{int(v*255):02x}' for v in np.clip(rgb,0,1))
        pieces.append(f'<circle cx="{xx:.6f}" cy="{yy:.6f}" r="{radius*2:.5f}" fill="{color}" opacity=".10"/>')
        pieces.append(f'<circle cx="{xx:.6f}" cy="{yy:.6f}" r="{radius:.5f}" fill="{color}"/>')
        if len(drawn)<9 and px+15<xx<px+pw-130 and py+20<yy<py+ph-20 and all(abs(xx-a)>95 or abs(yy-b)>25 for a,b in label_boxes):
            pieces.append(f'<text x="{xx+radius+7:.5f}" y="{yy-7:.5f}" font-family="Segoe UI,Arial,sans-serif" font-size="12" fill="#bcbcbc">{escape(str(catalog.name[row]))}</text>')
            label_boxes.append((xx,yy));drawn.append(int(row))
    pieces.extend(['<g fill="#bcbcbc" font-family="Segoe UI,Arial,sans-serif" font-size="17" letter-spacing="2">',
                   '<text x="80" y="590">ABERRATION</text><text x="475" y="590">DOPPLER SHIFT</text><text x="935" y="590">SOL AT 1 AU</text>','</g></svg>'])
    svg=out/'social-preview.svg';svg.write_text('\n'.join(pieces),encoding='utf-8',newline='\n')
    render_svg(svg,out/'social-preview.png',width,height)
    assert (out/'social-preview.png').stat().st_size<1000000
    record={'status':'passed','size_px':[width,height],'png_bytes':(out/'social-preview.png').stat().st_size,
        'view':asdict(state),'catalog_source':asdict(catalog.metadata),'visible_catalog_rows':rows.tolist(),
        'named_labels_drawn':drawn,'display':'Actual core x/y/RGB/marker areas; SVG point radius mapping sqrt(area/pi)*0.72, clipped 1.8..8 px; 10% halo; no inferred measurements.',
        'brand':'Flat SVG redraw of selected logo 1; cyan/amber only in mark and scientific data.',
        'theme':'Neutral charcoal/gray chrome; no decorative galaxy or AI-generated sky.',
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}}
    (out/'branding_provenance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'status':'passed','size_px':[width,height],'png_bytes':record['png_bytes'],'output':str(out)},indent=2))
if __name__=='__main__':main()
