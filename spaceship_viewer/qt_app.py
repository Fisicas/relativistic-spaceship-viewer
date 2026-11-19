"""Qt desktop interface for the validated instantaneous sky model."""
from __future__ import annotations

from dataclasses import replace
import math
import os
from pathlib import Path
import queue
import sys
import threading
import time
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as W
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from . import __version__
from .catalog import load_csv, fetch_hipparcos, UnitRequiredError
from .demo_catalog import built_in_catalog
from .exporting import export_scene
from .geometry import CameraPose,unit_to_radec
from .inspection import inspect_object
from .navigation import center_object, widescreen_fov, WIDESCREEN_RATIO,MIN_FOV
from .solar import SolarSettings,solar_reference,solar_geometry,AU_M,SOLAR_RADIUS_M,REST_RADIUS_RAD
from .solar_radiometry import summary as solar_radiance_summary, fitted_exposure, MIN_EV, MAX_EV
from .plotting import draw_figure, BACKGROUND
from .branding import icon_pixmap,MARK
from . import catalog_cache
from .presentation import Presentation
from .relativity import MAX_BETA, lorentz_factor, rest_frame_half_angle
from .session import load_document, save_document
from .state import ViewState
from .targets import ReferenceTarget

STYLE = '''
QMainWindow, QWidget { background: #191919; color: #e2e2e2; font-family: 'Segoe UI'; font-size: 10pt; }
QWidget#header { background: #202020; border-bottom: 1px solid #393939; }
QLabel { background: transparent; }
QLabel#brand { color: #f0f0f0; font-size: 16pt; font-weight: 600; }
QLabel#eyebrow { color: #d0d0d0; font-size: 9pt; font-weight: 600; }
QLabel#muted { color: #a4a4a4; font-size: 9pt; }
QLabel#metric { color: #ededed; font-size: 19pt; font-weight: 500; }
QFrame#skyBezel { background: #222222; border: 1px solid #505050; border-radius: 10px; }
QFrame#instrumentPod, QFrame#speedRail { background: #222222; border: 1px solid #393939; border-radius: 7px; }
QLabel#inspectorTitle { color: #ededed; font-size: 17pt; font-weight: 500; }
QFrame#metricCard { background: #242424; border: 1px solid #3b3b3b; border-radius: 7px; }
QGroupBox { border: 1px solid #414141; border-radius: 7px; margin-top: 13px; padding: 12px 10px 9px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 11px; padding: 0px 5px; color: #c0c0c0; }
QPushButton, QToolButton { background: #2a2a2a; color: #e8e8e8; border: 1px solid #484848; border-radius: 5px; padding: 7px 10px; }
QPushButton:hover, QToolButton:hover { background: #363636; border-color: #c0c0c0; }
QPushButton:pressed { background: #303030; }
QPushButton:checked, QToolButton:checked { background: #414141; border-color: #a6a6a6; }
QPushButton#primary { background: #dedede; color: #151515; border: none; font-weight: 600; }
QPushButton:disabled { color: #777777; border-color: #333333; }
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit { background: #171717; color: #e6e6e6; border: 1px solid #4b4b4b; border-radius: 4px; padding: 5px; min-height: 20px; }
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: #b0b0b0; }
QCheckBox { spacing: 7px; padding: 3px 0; font-weight: 400; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #6a6a6a; border-radius: 3px; background: #171717; }
QCheckBox::indicator:checked { background: #c4c4c4; border-color: #c4c4c4; image: url("__CHECKMARK_URL__"); }
QSlider::groove:horizontal { height: 4px; background: #4a4a4a; border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -5px 0; border-radius: 6px; background: #dedede; }
QScrollArea { border: none; } QScrollBar:vertical { background: #1c1c1c; width: 9px; }
QScrollBar::handle:vertical { background: #4b4b4b; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QSplitter::handle { background: #3a3a3a; width: 1px; }
QTabWidget::pane { border: none; } QTabBar::tab { padding: 9px 12px; color: #a0a0a0; }
QTabBar::tab:selected { color: #eeeeee; border-bottom: 2px solid #c4c4c4; }
QPlainTextEdit, QTextBrowser { border: none; background: #1c1c1c; padding: 8px; color: #c4c4c4; }
QStatusBar { background: #171717; color: #a8a8a8; border-top: 1px solid #393939; }
QMenuBar, QMenu { background: #202020; color: #d8d8d8; } QMenu::item:selected { background: #383838; }
QToolTip { background: #303030; color: #eeeeee; border: 1px solid #777777; }
'''.replace('__CHECKMARK_URL__',(Path(__file__).parent/'assets/checkmark.svg').as_posix())


def label(text, kind=None, wrap=False):
    widget = W.QLabel(text)
    if kind:
        widget.setObjectName(kind)
    widget.setWordWrap(wrap)
    widget.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def spin(minimum, maximum, value, decimals=4, step=1.):
    widget = W.QDoubleSpinBox()
    widget.setDecimals(decimals)
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    widget.setSingleStep(step)
    widget.setKeyboardTracking(False)
    return widget


