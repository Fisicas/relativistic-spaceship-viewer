"""Compatibility Tk GUI; the Qt redesign is a later, separate milestone."""
from __future__ import annotations

from dataclasses import replace
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import __version__
from .catalog import load_csv, UnitRequiredError, fetch_hipparcos
from .demo_catalog import built_in_catalog
from .geometry import finite_scalar
from .relativity import lorentz_factor, rest_frame_half_angle
from .rendering import draw_scene
from .scene import compute_scene
from .state import ViewState

APP_NAME = "Relativistic Spaceship Viewer"
APP_VERSION = __version__
HFOV_DEG = VFOV_DEG = 45.
ORION_RA_DEG, ORION_DEC_DEG = 84., -1.
GUI_MAX_BETA = .999  # retained slider range; core is tested to .999999


class Viewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1180x760")
        self.catalog = built_in_catalog()
        self.catalog_title = "Built-in bright-star demo catalog"
        self.view_state = ViewState()
        self.drag_state = None
        self.drag_button = None
        self._closed = False
        self._fetching = False
        self._messages = queue.Queue()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_id = self.after(100, self._poll_fetch)
        self.update_plot()

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        # A scrollable sidebar keeps existing controls reachable after adding the
        # camera lock and provenance text, including on smaller Windows displays.
        sidebar = ttk.Frame(self)
        sidebar.grid(row=0, column=0, sticky="ns")
        scroll_canvas = tk.Canvas(sidebar, width=365, highlightthickness=0)
        scroll_canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(sidebar, orient="vertical", command=scroll_canvas.yview)
        scrollbar.pack(side="right", fill="y")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        panel = ttk.Frame(scroll_canvas, padding=8)
        scroll_canvas.create_window((0, 0), window=panel, anchor="nw")
        panel.bind("<Configure>", lambda _: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        ttk.Label(panel, text="Relativistic Driver's Seat", font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 12))

        self.beta_var = tk.DoubleVar(value=0.)
        ttk.Label(panel, text="Velocity β = v/c").pack(anchor="w")
        ttk.Scale(panel, from_=0., to=GUI_MAX_BETA, variable=self.beta_var, command=lambda _: self.update_plot()).pack(fill="x")
        self.beta_label = ttk.Label(panel)
        self.beta_label.pack(anchor="w", pady=(2, 12))
        ttk.Label(panel, text="Windshield angular-axis FOV: 45° × 45°").pack(anchor="w")
        ttk.Label(panel, text="Left-drag: grab/pan. Right-drag: yaw/pitch.\nLocked: steer ship. Unlocked: look around.", wraplength=340).pack(anchor="w", pady=(4, 12))

        self.maglim_var = tk.DoubleVar(value=8.)
        ttk.Label(panel, text="Rest-frame catalog V magnitude limit").pack(anchor="w")
        ttk.Scale(panel, from_=0., to=10., variable=self.maglim_var, command=lambda _: self.update_plot()).pack(fill="x")
        self.maglim_label = ttk.Label(panel)
        self.maglim_label.pack(anchor="w", pady=(2, 12))
        ttk.Separator(panel).pack(fill="x", pady=10)
        ttk.Label(panel, text="Velocity heading (catalog rest-frame axes)").pack(anchor="w")
        grid = ttk.Frame(panel)
        grid.pack(anchor="w")
        ttk.Label(grid, text="RA deg").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Dec deg").grid(row=0, column=1, sticky="w")
        self.ra_var, self.dec_var = tk.DoubleVar(value=84.), tk.DoubleVar(value=-1.)
        ttk.Entry(grid, textvariable=self.ra_var, width=9).grid(row=1, column=0, padx=(0, 6))
        ttk.Entry(grid, textvariable=self.dec_var, width=9).grid(row=1, column=1, padx=(0, 6))
        ttk.Button(grid, text="Apply", command=self.apply_heading).grid(row=1, column=2)
        btns = ttk.Frame(panel)
        btns.pack(anchor="w", pady=6)
        for col, (name, ra, dec) in enumerate((("Orion", 84., -1.), ("Galactic Center", 266.4168, -29.0078), ("Tau Ceti", 26.0170, -15.9375))):
            ttk.Button(btns, text=name, command=lambda ra=ra, dec=dec: self.set_target(ra, dec)).grid(row=0, column=col, padx=(0, 6))
        self.lock_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(panel, text="Lock camera to velocity heading", variable=self.lock_var, command=self.toggle_lock).pack(anchor="w")
        self.camera_label = ttk.Label(panel)
        self.camera_label.pack(anchor="w")

        ttk.Separator(panel).pack(fill="x", pady=10)
        self.doppler_color_var = tk.BooleanVar(value=True)
        self.doppler_bright_var = tk.BooleanVar(value=True)
        self.labels_var = tk.BooleanVar(value=True)
        self.glow_var = tk.BooleanVar(value=True)
        for label, var in (("Doppler colors (approximate RGB)", self.doppler_color_var),
                           ("Illustrative D³ brightness mapping", self.doppler_bright_var),
                           ("Label brightest visible objects", self.labels_var),
                           ("Soft glow (presentation only)", self.glow_var)):
            ttk.Checkbutton(panel, text=label, variable=var, command=self.update_plot).pack(anchor="w")
        ttk.Separator(panel).pack(fill="x", pady=10)
        ttk.Label(panel, text="Catalog").pack(anchor="w")
        ttk.Button(panel, text="Load CSV catalog...", command=self.load_csv_dialog).pack(fill="x", pady=2)
        self.fetch_button = ttk.Button(panel, text="Fetch Hipparcos via VizieR", command=self.fetch_hipparcos_dialog)
        self.fetch_button.pack(fill="x", pady=2)
        ttk.Button(panel, text="Use built-in demo catalog", command=self.use_builtin).pack(fill="x", pady=2)
        self.status = ttk.Label(panel, text="", wraplength=340, justify="left")
        self.status.pack(anchor="w", pady=(14, 0))
        fig = Figure(figsize=(8.8, 7.), dpi=100, facecolor="black")
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew")
        for event, handler in (("button_press_event", self.on_mouse_press),
                               ("motion_notify_event", self.on_mouse_motion),
                               ("button_release_event", self.on_mouse_release)):
            self.canvas.mpl_connect(event, handler)

    def _sync_heading_fields(self):
        self.ra_var.set(self.view_state.heading_ra_deg)
        self.dec_var.set(self.view_state.heading_dec_deg)

    def apply_heading(self):
        try:
            self.view_state = self.view_state.with_heading(self.ra_var.get(), self.dec_var.get())
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid velocity heading", str(exc), parent=self)
            return
        self._sync_heading_fields()
        self.update_plot()

    def set_target(self, ra, dec):
        self.view_state = self.view_state.with_heading(ra, dec)
        self._sync_heading_fields()
        self.update_plot()

    def toggle_lock(self):
        self.view_state = self.view_state.with_lock(self.lock_var.get())
        self.update_plot()

    def use_builtin(self):
        if self._fetching:
            return
        self.catalog = built_in_catalog()
        self.catalog_title = "Built-in bright-star demo catalog"
        self.update_plot()

    def load_csv_dialog(self):
        if self._fetching:
            return
        path = filedialog.askopenfilename(title="Load star catalog CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        options = {}
        try:
            while True:
                try:
                    candidate = load_csv(path, **options)
                    break
                except UnitRequiredError as exc:
                    answer = simpledialog.askstring("Declare catalog units", f"{exc}\nEnter one of: {', '.join(exc.choices)}", parent=self)
                    if answer is None:
                        return
                    options[exc.keyword] = answer.strip().lower()
            preview = candidate.import_report.summary()
            preview += "\n\nFirst accepted rows (RA deg, Dec deg, V mag):\n"
            preview += "\n".join(f"{name}: {ra:.6f}, {dec:.6f}, {mag:.3f}" for name, ra, dec, mag in
                                  zip(candidate.name[:5], candidate.ra_deg[:5], candidate.dec_deg[:5], candidate.vmag[:5]))
            preview += f"\n\nFrame: {candidate.metadata.coordinate_frame}; epoch: {candidate.metadata.coordinate_epoch}.\n\nUse this catalog?"
            if not messagebox.askyesno("Catalog import preview", preview, parent=self):
                return
            self.catalog, self.catalog_title = candidate, Path(path).name
            self.update_plot()
        except Exception as exc:
            messagebox.showerror("Could not load catalog", str(exc), parent=self)

    def fetch_hipparcos_dialog(self):
        if self._fetching:
            return
        max_vmag = float(self.maglim_var.get())
        self._fetching = True
        self.fetch_button.configure(state="disabled")
        self.status.configure(text=f"Fetching Hipparcos stars with rest Vmag < {max_vmag:.1f}…")

        def worker():
            # Worker never calls Tk: errors and results are passed to the main
            # event loop, including exceptions whose local name is cleared.
            try:
                self._messages.put((True, fetch_hipparcos(max_vmag), max_vmag))
            except Exception as exc:
                self._messages.put((False, str(exc), max_vmag))
        threading.Thread(target=worker, daemon=True).start()

    def _poll_fetch(self):
        if self._closed:
            return
        try:
            ok, result, max_vmag = self._messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self._fetching = False
            self.fetch_button.configure(state="normal")
            if ok:
                self.catalog = result
                self.catalog_title = f"Hipparcos via VizieR, rest Vmag < {max_vmag:.1f}"
            else:
                messagebox.showerror("Hipparcos fetch failed", result, parent=self)
            self.update_plot()
        self._poll_id = self.after(100, self._poll_fetch)

    def on_mouse_press(self, event):
        if event.inaxes is not self.ax or event.button not in (1, 3):
            return
        self.drag_button, self.drag_x, self.drag_y = event.button, event.x, event.y
        self.drag_state = self.view_state
        self.canvas.get_tk_widget().configure(cursor="fleur" if event.button == 1 else "exchange")

    def on_mouse_motion(self, event):
        if self.drag_button is None or self.drag_state is None or event.x is None or event.y is None:
            return
        width, height = max(self.ax.bbox.width, 1), max(self.ax.bbox.height, 1)
        dx = (event.x - self.drag_x) / width * self.view_state.hfov_deg
        dy = (event.y - self.drag_y) / height * self.view_state.vfov_deg
        yaw, pitch = (dx, -dy) if self.drag_button == 1 else (-dx, dy)
        camera = self.drag_state.camera.rotated(yaw, pitch)
        # Use current display settings; only camera/heading are inherited from
        # the drag-start pose. Preserve triad roll through pole crossings.
        self.view_state = self.view_state.with_camera(camera)
        self._sync_heading_fields()
        self.update_plot()

    def on_mouse_release(self, event):
        self.drag_button = self.drag_state = None
        self.canvas.get_tk_widget().configure(cursor="")

    def update_plot(self):
        try:
            beta = finite_scalar(self.beta_var.get(), "beta")
            if not 0 <= beta <= GUI_MAX_BETA:
                raise ValueError(f"GUI beta must be in [0, {GUI_MAX_BETA}].")
            self.view_state = replace(self.view_state, beta=beta, rest_mag_limit=self.maglim_var.get(),
                                      doppler_colors=self.doppler_color_var.get(),
                                      illustrative_brightness=self.doppler_bright_var.get(),
                                      labels=self.labels_var.get(), glow=self.glow_var.get())
            scene = compute_scene(self.catalog, self.view_state)
        except (ValueError, tk.TclError) as exc:
            self.status.configure(text=f"Invalid setting: {exc}")
            return
        self.last_scene = scene
        state = self.view_state
        self.beta_label.configure(text=f"β = {state.beta:.6f}     γ = {lorentz_factor(state.beta):.3f}")
        self.maglim_label.configure(text=f"rest-frame V magnitude limit = {state.rest_mag_limit:.1f}")
        camera_ra, camera_dec = state.camera.radec
        self.camera_label.configure(text=f"Camera: RA {camera_ra:.3f}°, Dec {camera_dec:.3f}°")
        draw_scene(self.ax, scene, state, self.catalog_title)
        dop = scene.doppler[scene.visible]
        dop_text = f"{dop.min():.3g} to {dop.max():.3g}" if len(dop) else "none (no visible objects)"
        if state.camera_locked:
            rest_half = rest_frame_half_angle(state.hfov_deg / 2., state.beta)
            cone_text = f"Central horizontal half-angle {state.hfov_deg / 2.:.1f}° corresponds to {rest_half:.1f}° in rest sky."
        else:
            cone_text = "Camera is independent of velocity; centered-cone half-angle summary does not apply."
        missing_bv = int(np.isnan(scene.candidates.bv[scene.visible]).sum())
        extended = int(np.sum(scene.candidates.object_kind[scene.visible] != "star"))
        self.status.configure(text=(f"Catalog objects loaded: {self.catalog.n:,}\nObjects plotted: {scene.n_visible:,}\n"
                                    f"{cone_text}\nDoppler factor: {dop_text}.\n"
                                    f"Frame: {self.catalog.metadata.coordinate_frame}; epoch: {self.catalog.metadata.coordinate_epoch}.\n"
                                    f"Unknown B−V displayed using 0.65: {missing_bv}. Extended demo point markers: {extended}.\n"
                                    "Colors and D³ brightness are illustrative; rest V cut is not apparent detectability.\n"
                                    "Distances are labels; no travel or uncertainty propagation. Catalog completeness is not certified."))
        self.canvas.draw_idle()

    def close(self):
        self._closed = True
        self.after_cancel(self._poll_id)
        self.destroy()


def main():
    Viewer().mainloop()
