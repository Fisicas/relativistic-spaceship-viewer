# Selected visual direction

Direction C, Flight Display, with logo 1, Aberration Window. The control theme
uses neutral charcoal/black/gray, based on the user's desktop-interface reference.
It avoids the former blue/cyan chrome. The logo's cyan/amber remain restrained
accents; scientific source colors retain their independent model semantics.

`spaceship_viewer/assets/viewer_mark.svg` is a flat vector redraw of the selected
logo concept, with a monochrome companion. The asymmetric aperture, amber wedge,
and compressed-light marks avoid PSI Contact Atlas's central green dot/four-arm
crosshair structure. The SVG source is shared by app header/icon generation and
social artwork. `viewer.ico` includes 16, 20, 24, 32, 40, 48, 64, 128, and 256 px.
The original concept was generated with the built-in image-generation tool;
the inspectable production mark is vector artwork. Code/artwork are MIT, separate
from the CIE dataset license. This is visual differentiation, not a trademark search.

The social preview's sky is calculated by the existing core from the inherited
33-object catalog at γ=2. Its independent-atan2 map uses equal pixels per degree,
with the displayed H/V field matched to the panel aspect. The accompanying
`docs/branding/branding_provenance.json` records the complete state, source rows,
label selection, point-size mapping, and source hashes. It is not a generated
galaxy or an observed photograph; point colors and marker areas remain illustrative.

Regenerate assets into a **new** folder:

```powershell
& 'C:\Users\nelso\.venvs\codex-science-v1\Scripts\python.exe' -X utf8 .\tools\generate_branding.py --output-dir .\work\branding_v03
```

The production social PNG is 1280×640 and under 1 MB, with an opaque charcoal
background. The README references it directly. GitHub's **Settings → Social
preview** is separate: upload `docs/branding/social-preview.png` there when ready.
The user handles the push and upload; neither is performed automatically.
[GitHub's social-preview guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
describes these size and upload requirements.

The application bezel and side controls are ordinary Qt widgets outside the
Matplotlib sky map. They do not change aberration, Doppler values, occultation,
or solar radiance. In wide focused windows (at least 1600×820 logical pixels),
side readouts replace the top cards. Smaller windows and comparison views keep
the top cards. The long slider uses the same rapidity mapping as the sidebar.
No extra camera perspective or image stretching is introduced.
