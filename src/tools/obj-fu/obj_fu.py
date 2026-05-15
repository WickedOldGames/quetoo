#!/usr/bin/env python3
"""Simple OBJ viewer with Quetoo-style `usemtl` texture path resolution."""

import argparse
import math
from pathlib import Path

import pygame
from OpenGL.GL import (
  GL_COLOR_BUFFER_BIT,
  GL_DEPTH_BUFFER_BIT,
  GL_DEPTH_TEST,
  GL_LINEAR,
  GL_MODELVIEW,
  GL_PROJECTION,
  GL_TEXTURE_2D,
  GL_TEXTURE_MAG_FILTER,
  GL_TEXTURE_MIN_FILTER,
  GL_TRIANGLES,
  GL_RGBA,
  GL_UNSIGNED_BYTE,
  glBegin,
  glBindTexture,
  glClear,
  glClearColor,
  glDisable,
  glEnable,
  glEnd,
  glGenTextures,
  glLoadIdentity,
  glMatrixMode,
  glTexCoord2f,
  glTexImage2D,
  glTexParameteri,
  glVertex3f,
)
from OpenGL.GLU import gluLookAt, gluPerspective
from pygame.locals import DOUBLEBUF, MOUSEBUTTONDOWN, MOUSEBUTTONUP, MOUSEMOTION, MOUSEWHEEL, OPENGL, QUIT


def obj_to_quake_space(v: tuple[float, float, float]) -> tuple[float, float, float]:
  # Match Quetoo R_LoadMeshModel OBJ axis transform: (x, z, y)
  return (v[0], v[2], v[1])


def load_obj(path: Path):
  verts: list[tuple[float, float, float]] = []
  texcoords: list[tuple[float, float]] = []
  faces_by_mtl: dict[str, list[list[tuple[int, int | None]]]] = {}
  current_mtl = ""

  with path.open() as f:
    for raw in f:
      line = raw.strip()
      if not line or line.startswith("#"):
        continue
      if line.startswith("v "):
        _, x, y, z = line.split()[:4]
        verts.append(obj_to_quake_space((float(x), float(y), float(z))))
      elif line.startswith("vt "):
        parts = line.split()
        texcoords.append((float(parts[1]), float(parts[2])))
      elif line.startswith("usemtl "):
        current_mtl = line[7:].strip()
      elif line.startswith("f "):
        tokens = line.split()[1:]
        poly: list[tuple[int, int | None]] = []
        for tok in tokens:
          parts = tok.split("/")
          vi = int(parts[0]) - 1
          ti = int(parts[1]) - 1 if len(parts) > 1 and parts[1] else None
          poly.append((vi, ti))
        if len(poly) >= 3:
          faces_by_mtl.setdefault(current_mtl, [])
          for i in range(1, len(poly) - 1):
            faces_by_mtl[current_mtl].append([poly[0], poly[i], poly[i + 1]])

  return verts, texcoords, faces_by_mtl


def resolve_quetoo_material(material: str, search_paths: list[Path], model_dir: Path) -> Path | None:
  if not material:
    return None

  rel = Path(material)
  image_exts = [".tga", ".png", ".jpg", ".jpeg"]

  def material_candidates(base: Path) -> list[Path]:
    out = [base]
    suffix = base.suffix.lower()
    # Materials like "missile.mdl_0" should also try ".tga"/etc appended.
    if suffix not in image_exts:
      out.extend([Path(f"{base}{ext}") for ext in image_exts])
    return out

  # Also support paths relative to the mesh model itself.
  local_candidates = [model_dir / rel]
  if not str(rel).startswith("models/"):
    local_candidates.append(model_dir / rel.name)
  for cand in local_candidates:
    for c in material_candidates(cand):
      if c.is_file():
        return c

  for base in search_paths:
    candidates = [
      base / "models" / rel,
      base / rel,
    ]
    if str(rel).startswith("models/"):
      candidates.insert(0, base / rel)
    for cand in candidates:
      for c in material_candidates(cand):
        if c.is_file():
          return c
  return None


def resolve_obj_path(obj_arg: str, search_paths: list[Path]) -> Path:
  candidate = Path(obj_arg).expanduser()
  if candidate.is_absolute():
    return candidate.resolve() if candidate.is_file() else candidate

  # Try current working directory first for normal local usage.
  cwd_candidate = Path.cwd() / candidate
  if cwd_candidate.is_file():
    return cwd_candidate.resolve()

  # Then try Quetoo data roots passed via -p.
  for base in search_paths:
    p = base / candidate
    if p.is_file():
      return p.resolve()
    if not str(candidate).startswith("models/"):
      p2 = base / "models" / candidate
      if p2.is_file():
        return p2.resolve()

  # Error-path fallback: report where we expected to find the asset under -p.
  if search_paths:
    return search_paths[0] / candidate
  return cwd_candidate


