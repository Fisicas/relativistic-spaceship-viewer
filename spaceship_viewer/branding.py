"""One inspectable SVG source for the window icon, installer, and preview art."""
from pathlib import Path

MARK = Path(__file__).parent/'assets/viewer_mark.svg'

def icon_pixmap(size=64,background=None):
    from PySide6 import QtCore,QtGui,QtSvg
    image=QtGui.QPixmap(size,size)
    image.fill(QtGui.QColor(background) if background else QtCore.Qt.GlobalColor.transparent)
    painter=QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    renderer=QtSvg.QSvgRenderer(str(MARK))
    if not renderer.isValid():
        raise ValueError('Invalid viewer mark SVG.')
    pad=size*.09
    renderer.render(painter,QtCore.QRectF(pad,pad,size-2*pad,size-2*pad))
    painter.end()
    return image
