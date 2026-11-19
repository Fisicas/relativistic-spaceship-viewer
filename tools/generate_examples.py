"""Regenerate high-resolution Orion examples from portable scene configurations.

Use a new output directory. --write-docs copies complete bundles into a new
docs/images/v02 directory and refuses to replace an earlier generation.
"""
from pathlib import Path
import argparse
import json
import math
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from spaceship_viewer.demo_catalog import built_in_catalog
from spaceship_viewer.exporting import export_scene
from spaceship_viewer.presentation import Presentation
from spaceship_viewer.state import ViewState


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--write-docs', action='store_true')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    catalog = built_in_catalog()
    examples = []
    for stem, beta in (('orion_rest', 0.), ('orion_beta030', .3), ('orion_gamma2', math.sqrt(3)/2)):
        folder = export_scene(args.output_dir, stem, catalog, ViewState(beta=beta), Presentation(max_labels=16),
                              'Orion · inherited bright-star demo', width=3840, height=3840, dpi=480, formats=('png', 'svg'))
        examples.append(folder.name)
    folder = export_scene(args.output_dir, 'orion_comparison', catalog, ViewState(beta=math.sqrt(3)/2),
                          Presentation(comparison=True, max_labels=16), 'Orion · rest and moving observers')
    examples.append(folder.name)
    (args.output_dir / 'examples_index.json').write_text(json.dumps({'examples': examples, 'single_dimensions': [3840, 3840],
        'comparison_dimensions': [3840, 2160],
        'settings': 'Each scene.json is a portable full-catalog snapshot, not an external CSV reference.'}, indent=2), encoding='utf-8')
    if args.write_docs:
        destination = ROOT / 'docs' / 'images' / 'v02'
        shutil.copytree(args.output_dir, destination)  # refuses existing destination
    print(json.dumps({'output': str(args.output_dir.resolve()), 'examples': examples}, indent=2))


if __name__ == '__main__':
    main()
