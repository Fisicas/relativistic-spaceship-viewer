"""
Relativistic Spaceship Viewer

A Tkinter + Matplotlib GUI for visualizing the apparent forward sky seen by an
observer moving at relativistic speed toward a selected direction.

Run:
    python relativistic_spaceship_viewer.py
"""

from __future__ import annotations

import csv
import math
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

APP_NAME = "Relativistic Spaceship Viewer"
APP_VERSION = "0.1.0"
HFOV_DEG = 45.0
VFOV_DEG = 45.0
ORION_RA_DEG = 84.0
ORION_DEC_DEG = -1.0
EPS = 1e-12


@dataclass
class StarCatalog:
    name: np.ndarray
    ra_deg: np.ndarray
    dec_deg: np.ndarray
    vmag: np.ndarray
    bv: np.ndarray
    distance_pc: np.ndarray

    @property
    def n(self) -> int:
        return len(self.name)

    @property
    def vectors(self) -> np.ndarray:
        return radec_to_unit(self.ra_deg, self.dec_deg)

    def limited(self, maglim: float) -> "StarCatalog":
        mask = self.vmag <= maglim
        return StarCatalog(self.name[mask], self.ra_deg[mask], self.dec_deg[mask],
                           self.vmag[mask], self.bv[mask], self.distance_pc[mask])


def radec_to_unit(ra_deg, dec_deg) -> np.ndarray:
    ra = np.deg2rad(ra_deg)
    dec = np.deg2rad(dec_deg)
    cd = np.cos(dec)
    return np.column_stack((cd * np.cos(ra), cd * np.sin(ra), np.sin(dec)))


def unit_to_radec(v: np.ndarray) -> tuple[float, float]:
    v = np.asarray(v, dtype=float)
    v = v / np.linalg.norm(v)
    ra = math.degrees(math.atan2(v[1], v[0])) % 360.0
    dec = math.degrees(math.asin(float(np.clip(v[2], -1.0, 1.0))))
    return ra, dec