class Viewer(W.QMainWindow):
    def __init__(self):
        super().__init__()
        self.catalog, self.catalog_title = built_in_catalog(), 'Orion · inherited bright-star demo'
        self.named_targets = built_in_catalog()
        self.named_references = tuple(ReferenceTarget.from_catalog(self.named_targets, i) for i in range(self.named_targets.n))+(solar_reference(SolarSettings()),)
        self.view_state, self.presentation = ViewState(), Presentation()
        self.panels = []
        self._drag = None
        self._fetching = False
        self._catalog_revision = 0
        self._messages = queue.Queue()
        self._render_count = 0
        self._focus_fov_before = None
        self.install_root = os.environ.get('RSV_INSTALL_ROOT')
        self._update_messages = queue.Queue()
        self._checking_update = self._downloading_update = False
        self.setWindowTitle(f'Relativistic Spaceship Viewer {__version__}')
        self.setWindowIcon(QtGui.QIcon(str(MARK.parent/'viewer.ico')))
        self.setMinimumSize(1000, 680)
        self.resize(1450, 900)
        self.setStyleSheet(STYLE)
        self._build_ui()
        self.render_timer = QtCore.QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.setInterval(30)
        self.render_timer.timeout.connect(self.refresh)
        self.fetch_timer = QtCore.QTimer(self)
        self.fetch_timer.setInterval(100)
        self.fetch_timer.timeout.connect(self.poll_fetch)
        self.fetch_timer.start()
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.setInterval(200)
        self.update_timer.timeout.connect(self.poll_updates)
        self.update_timer.start()
        self._update_menu()
        self._shortcuts()
        screen = self.screen().availableGeometry()
        self.resize(min(1450, screen.width()-40), min(900, screen.height()-60))
        if screen.width() < 1400:
            self.inspect_button.setChecked(False)
            self.inspector.hide()
        self.refresh()
        if self.install_root and self._update_settings().get('check_on_startup', True):
            QtCore.QTimer.singleShot(2000, lambda: self.check_updates(automatic=True))

    def button(self, text, callback, *, primary=False, checkable=False):
        button = W.QPushButton(text)
        button.setCheckable(checkable)
        if primary:
            button.setObjectName('primary')
        button.clicked.connect(callback)
        return button

    def group(self, layout, title):
        group = W.QGroupBox(title)
        inner = W.QVBoxLayout(group)
        inner.setSpacing(7)
        layout.addWidget(group)
        return inner

    def instrument_pod(self,fields):
        frame=W.QFrame()
        frame.setObjectName('instrumentPod')
        frame.setFixedWidth(145)
        layout=W.QVBoxLayout(frame)
        layout.setContentsMargins(12,20,12,18)
        layout.setSpacing(12)
        for title,key in fields:
            layout.addWidget(label(title,'muted',True))
            value=label('—','metric',True)
            value.setStyleSheet('font-size:17pt;')
            layout.addWidget(value)
            self.pod_values[key]=value
        layout.addStretch()
        layout.addWidget(label('Instantaneous\nobserver event','muted',True))
        return frame

    def _update_cockpit_layout(self):
        if not hasattr(self,'left_pod'):return
        expanded=self.focus_button.isChecked() and self.width()>=1600 and self.height()>=820 and not self.presentation.comparison
        self.left_pod.setVisible(expanded)
        self.right_pod.setVisible(expanded)
        self.metrics_strip.setVisible(not expanded)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self._update_cockpit_layout()
        if hasattr(self,'render_timer'):self._schedule()

    def _build_ui(self):
        root = W.QWidget()
        self.setCentralWidget(root)
        layout = W.QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        header = W.QWidget()
        header.setObjectName('header')
        bar = W.QHBoxLayout(header)
        bar.setContentsMargins(20, 13, 20, 13)
        mark=W.QLabel()
        mark.setPixmap(icon_pixmap(44))
        mark.setFixedSize(46,46)
        bar.addWidget(mark)
        brand = W.QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label('Relativistic Spaceship Viewer', 'brand'))
        brand.addWidget(label('An instantaneous sky, seen through a Lorentz boost', 'muted'))
        bar.addLayout(brand)
        bar.addStretch()
        self.compare_button = self.button('Compare rest / moving', self.toggle_comparison, checkable=True)
        bar.addWidget(self.compare_button)
        self.focus_button = self.button('Focus sky', self.focus_sky, checkable=True)
        bar.addWidget(self.focus_button)
        self.inspect_button = self.button('Inspector', lambda value: self.inspector.setVisible(value and not self.focus_button.isChecked()), checkable=True)
        self.inspect_button.setChecked(True)
        bar.addWidget(self.inspect_button)
        bar.addWidget(self.button('Open scene', self.open_scene))
        bar.addWidget(self.button('Save scene', self.save_scene))
        bar.addWidget(self.button('Export…', self.export_dialog, primary=True))
        layout.addWidget(header)
        self.splitter = W.QSplitter(QtCore.Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)
        controls_scroll = W.QScrollArea()
        self.controls_scroll = controls_scroll
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setMinimumWidth(310)
        controls_scroll.setMaximumWidth(340)
        control_widget = W.QWidget()
        controls = W.QVBoxLayout(control_widget)
        controls.setContentsMargins(14, 10, 14, 14)
        controls.setSpacing(9)
        controls_scroll.setWidget(control_widget)
        self.splitter.addWidget(controls_scroll)

        velocity = self.group(controls, 'VELOCITY')
        velocity.addWidget(label('Set β or γ. The slider uses rapidity.', 'muted', True))
        values = W.QFormLayout()
        self.beta_spin = spin(0., MAX_BETA, 0., 9, .01)
        self.beta_spin.setAccessibleName('Speed beta v divided by c')
        self.beta_spin.valueChanged.connect(self.set_beta)
        self.gamma_spin = spin(1., lorentz_factor(MAX_BETA), 1., 8, .1)
        self.gamma_spin.setAccessibleName('Lorentz factor gamma')
        self.gamma_spin.valueChanged.connect(self.set_gamma)
        values.addRow('β = v/c', self.beta_spin)
        values.addRow('Lorentz γ', self.gamma_spin)
        velocity.addLayout(values)
        self.speed_slider = W.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.speed_slider.setRange(0, 10000)
        self.speed_slider.setAccessibleName('Rapidity speed slider')
        self.speed_slider.valueChanged.connect(lambda v: self.set_beta(math.tanh(v/10000 * math.atanh(MAX_BETA))))
        velocity.addWidget(self.speed_slider)
        presets = W.QHBoxLayout()
        for text, value in (('Rest', 0.), ('0.30 c', .3), ('γ = 2', math.sqrt(3.)/2)):
            presets.addWidget(self.button(text, lambda checked=False, v=value: self.set_beta(v)))
        velocity.addLayout(presets)

        pointing = self.group(controls, 'HEADING & CAMERA')
        self.preset = W.QComboBox()
        self.preset.addItems(['Orion', 'Galactic Center', 'Tau Ceti', 'Custom heading'])
        self.preset.setPlaceholderText('Manual RA / Dec')
        self.preset.setToolTip('Choose a velocity heading. Custom uses the inspector object’s rest direction.')
        self.preset.activated.connect(self.apply_preset)
        pointing.addWidget(self.preset)
        form = W.QFormLayout()
        self.ra_spin, self.dec_spin = spin(0., 359.999999, 84., 6), spin(-90., 90., -1., 6)
        form.addRow('Heading RA (°)', self.ra_spin)
        form.addRow('Heading Dec (°)', self.dec_spin)
        pointing.addLayout(form)
        pointing.addWidget(self.button('Apply velocity heading', self.apply_heading))
        self.lock_check = W.QCheckBox('Camera follows velocity heading')
        self.lock_check.setChecked(True)
        self.lock_check.toggled.connect(self.set_lock)
        pointing.addWidget(self.lock_check)
        self.camera_text = label('', 'muted', True)
        pointing.addWidget(self.camera_text)
        pointing.addWidget(self.button('Recenter camera', self.recenter))
        pointing.addWidget(label('Drag to look / steer · Wheel to zoom\nSky focus: arrows turn · R resets · F expands', 'muted', True))

        field = self.group(controls, 'FIELD & DISPLAY')
        fov = W.QFormLayout()
        self.hfov_spin, self.vfov_spin = spin(MIN_FOV, 160., 45., 6, 1.), spin(MIN_FOV, 160., 45., 6, 1.)
        self.hfov_spin.valueChanged.connect(lambda v: self.change(hfov_deg=v))
        self.vfov_spin.valueChanged.connect(lambda v: self.change(vfov_deg=v))
        self.mag_spin = spin(-5., 20., 8., 1, .5)
        self.mag_spin.valueChanged.connect(lambda v: self.change(rest_mag_limit=v))
        fov.addRow('Horizontal FOV (°)', self.hfov_spin)
        fov.addRow('Vertical FOV (°)', self.vfov_spin)
        fov.addRow('Rest V limit', self.mag_spin)
        field.addLayout(fov)
        self.color_check = W.QCheckBox('Doppler colors · approximate RGB')
        self.brightness_check = W.QCheckBox('Illustrative D³ brightness')
        self.glow_check = W.QCheckBox('Soft glow · presentation only')
        self.labels_check = W.QCheckBox('Object labels')
        self.grid_check = W.QCheckBox('Angular grid')
        for widget, keyword in ((self.color_check, 'doppler_colors'), (self.brightness_check, 'illustrative_brightness'),
                                (self.glow_check, 'glow'), (self.labels_check, 'labels')):
            widget.setChecked(True)
            widget.toggled.connect(lambda checked, key=keyword: self.change(**{key: checked}))
            field.addWidget(widget)
        self.grid_check.setChecked(True)
        self.grid_check.toggled.connect(lambda v: self.change_presentation(grid=v))
        field.addWidget(self.grid_check)
        extra = W.QFormLayout()
        self.label_spin = W.QSpinBox()
        self.label_spin.setRange(0, 40)
        self.label_spin.setValue(12)
        self.label_spin.valueChanged.connect(lambda v: self.change_presentation(max_labels=v))
        self.marker_spin = spin(.1, 3., .85, 2, .1)
        self.marker_spin.valueChanged.connect(lambda v: self.change_presentation(marker_scale=v))
        extra.addRow('Maximum labels', self.label_spin)
        extra.addRow('Marker area scale', self.marker_spin)
        field.addLayout(extra)

        source = self.group(controls, 'CATALOG')
        self.source_text = label('', 'muted', True)
        source.addWidget(self.source_text)
        self.import_button = self.button('Import CSV…', self.import_csv)
        self.fetch_button = self.button('Load local Hipparcos', self.load_hipparcos_library)
        self.demo_button = self.button('Restore demo catalog', self.restore_demo)
        for button in (self.import_button, self.fetch_button, self.demo_button):
            source.addWidget(button)
        source.addWidget(self.button('Download / refresh Hipparcos…',self.start_fetch))
        source.addWidget(self.button('Catalog startup…',self.catalog_startup_dialog))
        source.addWidget(self.button('Catalog provenance…', self.show_provenance))
        controls.addStretch()

        center = W.QWidget()
        central = W.QVBoxLayout(center)
        central.setContentsMargins(14, 14, 14, 7)
        central.setSpacing(10)
        self.metrics_strip=W.QWidget()
        metrics = W.QHBoxLayout(self.metrics_strip)
        metrics.setContentsMargins(0,0,0,0)
        self.metrics = {}
        for title, key in (('LORENTZ FACTOR', 'gamma'), ('CATALOG DOPPLER RANGE', 'doppler'), ('CATALOG VISIBLE / LOADED', 'count')):
            card = W.QFrame()
            card.setObjectName('metricCard')
            card_layout = W.QVBoxLayout(card)
            card_layout.setContentsMargins(12, 9, 12, 9)
            card_layout.addWidget(label(title, 'muted'))
            value = label('—', 'metric')
            self.metrics[key] = value
            card_layout.addWidget(value)
            metrics.addWidget(card)
        central.addWidget(self.metrics_strip)
        self.figure = Figure(figsize=(8., 7.), dpi=100, facecolor=BACKGROUND)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(320, 280)
        self.canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        sky_row=W.QHBoxLayout()
        sky_row.setSpacing(12)
        self.pod_values={}
        self.left_pod=self.instrument_pod((('LORENTZ γ','gamma'),('SPEED β','beta')))
        self.right_pod=self.instrument_pod((('CATALOG D','doppler'),('VISIBLE / LOADED','count')))
        sky_row.addWidget(self.left_pod)
        self.sky_bezel=W.QFrame()
        self.sky_bezel.setObjectName('skyBezel')
        bezel_layout=W.QVBoxLayout(self.sky_bezel)
        bezel_layout.setContentsMargins(7,7,7,7)
        bezel_layout.setSpacing(0)
        bezel_layout.addWidget(self.canvas,1)
        sky_row.addWidget(self.sky_bezel,1)
        sky_row.addWidget(self.right_pod)
        self.left_pod.hide();self.right_pod.hide()
        central.addLayout(sky_row,1)
        self.speed_rail=W.QFrame()
        self.speed_rail.setObjectName('speedRail')
        rail_layout=W.QVBoxLayout(self.speed_rail)
        rail_layout.setContentsMargins(12,8,12,8)
        rail_layout.setSpacing(4)
        rail_top=W.QHBoxLayout()
        self.rail_speed_text=label('','muted')
        rail_top.addWidget(self.rail_speed_text,1)
        for text,value in (('Rest',0.),('0.30 c',.3),('γ = 2',math.sqrt(3)/2)):
            rail_top.addWidget(self.button(text,lambda checked=False,v=value:self.set_beta(v)))
        rail_top.addWidget(self.button('Catalog…',self.catalog_startup_dialog))
        rail_layout.addLayout(rail_top)
        self.cockpit_speed_slider=W.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.cockpit_speed_slider.setRange(0,10000)
        self.cockpit_speed_slider.setAccessibleName('Wide cockpit rapidity speed slider')
        self.cockpit_speed_slider.setToolTip('Speed uses the same rapidity scale as the sidebar; both controls stay synchronized.')
        self.cockpit_speed_slider.valueChanged.connect(lambda v:self.set_beta(math.tanh(v/10000*math.atanh(MAX_BETA))))
        rail_layout.addWidget(self.cockpit_speed_slider)
        central.addWidget(self.speed_rail)
        self.scene_note = label('', 'muted', True)
        central.addWidget(self.scene_note)
        self.splitter.addWidget(center)

        self.inspector = W.QTabWidget()
        self.inspector.setMinimumWidth(240)
        self.inspector.setMaximumWidth(320)
        inspect_page = W.QWidget()
        inspect_layout = W.QVBoxLayout(inspect_page)
        inspect_layout.setContentsMargins(12, 18, 12, 12)
        inspect_layout.addWidget(label('OBJECT INSPECTOR', 'eyebrow'))
        self.object_combo = W.QComboBox()
        self.object_combo.setPlaceholderText('Select a named target')
        self.object_combo.setMaxVisibleItems(12)
        self.object_combo.activated.connect(self.select_named_target)
        inspect_layout.addWidget(label('Original named targets · click the sky for catalog stars', 'muted', True))
        inspect_layout.addWidget(self.object_combo)
        self.object_name = label('Choose an object', 'inspectorTitle', True)
        inspect_layout.addWidget(self.object_name)
        self.object_details = W.QTextBrowser()
        self.object_details.setOpenExternalLinks(False)
        inspect_layout.addWidget(self.object_details, 1)
        self.solar_group=W.QGroupBox('SOL · FIXED 1 AU MODEL')
        solar_layout=W.QVBoxLayout(self.solar_group)
        solar_layout.setContentsMargins(4,8,4,4)
        solar_form=W.QFormLayout()
        solar_form.setRowWrapPolicy(W.QFormLayout.RowWrapPolicy.WrapAllRows)
        self.solar_ra_spin,self.solar_dec_spin=spin(0.,359.999999,0.,6),spin(-90.,90.,0.,6)
        solar_form.addRow('Sun RA (°)',self.solar_ra_spin)
        solar_form.addRow('Sun Dec (°)',self.solar_dec_spin)
        solar_layout.addLayout(solar_form)
        solar_layout.addWidget(self.button('Apply Sun direction',self.apply_solar_direction))
        self.solar_show_check=W.QCheckBox('Show solar disk')
        self.solar_show_check.setToolTip('Show the photosphere and occult distant background rays behind it.')
        self.solar_show_check.toggled.connect(lambda v:self.update_solar(enabled=v))
        solar_layout.addWidget(self.solar_show_check)
        self.solar_track_check=W.QCheckBox('Track Sol during boost')
        self.solar_track_check.toggled.connect(lambda v:self.update_solar(track_center=v))
        solar_layout.addWidget(self.solar_track_check)
        solar_layout.addWidget(self.button('Frame solar disk',self.frame_solar_disk))
        quick=W.QHBoxLayout()
        quick.setSpacing(3)
        for text,mode in (('Toward','toward'),('Away','away'),('90°','transverse')):
            button=self.button(text,lambda checked=False,m=mode:self.solar_heading(m))
            button.setToolTip('Set velocity heading relative to Sol; keep the disk centered.')
            quick.addWidget(button)
        solar_layout.addLayout(quick)
        self.solar_radiometry_check=W.QCheckBox('Doppler spectrum')
        self.solar_radiometry_check.setToolTip('Uniform 5772 K blackbody, shifted independently for each ray. No limb darkening.')
        self.solar_radiometry_check.toggled.connect(lambda v:self.update_solar(radiometry_enabled=v))
        solar_layout.addWidget(self.solar_radiometry_check)
        self.solar_exposure_spin=spin(MIN_EV,MAX_EV,0.,2)
        self.solar_exposure_spin.setSuffix(' EV')
        self.solar_exposure_spin.setToolTip('Fixed display exposure; +1 EV doubles linear exposure. Does not alter physical radiance or angular size.')
        self.solar_exposure_spin.valueChanged.connect(lambda v:self.update_solar(exposure_ev=v))
        exposure_form=W.QFormLayout()
        exposure_form.setRowWrapPolicy(W.QFormLayout.RowWrapPolicy.WrapAllRows)
        exposure_form.addRow('Display exposure',self.solar_exposure_spin)
        solar_layout.addLayout(exposure_form)
        solar_layout.addWidget(self.button('Fit exposure once',self.fit_solar_exposure))
        self.solar_outline_check=W.QCheckBox('Outline (annotation)')
        self.solar_outline_check.toggled.connect(lambda v:self.update_solar(show_outline=v))
        solar_layout.addWidget(self.solar_outline_check)
        self.solar_scroll=W.QScrollArea()
        self.solar_scroll.setWidgetResizable(True)
        self.solar_scroll.setMinimumHeight(120)
        self.solar_scroll.setMaximumHeight(300)
        self.solar_scroll.setWidget(self.solar_group)
        inspect_layout.addWidget(self.solar_scroll)
        self.solar_scroll.hide()
        inspect_layout.addWidget(label('Selecting centers the camera. Heading actions steer the velocity. The rest-magnitude cut applies to catalog stars.', 'muted', True))
        self.inspector.addTab(inspect_page, 'Object')
        self.physics_page = W.QTextBrowser()
        self.physics_page.setHtml('''<h3>Light, transformed</h3><p>Source directions point from observer to source. Photon momentum points the other way.</p>
<p><b>γ = 1 / √(1 − β²)</b></p><p><b>D = γ(1 + β cos θ)</b></p><p><b>cos θ′ = (cos θ + β) / (1 + β cos θ)</b></p>
<p><b>λ′ = λ / D</b></p><p>D &gt; 1: blueshift. D &lt; 1: redshift. Some sources behind the transverse plane are also blueshifted.</p>
<h3>What this view means</h3><p>Grid values are independent horizontal/vertical angular axes. Right is camera west; up is camera north.</p>
<p>Rest V is filtered before boosting. Catalog completeness is unknown. Color, D³ marker area, and glow are illustrative.</p>
<p>No travel, acceleration, proper motion, calibrated detector response, or uncertainty propagation is calculated.</p>
<p>The demo values have unspecified frame/epoch. M42 is an extended-object point placeholder.</p>''')
        self.inspector.addTab(self.physics_page, 'Physics')
        self.splitter.addWidget(self.inspector)
        self.splitter.setSizes([320, 840, 285])
        self.splitter.setStretchFactor(1, 1)
        self.statusBar().showMessage('Ready · offline demo')
        for event, callback in (('button_press_event', self.on_press), ('motion_notify_event', self.on_motion),
                                ('button_release_event', self.on_release), ('scroll_event', self.on_scroll)):
            self.canvas.mpl_connect(event, callback)
        self.canvas.mpl_connect('resize_event', lambda _: self._schedule() if hasattr(self, 'render_timer') else None)
        self._populate_objects()

    def _shortcuts(self):
        self.shortcuts = []
        for key, callback in (('R', self.reset), ('C', lambda: self.compare_button.click()), ('F', lambda: self.focus_button.click()),
                              ('I', lambda: self.inspect_button.click()), ('Ctrl+S', self.save_scene),
                              ('Ctrl+O', self.open_scene), ('Ctrl+E', self.export_dialog),
                              ('Left', lambda: self.turn(-2., 0.)), ('Right', lambda: self.turn(2., 0.)),
                              ('Up', lambda: self.turn(0., 2.)), ('Down', lambda: self.turn(0., -2.))):
            shortcut = QtGui.QShortcut(QtGui.QKeySequence(key), self)
            if key in ('Left', 'Right', 'Up', 'Down', 'R', 'C', 'I', 'F'):
                shortcut.setParent(self.canvas)
                shortcut.setContext(QtCore.Qt.ShortcutContext.WidgetShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

    def _schedule(self):
        # Coalesce event bursts without continually postponing a drag frame.
        if not self.render_timer.isActive():
            self.render_timer.start()

    def change(self, **kwargs):
        if self._focus_fov_before is not None and ('hfov_deg' in kwargs or 'vfov_deg' in kwargs):
            vertical = kwargs.get('vfov_deg', kwargs.get('hfov_deg', self.view_state.hfov_deg) / WIDESCREEN_RATIO)
            kwargs['hfov_deg'], kwargs['vfov_deg'] = widescreen_fov(vertical)
        self.view_state = replace(self.view_state, **kwargs)
        if 'beta' in kwargs:
            self._track_solar()
        self._schedule()

    def change_presentation(self, **kwargs):
        self.presentation = replace(self.presentation, **kwargs)
        self._schedule()

    def set_beta(self, beta):
        self.change(beta=min(float(beta), MAX_BETA))

    def set_gamma(self, gamma):
        self.set_beta(math.sqrt(max(0., (gamma-1.) * (gamma+1.))) / gamma)

    def apply_preset(self, index):
        if 0 <= index < 3:
            ra, dec = ((84., -1.), (266.4168, -29.0078), (26.0170, -15.9375))[index]
            self.view_state = self.view_state.with_heading(ra, dec)
            self._track_solar()
            self._schedule()
        elif index == 3 and self._inspection_selection() is not None:
            catalog, row, _ = self._inspection_selection()
            # Rest catalog direction defines a velocity heading. A source
            # exactly along that heading remains centered under aberration.
            self.view_state = self.view_state.with_lock(False).with_heading(
                float(catalog.ra_deg[row]), float(catalog.dec_deg[row])).with_lock(True)
            if self.presentation.solar is not None:
                self.presentation=replace(self.presentation,solar=replace(self.presentation.solar,track_center=False))
            self._schedule()

    def apply_heading(self):
        self.view_state = self.view_state.with_heading(self.ra_spin.value(), self.dec_spin.value())
        self._track_solar()
        with QtCore.QSignalBlocker(self.preset):
            self.preset.setCurrentIndex(3)
        self._schedule()

    def set_lock(self, checked):
        if checked and self.presentation.solar is not None:
            self.presentation=replace(self.presentation,solar=replace(self.presentation.solar,track_center=False))
        self.view_state = self.view_state.with_lock(checked)
        self._schedule()

    def recenter(self):
        camera = CameraPose.from_radec(self.view_state.heading_ra_deg, self.view_state.heading_dec_deg)
        self.view_state = self.view_state.with_camera(camera)
        self._schedule()

    def reset(self):
        self.focus_sky(False)
        self.view_state, self.presentation = ViewState(), Presentation()
        self._schedule()

    def toggle_comparison(self, value):
        self.change_presentation(comparison=value)

    def focus_sky(self, focused):
        with QtCore.QSignalBlocker(self.focus_button):
            self.focus_button.setChecked(focused)
        if focused and self._focus_fov_before is None:
            self._focus_fov_before = (self.view_state.hfov_deg, self.view_state.vfov_deg)
            horizontal, vertical = widescreen_fov(self.view_state.vfov_deg)
            self.view_state = replace(self.view_state, hfov_deg=horizontal, vfov_deg=vertical)
        elif not focused and self._focus_fov_before is not None:
            horizontal, vertical = self._focus_fov_before
            self.view_state = replace(self.view_state, hfov_deg=horizontal, vfov_deg=vertical)
            self._focus_fov_before = None
        self.controls_scroll.setVisible(not focused)
        self.inspector.setVisible(not focused and self.inspect_button.isChecked())
        self._schedule()

    def _sync_widgets(self):
        s, p = self.view_state, self.presentation
        solar=p.solar or SolarSettings()
        self.named_references=self.named_references[:33]+(solar_reference(solar),)
        settings = ((self.beta_spin, s.beta), (self.gamma_spin, lorentz_factor(s.beta)),
                    (self.speed_slider, round(math.atanh(s.beta) / math.atanh(MAX_BETA) * 10000)),
                    (self.ra_spin, s.heading_ra_deg), (self.dec_spin, s.heading_dec_deg),
                    (self.hfov_spin, s.hfov_deg), (self.vfov_spin, s.vfov_deg), (self.mag_spin, s.rest_mag_limit),
                    (self.marker_spin, p.marker_scale), (self.label_spin, p.max_labels))
        for widget, value in settings:
            with QtCore.QSignalBlocker(widget):
                widget.setValue(value)
        with QtCore.QSignalBlocker(self.cockpit_speed_slider):
            self.cockpit_speed_slider.setValue(round(math.atanh(s.beta)/math.atanh(MAX_BETA)*10000))
        self._update_cockpit_layout()
        targets = ((84., -1.), (266.4168, -29.0078), (26.0170, -15.9375))
        selection = self._inspection_selection()
        self.preset.setItemText(3, f'Custom: {selection[0].name[selection[1]]}' if selection else 'Custom heading')
        if selection:
            catalog, row, _ = selection
            targets += ((float(catalog.ra_deg[row]), float(catalog.dec_deg[row])),)
        preset_index = next((i for i, (ra, dec) in enumerate(targets)
                             if abs(s.heading_ra_deg-ra) < 1e-9 and abs(s.heading_dec_deg-dec) < 1e-9), -1 if selection else 3)
        with QtCore.QSignalBlocker(self.preset):
            self.preset.setCurrentIndex(preset_index)
        for widget, value in ((self.lock_check, s.camera_locked), (self.compare_button, p.comparison),
                              (self.color_check, s.doppler_colors), (self.brightness_check, s.illustrative_brightness),
                              (self.glow_check, s.glow), (self.labels_check, s.labels), (self.grid_check, p.grid)):
            with QtCore.QSignalBlocker(widget):
                widget.setChecked(value)
        with QtCore.QSignalBlocker(self.object_combo):
            target = self._current_named_target()
            index = (33 if target.object_kind=='solar_disk' else
                     next((i for i, item in enumerate(self.named_references) if item == target), -1)) if target else -1
            self.object_combo.setCurrentIndex(index)
        for widget,value in ((self.solar_ra_spin,solar.ra_deg),(self.solar_dec_spin,solar.dec_deg),
                             (self.solar_exposure_spin,solar.exposure_ev)):
            with QtCore.QSignalBlocker(widget):
                widget.setValue(value)
        for widget,value in ((self.solar_show_check,solar.enabled),(self.solar_track_check,solar.track_center),
                             (self.solar_radiometry_check,solar.radiometry_enabled),(self.solar_outline_check,solar.show_outline)):
            with QtCore.QSignalBlocker(widget):
                widget.setChecked(value)
        self.solar_scroll.setVisible(p.reference_target is not None and p.reference_target.object_kind=='solar_disk')

    def refresh(self):
        started = time.perf_counter()
        self._sync_widgets()
        self.panels = draw_figure(self.figure, self.catalog, self.view_state, self.presentation, self.catalog_title)
        scene = self.panels[-1]['scene']
        self.last_scene = scene
        self.canvas.draw_idle()
        self.metrics['gamma'].setText(f'{lorentz_factor(self.view_state.beta):.5g}')
        d = scene.doppler[scene.visible]
        self.metrics['doppler'].setText(f'{d.min():.3g} – {d.max():.3g}' if len(d) else '—')
        self.metrics['count'].setText(f'{scene.n_visible} / {self.catalog.n:,}')
        for key,value in self.pod_values.items():
            value.setText(f'{self.view_state.beta:.6f}' if key=='beta' else self.metrics[key].text())
        self.rail_speed_text.setText(f'β {self.view_state.beta:.7g} · γ {lorentz_factor(self.view_state.beta):.5g}')
        ra, dec = self.view_state.camera.radec
        self.camera_text.setText(f'Camera RA {ra:.4f}° · Dec {dec:.4f}°')
        note = f'β {self.view_state.beta:.9g}  ·  '
        if self.view_state.camera_locked:
            half = rest_frame_half_angle(self.view_state.hfov_deg/2, self.view_state.beta)
            note += f'Central half-angle {self.view_state.hfov_deg/2:g}° corresponds to {half:.2f}° in rest sky. '
        else:
            note += 'Camera independent of velocity. '
        if self._focus_fov_before is not None:
            note += f'16:9 angular viewport · FOV {self.view_state.hfov_deg:g}° × {self.view_state.vfov_deg:g}°. '
        if self.presentation.solar is not None and self.presentation.solar.enabled:
            note += ('Sol: fixed 1 AU; uniform 5772 K blackbody, per-ray Doppler radiance, fixed display exposure. '
                     if self.presentation.solar.radiometry_enabled else 'Sol: fixed 1 AU neutral geometry fill. ')
        self.scene_note.setText(note + 'Illustrative RGB / marker brightness; no travel or calibrated photometry.')
        self.source_text.setText(f'{self.catalog.n:,} objects · {self.catalog.metadata.coordinate_epoch}\nCompleteness unknown')
        self._update_inspector()
        self._render_count += 1
        self.last_render_ms = (time.perf_counter()-started)*1000
        if not self._fetching:
            self.statusBar().showMessage(f'{self.catalog_title}   ·   click an object to inspect   ·   {self.last_render_ms:.0f} ms')

    def _populate_objects(self):
        with QtCore.QSignalBlocker(self.object_combo):
            self.object_combo.clear()
            self.object_combo.addItems([target.name for target in self.named_references])
            self.object_combo.setCurrentIndex(-1)

    def select_row(self, row):
        if row is not None:
            self.view_state = center_object(self.catalog, self.view_state, row)
        self.presentation = replace(self.presentation, selected_row=row, reference_target=None)
        self._schedule()

    def _inspection_selection(self):
        if self.presentation.reference_target is not None:
            return self.presentation.reference_target.as_catalog(), 0, True
        if self.presentation.selected_row is not None:
            return self.catalog, self.presentation.selected_row, False
        return None

    def _current_named_target(self):
        if self.presentation.reference_target is not None:
            return self.presentation.reference_target
        row = self.presentation.selected_row
        if row is not None:
            target = ReferenceTarget.from_catalog(self.catalog, row)
            if target in self.named_references:
                return target
        return None

    def select_named_target(self, index):
        if not 0 <= index < len(self.named_references):
            return
        if index==33:
            settings=replace(self.presentation.solar or SolarSettings(),enabled=True,track_center=True)
            self.presentation=replace(self.presentation,selected_row=None,reference_target=solar_reference(settings),solar=settings)
            self._track_solar()
            self._schedule()
            return
        target = self.named_references[index]
        # An exact original demo row can use its existing selection highlight.
        # Never infer a Hipparcos match from name or proximity alone.
        if self.catalog.metadata == self.named_targets.metadata:
            for row in range(self.catalog.n):
                if ReferenceTarget.from_catalog(self.catalog, row) == target:
                    self.select_row(row)
                    return
        self.view_state = center_object(target.as_catalog(), self.view_state, 0)
        self.presentation = replace(self.presentation, selected_row=None, reference_target=target)
        self._schedule()

    def _track_solar(self):
        settings=self.presentation.solar
        target=self.presentation.reference_target
        if settings is not None and settings.track_center and target is not None and target.object_kind=='solar_disk':
            geometry=solar_geometry(settings,self.view_state)
            ra,dec=unit_to_radec(geometry['cap_center'])
            self.view_state=replace(self.view_state,camera_locked=False,camera=CameraPose.from_radec(ra,dec))

    def update_solar(self,**changes):
        settings=replace(self.presentation.solar or SolarSettings(),**changes)
        target=self.presentation.reference_target
        if target is not None and target.object_kind=='solar_disk':
            target=solar_reference(settings)
        self.presentation=replace(self.presentation,solar=settings,reference_target=target)
        if 'ra_deg' in changes or 'dec_deg' in changes or changes.get('track_center') is True:
            self._track_solar()
        self._schedule()

    def fit_solar_exposure(self):
        settings=self.presentation.solar or SolarSettings()
        geometry=solar_geometry(settings,self.view_state)
        self.update_solar(exposure_ev=fitted_exposure(geometry['doppler_max']))

    def apply_solar_direction(self):
        self.update_solar(ra_deg=self.solar_ra_spin.value(),dec_deg=self.solar_dec_spin.value())

    def frame_solar_disk(self):
        settings=replace(self.presentation.solar or SolarSettings(),enabled=True)
        self.presentation=replace(self.presentation,solar=settings,reference_target=solar_reference(settings),selected_row=None)
        geometry=solar_geometry(settings,self.view_state)
        ra,dec=unit_to_radec(geometry['cap_center'])
        self.view_state=replace(self.view_state,camera_locked=False,camera=CameraPose.from_radec(ra,dec))
        field=float(np.clip(3*math.degrees(2*geometry['radius_rad']),MIN_FOV,160.))
        self.change(hfov_deg=field,vfov_deg=field)

    def solar_heading(self,mode):
        settings=self.presentation.solar or SolarSettings()
        vector={'toward':settings.direction,'away':-settings.direction,
                'transverse':np.asarray(CameraPose.from_radec(settings.ra_deg,settings.dec_deg).east)}[mode]
        ra,dec=unit_to_radec(vector)
        self.view_state=self.view_state.with_lock(False).with_heading(ra,dec)
        self.update_solar(enabled=True,track_center=True)

    def _solar_inspector(self):
        settings=self.presentation.solar
        geometry=solar_geometry(settings,self.view_state)
        ra,dec=unit_to_radec(geometry['central_ray'])
        radiance=solar_radiance_summary(geometry,settings)
        cra,cdec=unit_to_radec(geometry['cap_center'])
        self.object_name.setText('Sol · our Sun')
        radius=math.degrees(geometry['radius_rad'])
        limit='<p>The disk covers at least half the sky; its complete limb cannot fit this front-hemisphere projection.</p>' if radius>=90 else ''
        self.object_details.setHtml(f'''<p style="color:#c8c8c8">FINITE SOLAR DISK · FIXED 1 AU MODEL</p>
<p>Observer distance: 1 AU ({AU_M:,.0f} m)<br>IAU nominal radius: {SOLAR_RADIUS_M/1000:,.0f} km</p>
<p><b>Rest angular diameter</b><br>{math.degrees(2*REST_RADIUS_RAD):.7f}°</p>
<p><b>Apparent limb-cone half-angle</b><br>{radius:.7g}°<br>Through-disk diameter: {2*radius:.7g}°</p>
<p><b>Solid angle</b><br>{geometry['solid_angle_sr']:.7g} sr<br>{geometry['solid_angle_sr']/(4*math.pi)*100:.5g}% of full sky<br>Area ratio to rest: {geometry['solid_angle_ratio']:.7g}</p>
<p><b>Central-ray Doppler factor</b><br>{geometry['central_doppler']:.8g}<br>Across disk: {geometry['doppler_min']:.7g} – {geometry['doppler_max']:.7g}</p>
<p>550 nm example → {550/geometry['central_doppler']:.7g} nm<br>Example wavelength, not a measured solar line.</p>
<p><b>Rest center</b><br>RA {settings.ra_deg:.6f}° · Dec {settings.dec_deg:.6f}°</p>
<p><b>Apparent central ray</b><br>RA {ra:.6f}° · Dec {dec:.6f}°<br><b>Apparent limb-circle center</b><br>RA {cra:.6f}° · Dec {cdec:.6f}°</p>
{limit}<p><b>Ideal blackbody radiance</b><br>Rest temperature: 5772 K<br>Central shifted temperature: {radiance['shifted_temperature_k']:.7g} K<br>Central bolometric surface radiance ratio (D⁴): {radiance['central_bolometric_radiance_ratio']:.7g}<br>Central visible Y ratio: {radiance['central_visible_y_ratio']:.7g}<br>Central model luminance: {radiance['central_luminance_cd_m2']:.7g} cd/m²</p>
<p>Per-ray spectrum Bλ(D × 5772 K); CIE 1931 2° observer. Uniform blackbody approximation; no absorption lines or limb darkening. These are surface-radiance values, not disk-integrated flux.</p>
<p>Display: {'fixed-exposure Doppler rendering' if settings.radiometry_enabled else 'legacy neutral geometry fill'}; {settings.exposure_ev:+.2f} EV. Tone mapping and sRGB gamut compression limit display brightness and color. Fit exposure is a one-time adjustment; subsequent speed changes retain it. Extremely redshifted visible light may remain black even at maximum exposure.</p>
<p>Exposure never resizes the physical disk. The optional outline and center cross are geometry annotations. Point-star RGB and D³ marker controls do not affect Sol.</p>
<p>Fixed teaching direction, not a dated ephemeris. Speed changes the instantaneous boost at the same 1 AU event; no trajectory, orbit, or changing distance is calculated.</p>''')

    def _update_inspector(self):
        selection = self._inspection_selection()
        if selection is None:
            self.object_name.setText('Choose an object')
            self.object_details.setHtml('<p>Select a star to see its rest and apparent directions, Doppler factor, and a wavelength example.</p>')
            return
        import html
        catalog, row, reference = selection
        if reference and self.presentation.reference_target.object_kind=='solar_disk':
            self._solar_inspector()
            return
        info = inspect_object(catalog, self.view_state, row)
        self.object_name.setText(info['name'])
        optional = lambda value, unit: f'{value:.4g} {unit}' if value is not None else 'Unknown'
        visible = not reference and row in self.panels[-1]['rows']
        status = 'NAMED REFERENCE TARGET' if reference else 'IN MOVING VIEW' if visible else 'OUTSIDE CURRENT SELECTION / FOV'
        if not reference and self.presentation.solar is not None and self.presentation.solar.enabled:
            from .solar import occulted_by_sol
            if occulted_by_sol(catalog.vectors[row:row+1],self.presentation.solar)[0]:
                status='OCCULTED BY SOL'
        provenance = ('Original demo coordinates and approximate values; frame/epoch unspecified. '
                      'Navigation reference, not an identified Hipparcos measurement.') if reference else catalog.metadata.source
        self.object_details.setHtml(f'''<p style="color:#c8c8c8">{status}</p>
<p>{html.escape(provenance)}</p>
<p><b>Rest direction</b><br>RA {info['rest_ra_deg']:.6f}°<br>Dec {info['rest_dec_deg']:.6f}°</p>
<p><b>Apparent direction</b><br>RA {info['apparent_ra_deg']:.6f}°<br>Dec {info['apparent_dec_deg']:.6f}°</p>
<p><b>Angle to velocity</b><br>Rest {info['rest_heading_angle_deg']:.4f}°<br>Apparent {info['apparent_heading_angle_deg']:.4f}°</p>
<p><b>Doppler factor</b><br><span style="color:#ededed;font-size:18pt">{info['doppler_factor']:.7g}</span></p>
<p><b>Example wavelength</b><br>550 nm → {info['shifted_wavelength_nm']:.4g} nm<br>Example only; not a measured line.</p>
<p>Rest V magnitude: {info['rest_vmag']:.3f}<br>Display proxy: {info['display_magnitude_proxy']:.3f}<br>B−V: {optional(info['bv'], '')}<br>Distance label: {optional(info['distance_pc'], 'pc')}</p>
<p>{html.escape(info['kind'])}. {'Unknown B−V uses 0.65 for display.' if info['bv'] is None else ''}
{'Extended-object point placeholder, not a stellar spectrum.' if info['kind'] != 'star' else ''}</p>''')

    def on_press(self, event):
        panel = next((p for p in self.panels if event.inaxes is p['ax']), None)
        if panel and event.button in (1, 3):
            self._drag = (event.x, event.y, self.view_state, panel, event.button)

    def on_motion(self, event):
        if self._drag is None or event.x is None or event.y is None:
            return
        x, y, state, panel, button = self._drag
        dx = (event.x-x) / max(panel['ax'].bbox.width, 1) * state.hfov_deg
        dy = (event.y-y) / max(panel['ax'].bbox.height, 1) * state.vfov_deg
        yaw, pitch = (dx, -dy) if button == 1 else (-dx, dy)
        self.view_state = self.view_state.with_camera(state.camera.rotated(yaw, pitch))
        self._schedule()

    def on_release(self, event):
        if self._drag is None:
            return
        x, y, state, panel, button = self._drag
        self._drag = None
        if event.x is None or event.y is None or math.hypot(event.x-x, event.y-y) > 5 or button != 1:
            return
        if panel['solar'] is not None and event.xdata is not None and event.ydata is not None:
            camera=panel['state'].camera
            ray=np.asarray(camera.forward)-math.tan(math.radians(event.xdata))*np.asarray(camera.east)+math.tan(math.radians(event.ydata))*np.asarray(camera.north)
            ray/=np.linalg.norm(ray)
            if ray@panel['solar']['cap_center']>=math.cos(panel['solar']['radius_rad']):
                self.select_named_target(33)
                return
        scene = panel['scene']
        xy = panel['ax'].transData.transform(np.column_stack((scene.x_deg[scene.visible], scene.y_deg[scene.visible])))
        if len(xy):
            distance = np.linalg.norm(xy-np.array([event.x, event.y]), axis=1)
            nearest = int(distance.argmin())
            if distance[nearest] < 18:
                self.select_row(int(panel['rows'][nearest]))

    def on_scroll(self, event):
        if event.inaxes:
            factor = .9 ** event.step
            self.change(hfov_deg=float(np.clip(self.view_state.hfov_deg*factor, MIN_FOV, 160)),
                        vfov_deg=float(np.clip(self.view_state.vfov_deg*factor, MIN_FOV, 160)))

    def turn(self, yaw, pitch):
        self.view_state = self.view_state.with_camera(self.view_state.camera.rotated(yaw, pitch))
        self._schedule()

    def apply_catalog(self, catalog, title):
        target = self._current_named_target()
        self._catalog_revision += 1
        self.catalog, self.catalog_title = catalog, str(title)
        self.presentation = replace(self.presentation, selected_row=None, reference_target=target)
        self._populate_objects()
        self._schedule()

    def restore_demo(self):
        self.apply_catalog(built_in_catalog(), 'Orion · inherited bright-star demo')

    def import_csv(self):
        path, _ = W.QFileDialog.getOpenFileName(self, 'Import catalog', '', 'CSV catalogs (*.csv)')
        if not path:
            return
        options = {}
        try:
            while True:
                try:
                    candidate = load_csv(path, **options)
                    break
                except UnitRequiredError as exc:
                    answer, ok = W.QInputDialog.getItem(self, 'Declare catalog units', str(exc), list(exc.choices), 0, False)
                    if not ok:
                        return
                    options[exc.keyword] = answer
            preview = candidate.import_report.summary() + '\n\nFirst accepted rows (RA°, Dec°, V):\n'
            preview += '\n'.join(f'{n}: {r:.5f}, {d:.5f}, {m:.3f}' for n, r, d, m in
                                  zip(candidate.name[:5], candidate.ra_deg[:5], candidate.dec_deg[:5], candidate.vmag[:5]))
            if W.QMessageBox.question(self, 'Catalog import preview', preview + '\n\nUse this catalog?') == W.QMessageBox.StandardButton.Yes:
                self.apply_catalog(candidate, Path(path).name)
        except Exception as exc:
            self.error('Catalog import failed', exc)

    def show_provenance(self):
        import json
        from dataclasses import asdict
        dialog = W.QDialog(self)
        dialog.setWindowTitle('Catalog provenance and import report')
        dialog.resize(650, 600)
        layout = W.QVBoxLayout(dialog)
        text = W.QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(json.dumps(asdict(self.catalog.metadata), indent=2, ensure_ascii=False) + '\n\n' +
                          (self.catalog.import_report.summary() if self.catalog.import_report else 'Inherited demo: no import report.'))
        layout.addWidget(text)
        layout.addWidget(self.button('Close', dialog.accept))
        dialog.exec()

    def load_hipparcos_library(self):
        try:
            catalog,info=catalog_cache.load_cached(minimum_limit=self.view_state.rest_mag_limit)
            self.apply_catalog(catalog,'Hipparcos · local library')
            self.statusBar().showMessage(f"Loaded {catalog.n:,} stars from verified local snapshot; no network request.")
        except (OSError,ValueError,KeyError,TypeError) as exc:
            self.catalog_startup_dialog(reason=str(exc))

    def catalog_startup_dialog(self,checked=False,*,reason=None):
        if self._fetching:return
        dialog=W.QDialog(self)
        dialog.setWindowTitle('Choose a sky catalog')
        dialog.setMinimumWidth(440)
        layout=W.QVBoxLayout(dialog)
        layout.addWidget(label('Choose a sky catalog','inspectorTitle'))
        info=None
        try:info=catalog_cache.cached_info()
        except (OSError,ValueError,KeyError,TypeError) as exc:reason=str(exc)
        if info:
            description=(f"A local Hipparcos snapshot is available: {info['accepted_rows']:,} accepted stars, "
                         f"{info['compressed_bytes']/1e6:.2f} MB. It can be loaded offline.")
        else:
            description=('No local Hipparcos copy is available. Download the six required main-catalog columns once, '
                         'then reuse the verified local snapshot offline. The 33-object demo is always available.')
        layout.addWidget(label(description,'muted',True))
        if reason:layout.addWidget(label(reason,'muted',True))
        remember=W.QCheckBox('Remember my choice for next launch')
        remember.setChecked(True)
        layout.addWidget(remember)
        actions=W.QDialogButtonBox()
        local=actions.addButton('Load local Hipparcos' if info else 'Download Hipparcos once',W.QDialogButtonBox.ButtonRole.AcceptRole)
        demo=actions.addButton('Use demo',W.QDialogButtonBox.ButtonRole.ActionRole)
        cancel=actions.addButton(W.QDialogButtonBox.StandardButton.Cancel)
        decision={'value':None}
        def choose(value):decision['value']=value;dialog.accept()
        local.clicked.connect(lambda:choose('hipparcos'))
        demo.clicked.connect(lambda:choose('demo'))
        cancel.clicked.connect(dialog.reject)
        layout.addWidget(actions)
        if dialog.exec()!=W.QDialog.DialogCode.Accepted:return
        choice=decision['value']
        if choice is None:return
        if choice=='demo':
            self.restore_demo()
            catalog_cache.set_startup_choice('demo' if remember.isChecked() else 'ask')
        elif info:
            try:
                catalog,loaded=catalog_cache.load_cached(minimum_limit=self.view_state.rest_mag_limit)
                self.apply_catalog(catalog,'Hipparcos · local library')
                catalog_cache.set_startup_choice('hipparcos' if remember.isChecked() else 'ask')
            except (OSError,ValueError,KeyError,TypeError) as exc:
                self.error('Local Hipparcos could not be loaded',str(exc)+'\nUse Download / refresh Hipparcos to create a new snapshot. The current catalog is unchanged.')
        else:
            # Remember only after a complete successful download and save.
            self.start_fetch(remember_startup=remember.isChecked())

    def catalog_on_startup(self):
        choice=catalog_cache.startup_choice()
        if choice=='demo':return
        if choice=='hipparcos':self.load_hipparcos_library()
        else:self.catalog_startup_dialog()

    def start_fetch(self,checked=False,*,remember_startup=None):
        if self._fetching:
            return
        limit = None  # Cache the complete six-column main table, filter V locally.
        revision = self._catalog_revision
        self._fetching = True
        self._remember_catalog_after_fetch=remember_startup
        for button in (self.fetch_button, self.import_button, self.demo_button):
            button.setEnabled(False)
        self.statusBar().showMessage('Downloading the Hipparcos main table and saving a local snapshot…')
        def worker():
            try:
                result=fetch_hipparcos(limit)
                catalog_cache.save_cached(result,server_vmag_limit=limit)
                self._messages.put((True, result, limit, revision))
            except Exception as exc:
                self._messages.put((False, str(exc), limit, revision))
        threading.Thread(target=worker, daemon=True).start()

    def poll_fetch(self):
        try:
            ok, result, limit, revision = self._messages.get_nowait()
        except queue.Empty:
            return
        self._fetching = False
        for button in (self.fetch_button, self.import_button, self.demo_button):
            button.setEnabled(True)
        if revision != self._catalog_revision:
            self.statusBar().showMessage('A newer catalog was opened; the earlier fetch result was discarded.')
            return
        if ok:
            self.apply_catalog(result,'Hipparcos · local library' if limit is None else f'Hipparcos · rest V < {limit:g}')
            remember=getattr(self,'_remember_catalog_after_fetch',None)
            if remember is not None:catalog_cache.set_startup_choice('hipparcos' if remember else 'ask')
            self.statusBar().showMessage(f'Hipparcos saved locally: {result.n:,} accepted stars. Next load works offline.')
        else:
            self.error('Hipparcos fetch failed', result)
            self.statusBar().showMessage('Fetch failed; previous catalog retained.')

    def open_scene(self):
        path, _ = W.QFileDialog.getOpenFileName(self, 'Open saved scene', '', 'Scene JSON (*.json)')
        if not path:
            return
        try:
            catalog, state, presentation, title = load_document(path)
            self.focus_sky(False)
            self._catalog_revision += 1
            self.catalog, self.view_state, self.presentation, self.catalog_title = catalog, state, presentation, title
            self._populate_objects()
            self._schedule()
        except Exception as exc:
            self.error('Could not open scene', exc)

    def save_scene(self):
        path, _ = W.QFileDialog.getSaveFileName(self, 'Save a new scene JSON', 'spaceship_scene.json', 'Scene JSON (*.json)')
        if not path:
            return
        try:
            save_document(path, self.catalog, self.view_state, self.presentation, self.catalog_title)
            self.statusBar().showMessage(f'Saved scene: {path}')
        except Exception as exc:
            self.error('Could not save scene (choose a new filename)', exc)

    def export_dialog(self):
        dialog = W.QDialog(self)
        dialog.setWindowTitle('Export the current scientific view')
        form = W.QFormLayout(dialog)
        form.addRow(label('PNG, SVG, PDF, numeric arrays, and a portable JSON scene.\nEach export creates a new versioned folder.', 'muted', True))
        sizes = W.QComboBox()
        sizes.addItems(['4K · 3840 × 2160', 'Full HD · 1920 × 1080', 'Square · 2400 × 2400'])
        stem = W.QLineEdit('spaceship_scene')
        form.addRow('Figure size', sizes)
        form.addRow('Folder name', stem)
        buttons = W.QDialogButtonBox(W.QDialogButtonBox.StandardButton.Ok | W.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() != W.QDialog.DialogCode.Accepted:
            return
        directory = W.QFileDialog.getExistingDirectory(self, 'Choose export parent folder')
        if not directory:
            return
        width, height = ((3840, 2160), (1920, 1080), (2400, 2400))[sizes.currentIndex()]
        W.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            folder = export_scene(directory, stem.text(), self.catalog, self.view_state, self.presentation,
                                  self.catalog_title, width=width, height=height)
            W.QMessageBox.information(self, 'Export complete', f'Saved figure formats, arrays, and JSON to:\n{folder}')
        except Exception as exc:
            self.error('Export failed', exc)
        finally:
            W.QApplication.restoreOverrideCursor()

    def error(self, title, error):
        W.QMessageBox.critical(self, title, str(error))

    def _update_settings(self):
        from .deployment import data_root, read_json
        path=data_root()/'update-settings.json'
        try:
            return read_json(path) if path.exists() else {}
        except (ValueError,OSError):
            return {}

    def _update_menu(self):
        menu=self.menuBar().addMenu('Application')
        menu.addAction('Catalog startup…', self.catalog_startup_dialog)
        menu.addAction('Load local Hipparcos', self.load_hipparcos_library)
        menu.addAction('Download / refresh Hipparcos…', self.start_fetch)
        menu.addSeparator()
        menu.addAction('Check for updates…', lambda: self.check_updates(automatic=False))
        menu.addAction('Roll back previous installed build…', self.queue_rollback)
        automatic=menu.addAction('Check for stable releases at startup')
        automatic.setCheckable(True)
        automatic.setChecked(self._update_settings().get('check_on_startup',True))
        automatic.setEnabled(bool(self.install_root))
        automatic.toggled.connect(self.set_automatic_updates)
        menu.addSeparator()
        menu.addAction('About and licenses…', self.about)
        self.update_notice=self.button('Update available…', self.show_available_update)
        self.update_notice.hide()
        self.statusBar().addPermanentWidget(self.update_notice)

    def set_automatic_updates(self, checked):
        from .deployment import data_root, atomic_json
        root=data_root()
        root.mkdir(parents=True,exist_ok=True)
        atomic_json(root/'update-settings.json',{'check_on_startup':bool(checked)})

    def check_updates(self, automatic=False):
        if self._checking_update or self._downloading_update:
            return
        self._checking_update=True
        def worker():
            try:
                from .deployment import latest_release
                self._update_messages.put(('check', latest_release(__version__), None, automatic))
            except Exception as exc:
                self._update_messages.put(('check', None, str(exc), automatic))
        threading.Thread(target=worker,daemon=True).start()

    def poll_updates(self):
        try:
            kind,result,error,automatic=self._update_messages.get_nowait()
        except queue.Empty:
            return
        if kind=='check':
            self._checking_update=False
            if error:
                if not automatic:
                    self.error('Could not check releases',error+'\nThe installed viewer is unchanged.')
                return
            if result is None:
                if not automatic:
                    W.QMessageBox.information(self,'Stable releases',f'Current version: {__version__}\nNo newer published Windows release is available.')
                return
            self.available_release=result
            self.update_notice.setText(f"Version {result['version']} available…")
            self.update_notice.show()
            if not automatic:
                self.show_available_update()
        else:
            self._downloading_update=False
            if error:
                self.error('Update was not activated',error+'\nThe current installed version is retained.')
            else:
                self.update_notice.hide()
                W.QMessageBox.information(self,'Update verified',
                    'The new build passed its startup and physics checks.\nClose the viewer when ready; it will be activated for the next launch.')

    def show_available_update(self):
        release=getattr(self,'available_release',None)
        if not release:
            self.check_updates(automatic=False)
            return
        dialog=W.QDialog(self)
        dialog.setWindowTitle('Stable release update')
        dialog.resize(600,450)
        layout=W.QVBoxLayout(dialog)
        layout.addWidget(label(f"Current {__version__} → Available {release['version']}",'inspectorTitle'))
        notes=W.QPlainTextEdit(release['notes'])
        notes.setReadOnly(True)
        layout.addWidget(notes)
        layout.addWidget(label('The verified update will be activated after this viewer closes.\nYour scenes and exports are kept separately.','muted',True))
        download=self.button('Download and install after closing',dialog.accept,primary=True)
        download.setEnabled(bool(self.install_root) and not self._downloading_update)
        layout.addWidget(download)
        if not self.install_root:
            layout.addWidget(label('This is a source/portable launch. Use the per-user setup to enable managed updates.','muted',True))
        layout.addWidget(self.button('Later',dialog.reject))
        if dialog.exec()!=W.QDialog.DialogCode.Accepted:
            return
        self._downloading_update=True
        self.statusBar().showMessage('Downloading and verifying update; the current view can stay open…')
        def worker():
            try:
                from .deployment import prepare_update
                slot=prepare_update(self.install_root,release)
                self._update_messages.put(('download',slot,None,False))
            except Exception as exc:
                self._update_messages.put(('download',None,str(exc),False))
        threading.Thread(target=worker,daemon=True).start()

    def queue_rollback(self):
        if not self.install_root:
            W.QMessageBox.information(self,'Rollback','Rollback is available for a managed per-user installation.')
            return
        try:
            from .deployment import active_state, queue_activation
            previous=active_state(self.install_root).get('previous')
            if not previous:
                raise ValueError('No previous installed build is available.')
            if W.QMessageBox.question(self,'Restore previous build','Activate the previous installed build after this viewer closes?')==W.QMessageBox.StandardButton.Yes:
                queue_activation(self.install_root,previous)
                W.QMessageBox.information(self,'Rollback queued','Close the viewer when ready. The previous build will be selected for the next launch.')
        except Exception as exc:
            self.error('Could not queue rollback',exc)

    def about(self):
        dialog=W.QDialog(self)
        dialog.setWindowTitle('About Relativistic Spaceship Viewer')
        layout=W.QVBoxLayout(dialog)
        layout.addWidget(label(f'Relativistic Spaceship Viewer {__version__}','inspectorTitle'))
        layout.addWidget(label('Special-relativistic directions, with illustrative color and marker brightness.\nNo calibrated photometry, travel, or uncertainty propagation.','muted',True))
        licenses=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]))/'licenses'
        if licenses.is_dir():
            layout.addWidget(self.button('Open bundled license notices',lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(licenses)))))
        layout.addWidget(label('Source: github.com/Fisicas/relativistic-spaceship-viewer\nMIT project license; bundled dependencies have their own licenses.','muted',True))
        layout.addWidget(self.button('Close',dialog.accept))
        dialog.exec()

    def closeEvent(self, event):
        self.render_timer.stop()
        self.fetch_timer.stop()
        self.update_timer.stop()
        super().closeEvent(event)


def main():
    app = W.QApplication.instance() or W.QApplication(sys.argv)
    app.setApplicationName('Relativistic Spaceship Viewer')
    app.setApplicationVersion(__version__)
    app.setStyle('Fusion')
    viewer = Viewer()
    viewer.show()
    QtCore.QTimer.singleShot(250,viewer.catalog_on_startup)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
