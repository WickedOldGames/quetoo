#!/usr/bin/env python3
# Run with the repo-root venv:  ../../venv/bin/python3 muzzle-fu.py <tris.obj>
"""
muzzle-fu: Visual muzzle position editor for Quetoo weapon models.

Usage:
    python3 muzzle-fu.py path/to/models/weapons/blaster/tris.obj

Controls:
    Left mouse drag   Orbit camera
    Mouse wheel       Dolly camera in/out
    Arrow Left/Right  Move muzzle along X axis
    Arrow Up/Down     Move muzzle along Y axis (barrel depth)
    Q / E             Move muzzle along Z axis (Quake Z-up)
    Shift             10x coarser step
    S                 Save muzzle to link.cfg and view.cfg
    R                 Reset muzzle to model centroid
    Escape            Quit
"""

import math
import os
import sys

import pygame
from pygame.locals import DOUBLEBUF, KEYDOWN, MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION, MOUSEWHEEL, OPENGL, QUIT
from OpenGL.GL import (GL_AMBIENT, GL_AMBIENT_AND_DIFFUSE, GL_BLEND, GL_COLOR_BUFFER_BIT,
                       GL_COLOR_MATERIAL, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST,
                       GL_DIFFUSE, GL_FRONT_AND_BACK, GL_LIGHT0, GL_LIGHTING,
                       GL_LINEAR, GL_LINES, GL_MODELVIEW, GL_ONE_MINUS_SRC_ALPHA,
                       GL_PROJECTION, GL_QUADS, GL_RGBA, GL_SRC_ALPHA,
                       GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
                       GL_TRIANGLES, GL_UNSIGNED_BYTE, glBegin, glBindTexture, glBlendFunc,
                       glClear, glClearColor, glColor3f, glColorMaterial, glDeleteTextures,
                       glDisable, glEnable, glEnd, glGenTextures, glLightfv, glLineWidth,
                       glLoadIdentity, glMatrixMode, glNormal3f, glOrtho, glPopMatrix,
                       glPushMatrix, glTexCoord2f, glTexImage2D, glTexParameteri,
                       glVertex2f, glVertex3f)
from OpenGL.GLU import gluLookAt, gluPerspective


# ---------------------------------------------------------------------------
# OBJ loader
# ---------------------------------------------------------------------------

def load_obj(path):
    """Parse an OBJ file, returning (verts, triangles)."""
    verts = []
    tris = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('v '):
                _, x, y, z = line.split()
                verts.append((float(x), float(y), float(z)))
            elif line.startswith('f '):
                parts = line.split()[1:]
                # Each token may be v, v/vt, or v/vt/vn — we only need v
                indices = [int(p.split('/')[0]) - 1 for p in parts]
                # Fan-triangulate polygons
                for i in range(1, len(indices) - 1):
                    tris.append((indices[0], indices[i], indices[i + 1]))

    return verts, tris


def compute_face_normals(verts, tris):
    normals = []
    for a, b, c in tris:
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        ex, ey, ez = bx - ax, by - ay, bz - az
        fx, fy, fz = cx - ax, cy - ay, cz - az
        nx = ey * fz - ez * fy
        ny = ez * fx - ex * fz
        nz = ex * fy - ey * fx
        length = math.sqrt(nx * nx + ny * ny + nz * nz)
        if length > 0:
            normals.append((nx / length, ny / length, nz / length))
        else:
            normals.append((0.0, 0.0, 1.0))
    return normals


def model_bounds(verts):
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return ((min(xs), max(xs)),
            (min(ys), max(ys)),
            (min(zs), max(zs)))


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def draw_model(verts, tris, normals):
    glBegin(GL_TRIANGLES)
    for i, (a, b, c) in enumerate(tris):
        glNormal3f(*normals[i])
        glVertex3f(*verts[a])
        glVertex3f(*verts[b])
        glVertex3f(*verts[c])
    glEnd()


