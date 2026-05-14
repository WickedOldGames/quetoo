# muzzle-fu

Visual muzzle-position editor for Quetoo weapon models.

Loads a weapon `.obj`, renders it in a plain 3-D view, and lets you place
a crosshair at the exact barrel tip in model space.  The confirmed position
is written back into `link.cfg` and `view.cfg` next to the `.obj` as a
`muzzle "x y z"` line.

## Setup

Uses the shared virtual environment at the repo root (same as mat-fu /
normalmap-fu):

```bash
# from repo root — only needed once
python3 -m venv venv
source venv/bin/activate
pip install pygame PyOpenGL PyOpenGL_accelerate
```

## Running

```bash
# from repo root
venv/bin/python3 src/tools/muzzle-fu/muzzle-fu.py \
    ~/Coding/quetoo-data/target/default/models/weapons/blaster/tris.obj
```

## Controls

| Input | Action |
|---|---|
| Left mouse drag | Orbit camera |
| Scroll wheel | Dolly in / out |
| ← → | Move muzzle along X |
| ↑ ↓ | Move muzzle along Y (barrel depth) |
| Q / E | Move muzzle along Z (Quake Z-up) |
| Shift | 10× coarser step |
| S | Save to `link.cfg` + `view.cfg` |
| R | Reset muzzle to model centroid |
| Escape | Quit |

The saved line looks like:

```
muzzle "7.6900 25.9800 0.0000"
```

This value is in model/object space, before any cfg `translate` or `scale`
is applied, so the same value is correct for both first-person (view.cfg)
and third-person (link.cfg) rendering.