def basis_from_radec(ra_deg: float, dec_deg: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    fwd = radec_to_unit(np.array([ra_deg]), np.array([dec_deg]))[0]
    ra = math.radians(ra_deg)
    east = np.array([-math.sin(ra), math.cos(ra), 0.0], dtype=float)
    east /= np.linalg.norm(east)
    north = np.cross(fwd, east)
    north /= np.linalg.norm(north)
    return fwd, east, north


def rotate_forward(fwd: np.ndarray, east: np.ndarray, north: np.ndarray,
                   yaw_deg: float, pitch_deg: float) -> np.ndarray:
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    new_fwd = math.cos(pitch) * (math.cos(yaw) * fwd + math.sin(yaw) * east) + math.sin(pitch) * north
    return new_fwd / np.linalg.norm(new_fwd)


def aberrate(vectors: np.ndarray, forward: np.ndarray, beta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    beta = float(np.clip(beta, 0.0, 0.999999))
    gamma = 1.0 / math.sqrt(max(1.0 - beta * beta, EPS))
    mu = vectors @ forward
    denom = np.maximum(1.0 + beta * mu, EPS)
    parallel_prime = ((mu + beta) / denom)[:, None] * forward[None, :]
    perp = vectors - mu[:, None] * forward[None, :]
    perp_prime = perp / (gamma * denom)[:, None]
    apparent = parallel_prime + perp_prime
    apparent /= np.linalg.norm(apparent, axis=1)[:, None]
    doppler = gamma * denom
    return apparent, doppler, mu


def bv_to_temperature(bv):
    bv = np.nan_to_num(np.asarray(bv, dtype=float), nan=0.65, posinf=0.65, neginf=0.65)
    bv = np.clip(bv, -0.40, 2.20)
    return 4600.0 * (1.0 / (0.92 * bv + 1.7) + 1.0 / (0.92 * bv + 0.62))


def temperature_to_rgb(temp_k):
    t = np.atleast_1d(np.asarray(temp_k, dtype=float))
    t = np.clip(np.nan_to_num(t, nan=5800.0, posinf=40000.0, neginf=1000.0), 1000.0, 40000.0) / 100.0
    r = np.empty_like(t); g = np.empty_like(t); b = np.empty_like(t)
    low = t <= 66.0; high = ~low
    r[low] = 255.0
    g[low] = 99.4708025861 * np.log(np.maximum(t[low], 1.0)) - 161.1195681661
    b[low] = np.where(t[low] <= 19.0, 0.0,
                      138.5177312231 * np.log(np.maximum(t[low] - 10.0, 1.0)) - 305.0447927307)
    r[high] = 329.698727446 * np.power(t[high] - 60.0, -0.1332047592)
    g[high] = 288.1221695283 * np.power(t[high] - 60.0, -0.0755148492)
    b[high] = 255.0
    return np.clip(np.column_stack((r, g, b)) / 255.0, 0.0, 1.0)


def display_mag(vmag: np.ndarray, doppler: np.ndarray, enabled: bool) -> np.ndarray:
    if not enabled:
        return vmag.copy()
    return vmag - 2.5 * 3.0 * np.log10(np.maximum(doppler, 1e-9))


def marker_sizes(mag_eff: np.ndarray) -> np.ndarray:
    sizes = 28.0 * 10.0 ** (-0.4 * (mag_eff - 1.0))
    return np.clip(sizes, 0.35, 260.0)


def built_in_catalog() -> StarCatalog:
    # RA/Dec in degrees; visual magnitudes, approximate B-V, and approximate distances in parsecs.
    rows = [
        ("Betelgeuse", 88.7929, 7.4071, 0.42, 1.85, 168),
        ("Rigel", 78.6345, -8.2016, 0.13, -0.03, 264),
        ("Bellatrix", 81.2828, 6.3497, 1.64, -0.22, 77),
        ("Mintaka", 83.0017, -0.2991, 2.23, -0.20, 380),
        ("Alnilam", 84.0534, -1.2019, 1.69, -0.18, 606),
        ("Alnitak", 85.1897, -1.9426, 1.74, -0.20, 387),
        ("Saiph", 86.9391, -9.6696, 2.06, -0.18, 198),
        ("Meissa", 83.7845, 9.9342, 3.39, -0.22, 340),
        ("Orion Nebula/M42", 83.8221, -5.3911, 4.0, 0.0, 414),
        ("Aldebaran", 68.9802, 16.5093, 0.86, 1.54, 20),
        ("Elnath", 81.5729, 28.6075, 1.65, -0.13, 41),
        ("Alhena", 99.4279, 16.3993, 1.93, 0.0, 34),
        ("Sirius", 101.2872, -16.7161, -1.46, 0.0, 2.6),
        ("Wezen", 107.0979, -26.3932, 1.83, 0.67, 492),
        ("Adhara", 104.6564, -28.9721, 1.50, -0.21, 132),
        ("Procyon", 114.8255, 5.2250, 0.34, 0.42, 3.5),
        ("Pollux", 116.3290, 28.0262, 1.14, 1.00, 10.3),
        ("Castor", 113.6500, 31.8883, 1.58, 0.03, 15.6),
        ("Capella", 79.1723, 45.9980, 0.08, 0.80, 13),
        ("Menkalinan", 89.8822, 44.9474, 1.90, 0.00, 25),
        ("Mirfak", 51.0807, 49.8612, 1.79, 0.48, 155),
        ("Regulus", 152.0929, 11.9672, 1.36, -0.11, 24),
        ("Canopus", 95.9879, -52.6957, -0.74, 0.15, 95),
        ("Avior", 125.6285, -59.5095, 1.86, 1.22, 190),
        ("Achernar", 24.4286, -57.2368, 0.46, -0.16, 43),
        ("Tau Ceti", 26.0170, -15.9375, 3.50, 0.72, 3.65),
        ("Vega", 279.2347, 38.7837, 0.03, 0.00, 7.7),
        ("Arcturus", 213.9153, 19.1824, -0.05, 1.23, 11.3),
        ("Alpha Centauri", 219.9021, -60.8339, -0.27, 0.71, 1.34),
        ("Polaris", 37.9546, 89.2641, 1.98, 0.60, 137),
        ("Antares", 247.3519, -26.4320, 1.06, 1.83, 170),
        ("Spica", 201.2983, -11.1614, 0.98, -0.23, 77),
        ("Fomalhaut", 344.4128, -29.6222, 1.16, 0.09, 7.7),
    ]
    return StarCatalog(*(np.array(col) for col in zip(*rows)))


def load_csv(path: str) -> StarCatalog:
    names=[]; ras=[]; decs=[]; mags=[]; bvs=[]; dists=[]
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row.")
        lower = {c.lower().strip(): c for c in reader.fieldnames}
        def col(*choices):
            for c in choices:
                if c in lower:
                    return lower[c]
            return None
        ra_c = col("ra_deg", "ra", "raj2000")
        dec_c = col("dec_deg", "dec", "dej2000")
        mag_c = col("mag", "vmag", "v_mag", "v")
        bv_c = col("bv", "b-v", "ci", "color_index")
        name_c = col("name", "proper", "hip", "id")
        dist_c = col("distance_pc", "dist", "distance", "parallax")
        if not ra_c or not dec_c or not mag_c:
            raise ValueError("CSV must contain RA, Dec, and magnitude columns.")
        raw_ra=[]
        for i,row in enumerate(reader):
            try:
                ra=float(row[ra_c]); dec=float(row[dec_c]); mag=float(row[mag_c])
            except Exception:
                continue
            raw_ra.append(ra); ras.append(ra); decs.append(dec); mags.append(mag)
            bvs.append(float(row[bv_c]) if bv_c and row.get(bv_c,"").strip() else 0.65)
            dists.append(float(row[dist_c]) if dist_c and row.get(dist_c,"").strip() else np.nan)
            names.append(row[name_c].strip() if name_c and row.get(name_c,"").strip() else f"star {i+1}")
    if not names:
        raise ValueError("No usable rows found.")
    ras = np.array(ras, dtype=float)
    if np.nanmax(np.abs(ras)) <= 24.0:
        ras *= 15.0
    return StarCatalog(np.array(names, dtype=object), ras % 360.0, np.array(decs, dtype=float),
                       np.array(mags, dtype=float), np.array(bvs, dtype=float), np.array(dists, dtype=float))


def fetch_hipparcos(max_vmag: float = 8.0) -> StarCatalog:
    from astroquery.vizier import Vizier
    v = Vizier(columns=["HIP", "RAICRS", "DEICRS", "Vmag", "B-V", "Plx"], row_limit=-1)
    result = v.query_constraints(catalog="I/239/hip_main", Vmag=f"<{max_vmag}")
    if not result:
        raise RuntimeError("No Hipparcos result returned by VizieR.")
    tab = result[0]
    ra = np.array(tab["RAICRS"], dtype=float)
    dec = np.array(tab["DEICRS"], dtype=float)
    mag = np.array(tab["Vmag"], dtype=float)
    bv = np.array(tab["B-V"], dtype=float)
    hip = np.array(tab["HIP"], dtype=object)
    plx = np.array(tab["Plx"], dtype=float)  # milliarcsec
    dist = np.where(plx > 0, 1000.0 / plx, np.nan)
    names = np.array([f"HIP {h}" for h in hip], dtype=object)
    return StarCatalog(names, ra, dec, mag, bv, dist)


class Viewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x760")
        self.catalog = built_in_catalog()
        self.catalog_title = "Built-in bright-star demo catalog"
        self.drag_button = None
        self.drag_x = None
        self.drag_y = None
        self.drag_basis = None
        self._build_ui()
        self.update_plot()

    def _build_ui(self):
        self.columnconfigure(1, weight=1); self.rowconfigure(0, weight=1)
        panel = ttk.Frame(self, padding=8); panel.grid(row=0, column=0, sticky="ns")
        ttk.Label(panel, text="Relativistic Driver's Seat", font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 12))

        self.beta_var = tk.DoubleVar(value=0.0)
        ttk.Label(panel, text="Velocity β = v/c").pack(anchor="w")
        ttk.Scale(panel, from_=0.0, to=0.999, variable=self.beta_var, command=lambda _ : self.update_plot()).pack(fill="x")
        self.beta_label = ttk.Label(panel); self.beta_label.pack(anchor="w", pady=(2, 12))

        ttk.Label(panel, text=f"Windshield FOV: {HFOV_DEG:.0f}° × {VFOV_DEG:.0f}°").pack(anchor="w")
        ttk.Label(panel, text="Left-drag: grab/pan. Right-drag: rotate/yaw-pitch.", wraplength=290).pack(anchor="w", pady=(4, 12))

        self.maglim_var = tk.DoubleVar(value=8.0)
        ttk.Label(panel, text="Catalog magnitude limit shown").pack(anchor="w")
        ttk.Scale(panel, from_=0.0, to=10.0, variable=self.maglim_var, command=lambda _ : self.update_plot()).pack(fill="x")
        self.maglim_label = ttk.Label(panel); self.maglim_label.pack(anchor="w", pady=(2, 12))

        ttk.Separator(panel).pack(fill="x", pady=10)
        ttk.Label(panel, text="Forward direction").pack(anchor="w")
        grid = ttk.Frame(panel); grid.pack(anchor="w")
        ttk.Label(grid, text="RA deg").grid(row=0, column=0, sticky="w")
        ttk.Label(grid, text="Dec deg").grid(row=0, column=1, sticky="w")
        self.ra_var = tk.DoubleVar(value=ORION_RA_DEG)
        self.dec_var = tk.DoubleVar(value=ORION_DEC_DEG)
        ttk.Entry(grid, textvariable=self.ra_var, width=9).grid(row=1, column=0, padx=(0,6))
        ttk.Entry(grid, textvariable=self.dec_var, width=9).grid(row=1, column=1, padx=(0,6))
        ttk.Button(grid, text="Apply", command=self.update_plot).grid(row=1, column=2)
        btns = ttk.Frame(panel); btns.pack(anchor="w", pady=6)
        ttk.Button(btns, text="Orion", command=lambda: self.set_target(ORION_RA_DEG, ORION_DEC_DEG)).grid(row=0, column=0, padx=(0,6))
        ttk.Button(btns, text="Galactic Center", command=lambda: self.set_target(266.4168, -29.0078)).grid(row=0, column=1, padx=(0,6))
        ttk.Button(btns, text="Tau Ceti", command=lambda: self.set_target(26.0170, -15.9375)).grid(row=0, column=2)

        ttk.Separator(panel).pack(fill="x", pady=10)
        self.doppler_color_var = tk.BooleanVar(value=True)
        self.doppler_bright_var = tk.BooleanVar(value=True)
        self.labels_var = tk.BooleanVar(value=True)
        self.glow_var = tk.BooleanVar(value=True)
        for label, var in [("Doppler blue/red shift colors", self.doppler_color_var),
                           ("Doppler brightness boost/dimming", self.doppler_bright_var),
                           ("Label brightest visible stars", self.labels_var),
                           ("Soft star glow", self.glow_var)]:
            ttk.Checkbutton(panel, text=label, variable=var, command=self.update_plot).pack(anchor="w")

        ttk.Separator(panel).pack(fill="x", pady=10)
        ttk.Label(panel, text="Catalog").pack(anchor="w")
        ttk.Button(panel, text="Load CSV catalog...", command=self.load_csv_dialog).pack(fill="x", pady=2)
        ttk.Button(panel, text="Fetch Hipparcos via VizieR", command=self.fetch_hipparcos_dialog).pack(fill="x", pady=2)
        ttk.Button(panel, text="Use built-in demo catalog", command=self.use_builtin).pack(fill="x", pady=2)
        self.status = ttk.Label(panel, text="", wraplength=300, justify="left")
        self.status.pack(anchor="w", pady=(14, 0))

        fig = Figure(figsize=(8.8, 7.0), dpi=100, facecolor="black")
        self.ax = fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew")
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_motion)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)

    def set_target(self, ra, dec):
        self.ra_var.set(round(float(ra), 6)); self.dec_var.set(round(float(dec), 6)); self.update_plot()

    def use_builtin(self):
        self.catalog = built_in_catalog(); self.catalog_title = "Built-in bright-star demo catalog"; self.update_plot()

    def load_csv_dialog(self):
        path = filedialog.askopenfilename(title="Load star catalog CSV", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path: return
        try:
            self.catalog = load_csv(path)
            self.catalog_title = Path(path).name
            self.update_plot()
        except Exception as exc:
            messagebox.showerror("Could not load catalog", str(exc))

    def fetch_hipparcos_dialog(self):
        max_vmag = float(self.maglim_var.get())
        self.status.configure(text=f"Fetching Hipparcos stars with Vmag < {max_vmag:.1f}…")
        def worker():
            try:
                cat = fetch_hipparcos(max_vmag)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("Hipparcos fetch failed", str(exc)))
                self.after(0, self.update_plot)
                return
            def done():
                self.catalog = cat
                self.catalog_title = f"Hipparcos via VizieR, Vmag < {max_vmag:.1f}"
                self.update_plot()
            self.after(0, done)
        threading.Thread(target=worker, daemon=True).start()

    def on_mouse_press(self, event):
        if event.inaxes is not self.ax or event.button not in (1, 3): return
        self.drag_button = event.button; self.drag_x = event.x; self.drag_y = event.y
        self.drag_basis = basis_from_radec(float(self.ra_var.get()) % 360.0, float(self.dec_var.get()))
        self.canvas.get_tk_widget().configure(cursor="fleur" if event.button == 1 else "exchange")

    def on_mouse_motion(self, event):
        if self.drag_button is None or self.drag_basis is None or event.x is None or event.y is None: return
        width = max(self.canvas.get_tk_widget().winfo_width(), 1)
        height = max(self.canvas.get_tk_widget().winfo_height(), 1)
        dx_deg = (event.x - self.drag_x) / width * HFOV_DEG
        dy_deg = (event.y - self.drag_y) / height * VFOV_DEG
        if self.drag_button == 1:
            yaw_deg, pitch_deg = dx_deg, -dy_deg
        else:
            yaw_deg, pitch_deg = -dx_deg, dy_deg
        fwd, east, north = self.drag_basis
        new_fwd = rotate_forward(fwd, east, north, yaw_deg, pitch_deg)
        ra, dec = unit_to_radec(new_fwd)
        self.ra_var.set(round(ra, 6)); self.dec_var.set(round(dec, 6)); self.update_plot()

    def on_mouse_release(self, event):
        self.drag_button = None; self.drag_x = None; self.drag_y = None; self.drag_basis = None
        self.canvas.get_tk_widget().configure(cursor="")

    def update_plot(self):
        beta = float(np.clip(self.beta_var.get(), 0.0, 0.999))
        gamma = 1.0 / math.sqrt(max(1.0 - beta * beta, EPS))
        maglim = float(self.maglim_var.get())
        ra0 = float(self.ra_var.get()) % 360.0
        dec0 = float(np.clip(self.dec_var.get(), -89.999, 89.999))
        self.beta_label.configure(text=f"β = {beta:.6f}     γ = {gamma:.3f}")
        self.maglim_label.configure(text=f"rest-frame magnitude limit = {maglim:.1f}")

        cat = self.catalog.limited(maglim)
        fwd, east, north = basis_from_radec(ra0, dec0)
        apparent, doppler, _ = aberrate(cat.vectors, fwd, beta)
        z = apparent @ fwd
        x = -np.rad2deg(np.arctan2(apparent @ east, z))
        y = np.rad2deg(np.arctan2(apparent @ north, z))
        visible = (z > 0) & (np.abs(x) <= HFOV_DEG/2) & (np.abs(y) <= VFOV_DEG/2)
        xv, yv = x[visible], y[visible]
        dopv = doppler[visible]
        magv = cat.vmag[visible]
        bvv = cat.bv[visible]
        namev = cat.name[visible]
        distv = cat.distance_pc[visible]
        mag_eff = display_mag(magv, dopv, self.doppler_bright_var.get())
        sizes = marker_sizes(mag_eff)
        temp = bv_to_temperature(bvv)
        if self.doppler_color_var.get():
            temp = temp * dopv
        colors = temperature_to_rgb(temp)

        self.ax.clear(); self.ax.set_facecolor("black")
        for spine in self.ax.spines.values(): spine.set_color("0.35")
        self.ax.tick_params(colors="0.65")
        self.ax.xaxis.label.set_color("0.75"); self.ax.yaxis.label.set_color("0.75"); self.ax.title.set_color("0.9")
        if len(xv):
            if self.glow_var.get():
                self.ax.scatter(xv, yv, s=np.clip(sizes*4.5, 2, 900), c=colors, alpha=0.10, linewidths=0)
                self.ax.scatter(xv, yv, s=np.clip(sizes*2.0, 1, 500), c=colors, alpha=0.18, linewidths=0)
            self.ax.scatter(xv, yv, s=sizes, c=colors, alpha=0.95, linewidths=0)
            if self.labels_var.get():
                for i in np.argsort(mag_eff)[:min(24, len(mag_eff))]:
                    if sizes[i] < 1.0: continue
                    d = f" ({distv[i]:.0f} pc)" if np.isfinite(distv[i]) else ""
                    self.ax.text(xv[i]+0.35, yv[i]+0.35, f"{namev[i]}{d}", color="0.82", fontsize=8, alpha=0.85)
        self.ax.set_xlim(-HFOV_DEG/2, HFOV_DEG/2); self.ax.set_ylim(-VFOV_DEG/2, VFOV_DEG/2)
        self.ax.set_aspect("equal", adjustable="box")
        self.ax.grid(color="0.18", linewidth=0.5, alpha=0.5)
        self.ax.set_xlabel("apparent horizontal angle from center, degrees  (right = celestial west)")
        self.ax.set_ylabel("apparent vertical angle from center, degrees")
        self.ax.set_title(f"Forward view toward RA {ra0:.2f}°, Dec {dec0:.2f}°  |  {self.catalog_title}", fontsize=11)

        alpha_ship = math.radians(HFOV_DEG / 2.0)
        cos_edge = (math.cos(alpha_ship) - beta) / max(1.0 - beta * math.cos(alpha_ship), EPS)
        rest_half = math.degrees(math.acos(float(np.clip(cos_edge, -1.0, 1.0))))
        min_d = float(np.nanmin(dopv)) if len(dopv) else float("nan")
        max_d = float(np.nanmax(dopv)) if len(dopv) else float("nan")
        self.status.configure(text=(f"Catalog stars loaded: {self.catalog.n:,}\n"
                                    f"Stars plotted: {len(xv):,}\n"
                                    f"A {HFOV_DEG/2:.1f}° ship-frame half-angle corresponds to {rest_half:.1f}° in the rest sky at this β.\n"
                                    f"Doppler factor among plotted stars: {min_d:.3g} to {max_d:.3g}."))
        self.canvas.draw_idle()


def main():
    Viewer().mainloop()


if __name__ == "__main__":
    main()
