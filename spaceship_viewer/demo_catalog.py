"""Inherited demo values, unchanged from commit 0f4d46a."""
import numpy as np
from .catalog import StarCatalog, CatalogMetadata


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
    kinds = np.array(['extended_demo' if row[0] == 'Orion Nebula/M42' else 'star' for row in rows])
    metadata = CatalogMetadata(source='Inherited 0.1.0 built-in 33-object demo catalog',
                               notes=('Approximate inherited values; original measurement citations, coordinate frame, and epoch unspecified.',
                                      'M42 is an extended-object placeholder rendered as an illustrative point marker.',
                                      'Catalog is sparse and not complete at any magnitude limit; distances are labels only.'))
    return StarCatalog(*(np.array(col) for col in zip(*rows)), metadata=metadata, object_kind=kinds)