def load_texture(path: Path) -> int:
  surf = pygame.image.load(str(path)).convert_alpha()
  data = pygame.image.tostring(surf, "RGBA", True)
  w, h = surf.get_size()
  tex = glGenTextures(1)
  glBindTexture(GL_TEXTURE_2D, tex)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
  glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
  glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
  return tex


def bounds(verts: list[tuple[float, float, float]]):
  xs = [v[0] for v in verts]
  ys = [v[1] for v in verts]
  zs = [v[2] for v in verts]
  return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def main():
  parser = argparse.ArgumentParser(description="OBJ viewer with Quetoo usemtl path support")
  parser.add_argument("-p", "--path", action="append", default=[], help="Quetoo data root search path")
  parser.add_argument("obj", help="OBJ path")
  args = parser.parse_args()

  search_paths = [Path(p).expanduser().resolve() for p in args.path]
  if not search_paths:
    # Useful default for running directly in quetoo repo.
    search_paths.append((Path(__file__).resolve().parents[3] / ".." / "quetoo-data" / "target" / "default").resolve())
  obj_path = resolve_obj_path(args.obj, search_paths)
  if not obj_path.is_file():
    raise SystemExit(f"OBJ not found: {obj_path}")

  verts, texcoords, faces_by_mtl = load_obj(obj_path)
  if not verts:
    raise SystemExit("OBJ has no vertices")

  (minx, maxx), (miny, maxy), (minz, maxz) = bounds(verts)
  cx, cy, cz = (minx + maxx) * 0.5, (miny + maxy) * 0.5, (minz + maxz) * 0.5
  extent = max(maxx - minx, maxy - miny, maxz - minz)
  if extent <= 0:
    extent = 1.0

  pygame.init()
  w, h = 1280, 800
  pygame.display.set_mode((w, h), DOUBLEBUF | OPENGL)
  pygame.display.set_caption(f"obj-fu · {obj_path.name}")

  glEnable(GL_DEPTH_TEST)
  glEnable(GL_TEXTURE_2D)
  glClearColor(0.10, 0.11, 0.13, 1.0)

  glMatrixMode(GL_PROJECTION)
  glLoadIdentity()
  gluPerspective(50.0, w / h, max(0.01, extent * 0.01), extent * 100.0)
  glMatrixMode(GL_MODELVIEW)

  tex_by_mtl: dict[str, int | None] = {}
  for mtl in faces_by_mtl.keys():
    p = resolve_quetoo_material(mtl, search_paths, obj_path.parent)
    tex_by_mtl[mtl] = load_texture(p) if p else None
    if p:
      print(f"usemtl {mtl} -> {p}")
    elif mtl:
      print(f"usemtl {mtl} -> (not found)")

  yaw = 35.0
  pitch = 20.0
  dist = extent * 2.3
  orbiting = False
  last = (0, 0)
  clock = pygame.time.Clock()

  running = True
  while running:
    for event in pygame.event.get():
      if event.type == QUIT:
        running = False
      elif event.type == MOUSEBUTTONDOWN and event.button == 1:
        orbiting = True
        last = event.pos
      elif event.type == MOUSEBUTTONUP and event.button == 1:
        orbiting = False
      elif event.type == MOUSEMOTION and orbiting:
        dx = event.pos[0] - last[0]
        dy = event.pos[1] - last[1]
        yaw += dx * 0.35
        pitch += dy * 0.35
        last = event.pos
      elif event.type == MOUSEWHEEL:
        dist = max(extent * 0.15, dist - event.y * extent * 0.08)

    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()

    rt = math.radians(yaw)
    rp = math.radians(pitch)
    ex = cx + dist * math.cos(rp) * math.sin(rt)
    ey = cy + dist * math.cos(rp) * math.cos(rt)
    ez = cz + dist * math.sin(rp)
    upz = -1.0 if 90.0 < (pitch % 360.0) < 270.0 else 1.0
    gluLookAt(ex, ey, ez, cx, cy, cz, 0.0, 0.0, upz)

    for mtl, tris in faces_by_mtl.items():
      tex = tex_by_mtl.get(mtl)
      if tex:
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex)
      else:
        glDisable(GL_TEXTURE_2D)

      glBegin(GL_TRIANGLES)
      for tri in tris:
        for vi, ti in tri:
          if ti is not None and 0 <= ti < len(texcoords):
            u, v = texcoords[ti]
            glTexCoord2f(u, v)
          x, y, z = verts[vi]
          glVertex3f(x, y, z)
      glEnd()

    pygame.display.flip()
    clock.tick(60)

  pygame.quit()


if __name__ == "__main__":
  main()