def draw_crosshair(pos, size):
    """Draw a three-axis crosshair at `pos` with arm length `size`."""
    x, y, z = pos
    glDisable(GL_LIGHTING)
    glLineWidth(2.5)

    glColor3f(1.0, 0.15, 0.0)       # X — red
    glBegin(GL_LINES)
    glVertex3f(x - size, y, z);  glVertex3f(x + size, y, z)
    glEnd()

    glColor3f(0.1, 1.0, 0.1)        # Y — green
    glBegin(GL_LINES)
    glVertex3f(x, y - size, z);  glVertex3f(x, y + size, z)
    glEnd()

    glColor3f(0.2, 0.5, 1.0)        # Z — blue  (Quake up)
    glBegin(GL_LINES)
    glVertex3f(x, y, z - size);  glVertex3f(x, y, z + size)
    glEnd()

    glEnable(GL_LIGHTING)
    glLineWidth(1.0)


def draw_axes(extent):
    """Draw small world-space XYZ axis lines at the origin."""
    s = extent * 0.15
    glDisable(GL_LIGHTING)
    glLineWidth(1.5)
    glBegin(GL_LINES)
    glColor3f(1.0, 0.3, 0.3);  glVertex3f(0, 0, 0);  glVertex3f(s, 0, 0)   # X
    glColor3f(0.3, 1.0, 0.3);  glVertex3f(0, 0, 0);  glVertex3f(0, s, 0)   # Y
    glColor3f(0.3, 0.5, 1.0);  glVertex3f(0, 0, 0);  glVertex3f(0, 0, s)   # Z
    glEnd()
    glLineWidth(1.0)
    glEnable(GL_LIGHTING)


def draw_text(font, text, x, y, W, H, color=(255, 215, 50)):
    """Draw text at (x, y) from the top-left corner using an ortho overlay."""
    surf = font.render(text, True, color)
    tw, th = surf.get_size()
    # pygame surfaces are top-down; OpenGL textures expect bottom-up — flip.
    data = pygame.image.tostring(pygame.transform.flip(surf, False, True), "RGBA", False)

    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, tw, th, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)

    glMatrixMode(GL_PROJECTION); glPushMatrix(); glLoadIdentity()
    glOrtho(0, W, 0, H, -1, 1)
    glMatrixMode(GL_MODELVIEW);  glPushMatrix(); glLoadIdentity()

    glDisable(GL_LIGHTING); glDisable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D); glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor3f(1.0, 1.0, 1.0)

    # Convert y-from-top-left → y-from-bottom-left
    yy = H - y - th
    glBegin(GL_QUADS)
    glTexCoord2f(0, 0); glVertex2f(x,      yy)
    glTexCoord2f(1, 0); glVertex2f(x + tw, yy)
    glTexCoord2f(1, 1); glVertex2f(x + tw, yy + th)
    glTexCoord2f(0, 1); glVertex2f(x,      yy + th)
    glEnd()

    glBindTexture(GL_TEXTURE_2D, 0)
    glDeleteTextures([tex])
    glDisable(GL_TEXTURE_2D); glDisable(GL_BLEND)
    glEnable(GL_DEPTH_TEST); glEnable(GL_LIGHTING)
    glMatrixMode(GL_PROJECTION); glPopMatrix()
    glMatrixMode(GL_MODELVIEW);  glPopMatrix()


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def obj_to_quetoo(pos):
    """Apply the same Y/Z swap the engine uses when loading .obj files:
       Vec3(x, z, y)  — so Quetoo model-space == what the cfg must store."""
    return [pos[0], pos[2], pos[1]]

# The swap is its own inverse.
quetoo_to_obj = obj_to_quetoo



def read_cfg(path):
    """Read cfg lines, stripping any existing muzzle entry."""
    if not os.path.exists(path):
        return []
    with open(path) as f:
        lines = f.readlines()
    return [l for l in lines if not l.strip().startswith('muzzle')]


