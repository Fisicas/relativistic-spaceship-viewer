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
from .geometry import CameraPose
from .inspection import inspect_object
from .navigation import center_object, widescreen_fov, WIDESCREEN_RATIO
from .plotting import draw_figure, BACKGROUND
from .presentation import Presentation
from .relativity import MAX_BETA, lorentz_factor, rest_frame_half_angle
from .session import load_document, save_document
from .state import ViewState

STYLE = '''
QMainWindow, QWidget { background: #0e1623; color: #c8d7e8; font-family: 'Segoe UI'; font-size: 10pt; }
QWidget#header { background: #101c2c; border-bottom: 1px solid #26394f; }
QLabel { background: transparent; }
QLabel#brand { color: #ecf4fc; font-size: 16pt; font-weight: 600; }
QLabel#eyebrow { color: #6dd8ed; font-size: 9pt; font-weight: 600; }
QLabel#muted { color: #8299b4; font-size: 9pt; }
QLabel#metric { color: #eaf3ff; font-size: 19pt; font-weight: 500; }
QLabel#inspectorTitle { color: #eaf3ff; font-size: 17pt; font-weight: 500; }
QFrame#metricCard { background: #142033; border: 1px solid #24364d; border-radius: 7px; }
QGroupBox { border: 1px solid #27394f; border-radius: 7px; margin-top: 13px; padding: 12px 10px 9px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 11px; padding: 0px 5px; color: #74d9ed; }
QPushButton, QToolButton { background: #1a2b40; color: #dbe8f6; border: 1px solid #354b66; border-radius: 5px; padding: 7px 10px; }
QPushButton:hover, QToolButton:hover { background: #243f59; border-color: #74d9ed; }
QPushButton:pressed { background: #142d43; }
QPushButton:checked, QToolButton:checked { background: #16465a; border-color: #67cde5; }
QPushButton#primary { background: #7dd9eb; color: #082233; border: none; font-weight: 600; }
QPushButton:disabled { color: #60738b; border-color: #243447; }
QDoubleSpinBox, QSpinBox, QComboBox, QLineEdit { background: #09111e; color: #dce9f7; border: 1px solid #334963; border-radius: 4px; padding: 5px; min-height: 20px; }
QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus { border-color: #71cfe7; }
QCheckBox { spacing: 7px; padding: 3px 0; font-weight: 400; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #54718f; border-radius: 3px; background: #0a1220; }
QCheckBox::indicator:checked { background: #73d6e9; border-color: #73d6e9; }
QSlider::groove:horizontal { height: 4px; background: #263d56; border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -5px 0; border-radius: 6px; background: #8de1ed; }
QScrollArea { border: none; } QScrollBar:vertical { background: #0c1521; width: 9px; }
QScrollBar::handle:vertical { background: #334963; min-height: 30px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QSplitter::handle { background: #223249; width: 1px; }
QTabWidget::pane { border: none; } QTabBar::tab { padding: 9px 12px; color: #859eb8; }
QTabBar::tab:selected { color: #8addec; border-bottom: 2px solid #78d8ec; }
QPlainTextEdit, QTextBrowser { border: none; background: #0c1522; padding: 8px; color: #a9bdd4; }
QStatusBar { background: #0a1220; color: #8ea6c1; border-top: 1px solid #26394f; }
QMenuBar, QMenu { background: #121f30; color: #d1deec; } QMenu::item:selected { background: #25425c; }
QToolTip { background: #1d344b; color: #ecf7ff; border: 1px solid #64849d; }
'''


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
        icon = QtGui.QPixmap(64, 64)
        icon.fill(QtGui.QColor('#101c2c'))
        painter = QtGui.QPainter(icon)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setPen(QtGui.QPen(QtGui.QColor('#6dd8ed'), 2))
        painter.drawEllipse(13, 13, 38, 38)
        painter.drawLine(7, 32, 57, 32)
        painter.drawLine(32, 7, 32, 57)
        painter.setBrush(QtGui.QColor('#e8f8ff'))
        painter.drawEllipse(27, 27, 10, 10)
        painter.end()
        self.setWindowIcon(QtGui.QIcon(icon))
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
        brand = W.QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(label('RELATIVISTIC SPACESHIP VIEWER', 'brand'))
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
        self.hfov_spin, self.vfov_spin = spin(5., 160., 45., 1, 5.), spin(5., 160., 45., 1, 5.)
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
        self.fetch_button = self.button('Fetch Hipparcos', self.start_fetch)
        self.demo_button = self.button('Restore demo catalog', self.restore_demo)
        for button in (self.import_button, self.fetch_button, self.demo_button):
            source.addWidget(button)
        source.addWidget(self.button('Catalog provenance…', self.show_provenance))
        controls.addStretch()

        center = W.QWidget()
        central = W.QVBoxLayout(center)
        central.setContentsMargins(14, 14, 14, 7)
        central.setSpacing(10)
        metrics = W.QHBoxLayout()
        self.metrics = {}
        for title, key in (('LORENTZ FACTOR', 'gamma'), ('DOPPLER RANGE', 'doppler'), ('VISIBLE / LOADED', 'count')):
            card = W.QFrame()
            card.setObjectName('metricCard')
            card_layout = W.QVBoxLayout(card)
            card_layout.setContentsMargins(12, 9, 12, 9)
            card_layout.addWidget(label(title, 'muted'))
            value = label('—', 'metric')
            self.metrics[key] = value
            card_layout.addWidget(value)
            metrics.addWidget(card)
        central.addLayout(metrics)
        self.figure = Figure(figsize=(8., 7.), dpi=100, facecolor=BACKGROUND)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(320, 330)
        self.canvas.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        central.addWidget(self.canvas, 1)
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
        self.object_combo.setPlaceholderText('Select a catalog object')
        self.object_combo.activated.connect(lambda i: self.select_row(i if i >= 0 else None))
        inspect_layout.addWidget(self.object_combo)
        self.object_name = label('Choose an object', 'inspectorTitle', True)
        inspect_layout.addWidget(self.object_name)
        self.object_details = W.QTextBrowser()
        self.object_details.setOpenExternalLinks(False)
        inspect_layout.addWidget(self.object_details, 1)
        inspect_layout.addWidget(label('Selecting centers the moving view and unlocks the camera; velocity stays unchanged. Choose Custom in Heading & Camera to steer. The rest-magnitude cut still applies.', 'muted', True))
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
            self._schedule()
        elif index == 3 and self.presentation.selected_row is not None:
            row = self.presentation.selected_row
            # Rest catalog direction defines a velocity heading. A source
            # exactly along that heading remains centered under aberration.
            self.view_state = self.view_state.with_lock(False).with_heading(
                float(self.catalog.ra_deg[row]), float(self.catalog.dec_deg[row])).with_lock(True)
            self._schedule()

    def apply_heading(self):
        self.view_state = self.view_state.with_heading(self.ra_spin.value(), self.dec_spin.value())
        with QtCore.QSignalBlocker(self.preset):
            self.preset.setCurrentIndex(3)
        self._schedule()

    def set_lock(self, checked):
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
        settings = ((self.beta_spin, s.beta), (self.gamma_spin, lorentz_factor(s.beta)),
                    (self.speed_slider, round(math.atanh(s.beta) / math.atanh(MAX_BETA) * 10000)),
                    (self.ra_spin, s.heading_ra_deg), (self.dec_spin, s.heading_dec_deg),
                    (self.hfov_spin, s.hfov_deg), (self.vfov_spin, s.vfov_deg), (self.mag_spin, s.rest_mag_limit),
                    (self.marker_spin, p.marker_scale), (self.label_spin, p.max_labels))
        for widget, value in settings:
            with QtCore.QSignalBlocker(widget):
                widget.setValue(value)
        targets = ((84., -1.), (266.4168, -29.0078), (26.0170, -15.9375))
        row = p.selected_row
        self.preset.setItemText(3, f'Custom: {self.catalog.name[row]}' if row is not None else 'Custom heading')
        if row is not None:
            targets += ((float(self.catalog.ra_deg[row]), float(self.catalog.dec_deg[row])),)
        preset_index = next((i for i, (ra, dec) in enumerate(targets)
                             if abs(s.heading_ra_deg-ra) < 1e-9 and abs(s.heading_dec_deg-dec) < 1e-9), -1 if row is not None else 3)
        with QtCore.QSignalBlocker(self.preset):
            self.preset.setCurrentIndex(preset_index)
        for widget, value in ((self.lock_check, s.camera_locked), (self.compare_button, p.comparison),
                              (self.color_check, s.doppler_colors), (self.brightness_check, s.illustrative_brightness),
                              (self.glow_check, s.glow), (self.labels_check, s.labels), (self.grid_check, p.grid)):
            with QtCore.QSignalBlocker(widget):
                widget.setChecked(value)
        with QtCore.QSignalBlocker(self.object_combo):
            self.object_combo.setCurrentIndex(p.selected_row if p.selected_row is not None else -1)

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
            self.object_combo.addItems(self.catalog.name.tolist())
            self.object_combo.setCurrentIndex(-1)

    def select_row(self, row):
        if row is not None:
            self.view_state = center_object(self.catalog, self.view_state, row)
        self.presentation = replace(self.presentation, selected_row=row)
        self._schedule()

    def _update_inspector(self):
        row = self.presentation.selected_row
        if row is None:
            self.object_name.setText('Choose an object')
            self.object_details.setHtml('<p>Select a star to see its rest and apparent directions, Doppler factor, and a wavelength example.</p>')
            return
        import html
        info = inspect_object(self.catalog, self.view_state, row)
        self.object_name.setText(info['name'])
        optional = lambda value, unit: f'{value:.4g} {unit}' if value is not None else 'Unknown'
        visible = row in self.panels[-1]['rows']
        self.object_details.setHtml(f'''<p style="color:#78d6eb">{'IN MOVING VIEW' if visible else 'OUTSIDE CURRENT SELECTION / FOV'}</p>
<p><b>Rest direction</b><br>RA {info['rest_ra_deg']:.6f}°<br>Dec {info['rest_dec_deg']:.6f}°</p>
<p><b>Apparent direction</b><br>RA {info['apparent_ra_deg']:.6f}°<br>Dec {info['apparent_dec_deg']:.6f}°</p>
<p><b>Angle to velocity</b><br>Rest {info['rest_heading_angle_deg']:.4f}°<br>Apparent {info['apparent_heading_angle_deg']:.4f}°</p>
<p><b>Doppler factor</b><br><span style="color:#8ae3ef;font-size:18pt">{info['doppler_factor']:.7g}</span></p>
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
            self.change(hfov_deg=float(np.clip(self.view_state.hfov_deg*factor, 5, 160)),
                        vfov_deg=float(np.clip(self.view_state.vfov_deg*factor, 5, 160)))

    def turn(self, yaw, pitch):
        self.view_state = self.view_state.with_camera(self.view_state.camera.rotated(yaw, pitch))
        self._schedule()

    def apply_catalog(self, catalog, title):
        self._catalog_revision += 1
        self.catalog, self.catalog_title = catalog, str(title)
        self.presentation = replace(self.presentation, selected_row=None)
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

    def start_fetch(self):
        if self._fetching:
            return
        limit = self.view_state.rest_mag_limit
        revision = self._catalog_revision
        self._fetching = True
        for button in (self.fetch_button, self.import_button, self.demo_button):
            button.setEnabled(False)
        self.statusBar().showMessage(f'Fetching Hipparcos with rest V < {limit:g}…')
        def worker():
            try:
                self._messages.put((True, fetch_hipparcos(limit), limit, revision))
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
            self.apply_catalog(result, f'Hipparcos · rest V < {limit:g}')
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
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