def save_muzzle(obj_path, pos_obj):
    """Append / replace `muzzle` in link.cfg and view.cfg next to the obj.
       pos_obj is in OBJ space; we save in Quetoo space (Y/Z swapped)."""
    model_dir = os.path.dirname(obj_path)
    qt = obj_to_quetoo(pos_obj)
    line = f'muzzle "{qt[0]:.0f} {qt[1]:.0f} {qt[2]:.0f}"\n'

    saved = []
    for cfg_name in ('link.cfg', 'view.cfg'):
        cfg_path = os.path.join(model_dir, cfg_name)
        lines = read_cfg(cfg_path)
        lines.append(line)
        with open(cfg_path, 'w') as f:
            f.writelines(lines)
        saved.append(cfg_path)

    print(f'muzzle "{qt[0]:.0f} {qt[1]:.0f} {qt[2]:.0f}"  (Quetoo space)')
    print(f'  → written to: {", ".join(saved)}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    obj_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(obj_path):
        print(f'File not found: {obj_path}')
        sys.exit(1)

    print(f'Loading {obj_path} ...')
    verts, tris = load_obj(obj_path)
    normals = compute_face_normals(verts, tris)
    print(f'  {len(verts)} vertices, {len(tris)} triangles')

    (minx, maxx), (miny, maxy), (minz, maxz) = model_bounds(verts)
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    cz = (minz + maxz) / 2.0
    extent = max(maxx - minx, maxy - miny, maxz - minz)

    # Check for an existing muzzle entry in link.cfg (stored in Quetoo space)
    muzzle = [cx, cy, cz]
    link_cfg = os.path.join(os.path.dirname(obj_path), 'link.cfg')
    if os.path.exists(link_cfg):
        import re
        with open(link_cfg) as f:
            for ln in f:
                m = re.match(r'\s*muzzle\s+"([^"]+)"', ln)
                if m:
                    vals = list(map(float, m.group(1).split()))
                    if len(vals) == 3:
                        muzzle = [round(v) for v in quetoo_to_obj(vals)]
                        print(f'  Loaded existing muzzle from link.cfg: {vals} (Quetoo) → {muzzle} (OBJ)')

    # -----------------------------------------------------------------------
    # Pygame / OpenGL init
    # -----------------------------------------------------------------------
    pygame.init()
    pygame.key.set_repeat(400, 30)  # delay_ms, interval_ms
    W, H = 1280, 800
    pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
    model_name = os.path.basename(os.path.dirname(obj_path))
    pygame.display.set_caption(f'muzzle-fu  ·  {model_name}')

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  [0.85, 0.85, 0.85, 1.0])
    glLightfv(GL_LIGHT0, GL_AMBIENT,  [0.30, 0.30, 0.30, 1.0])

    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, W / H, extent * 0.01, extent * 50.0)
    glMatrixMode(GL_MODELVIEW)

    font_big  = pygame.font.SysFont('menlo', 20, bold=True)
    font_small = pygame.font.SysFont('menlo', 16)

    # -----------------------------------------------------------------------
    # Camera state  (orbit around model centre, Quake Z-up)
    # -----------------------------------------------------------------------
    cam_theta = 45.0       # horizontal angle (degrees)
    cam_phi   = 20.0       # elevation angle  (degrees, clamped ±89)
    cam_dist  = extent * 2.2

    orbiting    = False
    last_mouse  = (0, 0)

    # Muzzle nudge step — 1 unit fine, 5 units coarse; always rounded to integer
    STEP_FINE   = 1.0
    STEP_COARSE = 5.0

    status_msg  = ''
    clock = pygame.time.Clock()

    # -----------------------------------------------------------------------
    # Main loop
    # -----------------------------------------------------------------------
    running = True
    while running:

        for event in pygame.event.get():

            if event.type == QUIT:
                running = False

            elif event.type == KEYDOWN:
                key  = event.key
                mods = pygame.key.get_mods()
                step = STEP_COARSE if (mods & pygame.KMOD_SHIFT) else STEP_FINE

                if key == pygame.K_ESCAPE:
                    running = False

                elif key == pygame.K_LEFT:
                    muzzle[0] += step
                elif key == pygame.K_RIGHT:
                    muzzle[0] -= step
                elif key == pygame.K_DOWN:
                    muzzle[2] -= step        # OBJ Z = Quetoo Y
                elif key == pygame.K_UP:
                    muzzle[2] += step        # OBJ Z = Quetoo Y
                elif key in (pygame.K_q, pygame.K_PAGEDOWN):
                    muzzle[1] += step        # OBJ Y = Quetoo Z (barrel depth)
                elif key in (pygame.K_e, pygame.K_PAGEUP):
                    muzzle[1] -= step        # OBJ Y = Quetoo Z (barrel depth)
                elif key == pygame.K_r:
                    muzzle = [round(cx), round(cy), round(cz)]
                    status_msg = 'Muzzle reset to centroid'
                elif key == pygame.K_s:
                    save_muzzle(obj_path, muzzle)
                    status_msg = f'Saved  →  link.cfg / view.cfg'

                muzzle = [round(v) for v in muzzle]

            # ---- camera orbit (left mouse drag) ---------------------------
            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                orbiting   = True
                last_mouse = event.pos

            elif event.type == MOUSEBUTTONUP and event.button == 1:
                orbiting = False

            elif event.type == MOUSEMOTION and orbiting:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                cam_theta += dx * 0.4
                cam_phi   += dy * 0.4   # unclamped — full vertical orbit
                last_mouse = event.pos

            # ---- camera dolly (scroll wheel) ------------------------------
            elif event.type == MOUSEWHEEL:
                cam_dist = max(extent * 0.1,
                               cam_dist - event.y * extent * 0.08)

        # -------------------------------------------------------------------
        # Draw 3D scene
        # -------------------------------------------------------------------
        glClearColor(0.12, 0.13, 0.16, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        # Position camera on a sphere around the model centre (Z-up)
        rad_t = math.radians(cam_theta)
        rad_p = math.radians(cam_phi)
        eye_x = cx + cam_dist * math.cos(rad_p) * math.sin(rad_t)
        eye_y = cy + cam_dist * math.cos(rad_p) * math.cos(rad_t)
        eye_z = cz + cam_dist * math.sin(rad_p)
        # Flip up vector when past the top/bottom pole to avoid gimbal flip
        phi_mod = cam_phi % 360
        up_z = -1.0 if 90.0 < phi_mod < 270.0 else 1.0
        gluLookAt(eye_x, eye_y, eye_z,
                  cx, cy, cz,
                  0.0, 0.0, up_z)

        # Move the light with the camera so the model is always lit
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.85, 0.85, 0.85, 1.0])

        draw_axes(extent)

        glColor3f(0.55, 0.65, 0.78)
        draw_model(verts, tris, normals)

        draw_crosshair(muzzle, size=extent * 0.035)

        # -------------------------------------------------------------------
        # 2D overlay  (muzzle coords + help)
        # -------------------------------------------------------------------
        qt = obj_to_quetoo(muzzle)
        draw_text(font_big,
                  f'muzzle  x:{qt[0]:+.0f}  y:{qt[1]:+.0f}  z:{qt[2]:+.0f}  (Quetoo space)',
                  12, 10, W, H)

        help_lines = [
            '← → : X      ↑ ↓ : Y      Q/E : Z (barrel)      Shift : ×10',
            'Drag : orbit      Scroll : dolly      S : save      R : reset',
        ]
        for i, txt in enumerate(help_lines):
            draw_text(font_small, txt, 12, H - 14 - (i + 1) * 22, W, H,
                      color=(170, 170, 170))

        if status_msg:
            draw_text(font_small, status_msg, 12, 42, W, H,
                      color=(100, 255, 130))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
