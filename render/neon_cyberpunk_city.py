#!/usr/bin/env python3
"""
NEON CYBERPUNK CITY — DRONE SHOT  (fully procedural, no external assets)
=======================================================================
A car parked on a rooftop, a man sitting on the car, camera doing a slow
drone flyby/orbit through a neon skyline. Everything is generated in code.

Tested API range: Blender 4.2 LTS -> 5.x  (also runs as the `bpy` pip module)

USAGE
-----
GUI:
    Blender > Scripting tab > paste/run. Then Render > Render Animation.

Headless (what the GitHub Actions workflow does):
    blender -b --factory-startup --python render/neon_cyberpunk_city.py -- \
        --render --out frames --res 1280x720 --samples 32 --frames 1-150

Options (after the "--"):
    --engine cycles|eevee   render engine                (default: cycles)
    --res  WxH             resolution                    (default: 1920x1080)
    --percent N            resolution percentage         (default: 100)
    --samples N            samples / TAA samples         (default: 32)
    --frames A-B           frame range to build+render   (default: 1-150)
    --out DIR              PNG output directory          (default: render_out)
    --render               actually render (else build scene only)
    --glare                add compositor bloom/glare (version dependent)
    --seed N               random seed                   (default: 42)
"""

import bpy
import bmesh
import math
import os
import random
import sys
import time

try:  # tiny arg parser (argparse is available in Blender's python too)
    import argparse
except Exception:  # pragma: no cover
    argparse = None


# ======================================================================
# ARGS
# ======================================================================
def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    if argparse is None:
        return None
    p = argparse.ArgumentParser(description="Neon cyberpunk city drone shot")
    p.add_argument("--engine", default="cycles", choices=["cycles", "eevee"])
    p.add_argument("--res", default="1920x1080")
    p.add_argument("--percent", type=int, default=100)
    p.add_argument("--samples", type=int, default=32)
    p.add_argument("--frames", default="1-150")
    p.add_argument("--out", default="render_out")
    p.add_argument("--render", action="store_true")
    p.add_argument("--glare", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


ARGS = parse_args() or type(
    "D", (), dict(engine="cycles", res="1920x1080", percent=100, samples=32,
                  frames="1-150", out="render_out", render=False, glare=False,
                  seed=42)
)()

RES_X, RES_Y = (int(v) for v in ARGS.res.lower().split("x"))
FRAME_START, FRAME_END = (int(v) for v in ARGS.frames.split("-"))
RNG = random.Random(ARGS.seed)


# ======================================================================
# SCENE HELPERS
# ======================================================================
def clear_scene():
    """Wipe every object + orphan datablock so re-runs are clean."""
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    try:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete(use_global=False)
    except Exception:
        pass
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights,
                 bpy.data.cameras, bpy.data.curves, bpy.data.node_groups,
                 bpy.data.worlds, bpy.data.objects):
        for block in list(coll):
            if getattr(block, "users", 0) == 0:
                try:
                    coll.remove(block)
                except Exception:
                    pass


def activate(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_scale(obj):
    activate(obj)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def add_bevel(obj, width=0.03, segments=2, angle=35.0):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(angle)
    mod.harden_normals = False
    return mod


def cube(name, dims, loc, rot=(0, 0, 0), mat=None):
    """Axis-aligned box centred at loc with FULL dimensions `dims`."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.scale = dims
    obj.rotation_euler = rot
    if mat:
        obj.data.materials.append(mat)
    return obj


def cylinder(name, radius, depth, loc, rot=(0, 0, 0), mat=None, verts=32):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                        vertices=verts, location=loc,
                                        rotation=rot)
    obj = bpy.context.object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    return obj


def sphere(name, radius, loc, mat=None, segments=24, rings=16):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc,
                                         segments=segments, ring_count=rings)
    obj = bpy.context.object
    obj.name = name
    if mat:
        obj.data.materials.append(mat)
    bpy.ops.object.shade_smooth()
    return obj


def join(parts, name):
    bpy.ops.object.select_all(action="DESELECT")
    for p in parts:
        p.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    obj = bpy.context.object
    obj.name = name
    return obj


# ======================================================================
# MATERIALS
# ======================================================================
def emission_mat(name, color, strength=8.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*color, 1.0)
    em.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    try:
        mat.cycles.emission_sampling = "AUTO"
    except Exception:
        pass
    return mat


def pbr_mat(name, color, roughness=0.4, metallic=0.2, extra=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        for key, val in (extra or {}).items():
            if key in bsdf.inputs:
                bsdf.inputs[key].default_value = val
    return mat


def facade_material(name, window_strength=9.0, mirror=0.55):
    """
    Dark glass tower shell with a procedural grid of lit windows.

    Uses Geometry->Position (world space) so window size is physically
    consistent across every building, then:
      Brick texture  -> mortar mask  -> window glass mask
      Noise (blocks) ->  some windows are dark
      Object random  ->  per-building tint (cool/warm/neon)
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (500, -220)
    bsdf.inputs["Base Color"].default_value = (0.012, 0.014, 0.022, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.28
    bsdf.inputs["Metallic"].default_value = 0.62

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-900, 0)

    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-700, 0)
    mapping.inputs["Scale"].default_value = (0.34, 0.34, 0.34)
    L.new(geo.outputs["Position"], mapping.inputs["Vector"])

    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.location = (-480, 120)
    brick.offset = 0.5
    brick.offset_frequency = 2
    brick.squash = 1.0
    brick.inputs["Color1"].default_value = (1, 1, 1, 1)
    brick.inputs["Color2"].default_value = (1, 1, 1, 1)
    brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
    for sock, val in (("Scale", 1.0), ("Mortar Size", 0.055),
                      ("Mortar Smooth", 0.2), ("Bias", 0.0),
                      ("Brick Width", 0.52), ("Row Height", 0.26)):
        if sock in brick.inputs:
            brick.inputs[sock].default_value = val
    L.new(mapping.outputs["Vector"], brick.inputs["Vector"])

    # mortar = 1, glass = 0  ->  invert to get the lit glass mask
    invert = nt.nodes.new("ShaderNodeMath")
    invert.operation = "SUBTRACT"
    invert.location = (-240, 200)
    invert.inputs[0].default_value = 1.0
    L.new(brick.outputs["Fac"], invert.inputs[1])

    # clumps of dark windows
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-480, -180)
    noise.inputs["Scale"].default_value = 0.55
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 3.0
    L.new(geo.outputs["Position"], noise.inputs["Vector"])

    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-240, -180)
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.62
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    mask = nt.nodes.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    mask.location = (0, 60)
    L.new(invert.outputs["Value"], mask.inputs[0])
    L.new(ramp.outputs["Color"], mask.inputs[1])

    strength = nt.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.location = (180, 120)
    strength.inputs[1].default_value = window_strength
    L.new(mask.outputs["Value"], strength.inputs[0])

    # per-building window tint
    info = nt.nodes.new("ShaderNodeObjectInfo")
    info.location = (-480, -420)
    tint = nt.nodes.new("ShaderNodeValToRGB")
    tint.location = (-240, -420)
    cr = tint.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.55, 0.85, 1.0, 1)      # cold cyan
    cr.elements[1].position = 1.0
    cr.elements[1].color = (1.0, 0.72, 0.42, 1)      # warm tungsten
    e = cr.elements.new(0.55)
    e.color = (1.0, 0.45, 0.75, 1)                   # magenta
    L.new(info.outputs["Random"], tint.inputs["Fac"])

    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (400, 160)
    L.new(tint.outputs["Color"], em.inputs["Color"])
    L.new(strength.outputs["Value"], em.inputs["Strength"])

    add = nt.nodes.new("ShaderNodeAddShader")
    add.location = (700, 0)
    L.new(bsdf.outputs["BSDF"], add.inputs[0])
    L.new(em.outputs["Emission"], add.inputs[1])
    L.new(add.outputs["Shader"], out.inputs["Surface"])

    mat.use_backface_culling = False
    return mat


def screen_material(name, color_a, color_b, strength=6.0):
    """Big emissive billboard with a procedural 'video wall' pattern."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (500, 0)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-600, 0)
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.location = (-380, 0)
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 3.0
    if "Distortion" in wave.inputs:
        wave.inputs["Distortion"].default_value = 2.0
    L.new(geo.outputs["Position"], wave.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-120, 0)
    ramp.color_ramp.elements[0].color = (*color_a, 1)
    ramp.color_ramp.elements[1].color = (*color_b, 1)
    L.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (220, 0)
    em.inputs["Strength"].default_value = strength
    L.new(ramp.outputs["Color"], em.inputs["Color"])
    L.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


NEON = [
    (0.00, 0.90, 1.00),   # cyan
    (1.00, 0.06, 0.62),   # magenta
    (0.55, 0.10, 1.00),   # violet
    (0.10, 1.00, 0.45),   # acid green
    (1.00, 0.42, 0.05),   # amber
    (0.20, 0.45, 1.00),   # electric blue
]


# ======================================================================
# BUILD THE CITY
# ======================================================================
clear_scene()
scene = bpy.context.scene

BUILDING_MATS = [facade_material(f"Facade_{i}", window_strength=s)
                 for i, s in enumerate((7.0, 11.0, 9.0))]
ROOF_MAT = pbr_mat("RoofDeck", (0.02, 0.021, 0.026), roughness=0.75, metallic=0.15)
STRIP_MATS = [emission_mat(f"NeonStrip_{i}", c, strength=14.0)
              for i, c in enumerate(NEON)]
BAND_MATS = [emission_mat(f"NeonBand_{i}", c, strength=7.0)
             for i, c in enumerate(NEON)]


def two_tone_facade(obj, facade, roof):
    """Side faces get the window shader, the top face a plain roof deck."""
    obj.data.materials.clear()
    obj.data.materials.append(facade)
    obj.data.materials.append(roof)
    for poly in obj.data.polygons:
        poly.material_index = 1 if poly.normal.z > 0.5 else 0


def add_building(x, y, w, d, h):
    obj = cube(f"Bldg_{int(x)}_{int(y)}", (w, d, h), (x, y, h / 2))
    two_tone_facade(obj, RNG.choice(BUILDING_MATS), ROOF_MAT)

    # vertical neon strips hugging two corners
    strip_mat = RNG.choice(STRIP_MATS)
    for sx, sy in ((1, 1), (-1, -1)):
        cube("Strip", (0.13, 0.13, h * RNG.uniform(0.55, 0.98)),
             (x + sx * (w / 2 + 0.02), y + sy * (d / 2 + 0.02),
              h * RNG.uniform(0.5, 0.62)), mat=strip_mat)

    # glowing crown band
    cube("Band", (w * 1.03, d * 1.03, RNG.uniform(0.22, 0.5)),
         (x, y, h * RNG.uniform(0.82, 0.95)), mat=RNG.choice(BAND_MATS))

    # rooftop clutter + antenna
    if h > 26 and RNG.random() < 0.55:
        cylinder("Antenna", 0.16, RNG.uniform(4, 11),
                 (x + RNG.uniform(-w / 3, w / 3), y + RNG.uniform(-d / 3, d / 3),
                  h + RNG.uniform(2, 5.5)), mat=ROOF_MAT, verts=8)
        sphere("AntennaTip", 0.22,
               (x, y, h + RNG.uniform(6, 10)),
               mat=emission_mat("TipRed", (1.0, 0.12, 0.15), 25.0),
               segments=8, rings=6)
    return obj


def build_city(cells=6, cell=19.0, hero_clear=27.0, corridor=66.0):
    """Roughly 12x12 blocks with visible street gaps, a hero clearing in the
    middle and a lowered 'canyon' ring the camera flies through."""
    for ix in range(-cells, cells + 1):
        for iy in range(-cells, cells + 1):
            cx, cy = ix * cell, iy * cell
            x = cx + RNG.uniform(-1.6, 1.6)
            y = cy + RNG.uniform(-1.6, 1.6)
            dist = math.hypot(x, y)
            if dist < hero_clear:
                continue                      # hero rooftop clearing
            w = min(RNG.uniform(8.5, 14.5), cell - 5.0)
            d = min(RNG.uniform(8.5, 14.5), cell - 5.0)
            h = RNG.uniform(16, 46) * (1.0 + 1.15 * math.exp(-dist / 70.0))
            if dist < corridor:               # keep the flight path clear
                h = min(h, 46.0)
            add_building(x, y, w, d, h)

    # a handful of oversized landmark towers far out
    for ang, radius, w, d, h in ((12, 96, 18, 18, 118), (105, 88, 15, 15, 96),
                                 (198, 92, 20, 16, 130), (287, 84, 14, 14, 88)):
        a = math.radians(ang)
        add_building(radius * math.cos(a), radius * math.sin(a), w, d, h)


def build_billboards():
    """Three huge glowing video walls on distant facades."""
    specs = [
        (-58, -52, math.radians(38), 26, 15, (0.05, 0.85, 1.0), (0.55, 0.05, 1.0)),
        (70, -30, math.radians(-120), 22, 13, (1.0, 0.1, 0.55), (1.0, 0.55, 0.1)),
        (-20, 84, math.radians(200), 30, 17, (0.4, 0.05, 1.0), (0.1, 0.9, 0.7)),
    ]
    for i, (x, y, rot, w, h, ca, cb) in enumerate(specs):
        mat = screen_material(f"Billboard_{i}", ca, cb, strength=5.5)
        bpy.ops.mesh.primitive_plane_add(size=1, location=(x, y, 46 + i * 6))
        obj = bpy.context.object
        obj.name = f"Billboard_{i}"
        obj.scale = (w, h, 1)
        obj.rotation_euler = (math.radians(90), 0, rot)
        obj.data.materials.append(mat)


build_city()
build_billboards()

# ======================================================================
# HERO ROOFTOP
# ======================================================================
ROOF_H = 40.0                 # tower height
SLAB = 0.35                   # roof slab thickness
ROOF_Z = ROOF_H + SLAB        # walkable roof surface


def build_rooftop():
    tower = cube("HeroTower", (22, 22, ROOF_H), (0, 0, ROOF_H / 2))
    two_tone_facade(tower, BUILDING_MATS[1], ROOF_MAT)

    cube("RoofSlab", (22.8, 22.8, SLAB), (0, 0, ROOF_H + SLAB / 2),
         mat=pbr_mat("RoofSlabMat", (0.028, 0.029, 0.036), roughness=0.45,
                     metallic=0.25))

    # neon rim around the roof edge
    rim_mat = emission_mat("RimCyan", (0.05, 0.85, 1.0), strength=22.0)
    for i, (dx, dy, sx, sy) in enumerate(((0, 1, 1, 0), (0, -1, 1, 0),
                                          (1, 0, 0, 1), (-1, 0, 0, 1))):
        cube(f"Rim_{i}", (22.6 if sx else 0.18, 22.6 if sy else 0.18, 0.10),
             (dx * 11.1, dy * 11.1, ROOF_Z + 0.06), mat=rim_mat)

    # floor light strips casting the purple bounce
    floor_mat = emission_mat("RimMagenta", (1.0, 0.08, 0.55), strength=16.0)
    for i, dx in enumerate((-1, 1)):
        cube(f"FloorStrip_{i}", (0.16, 16.0, 0.06),
             (dx * 7.5, 2.0, ROOF_Z + 0.04), mat=floor_mat)

    # rooftop machinery
    for i, (px, py, dims) in enumerate(((-7.5, -6.5, (3.0, 2.2, 1.3)),
                                        (-6.6, 6.8, (2.2, 3.4, 1.1)),
                                        (8.2, 7.4, (2.6, 2.6, 1.5)))):
        body = cube(f"AC_{i}", dims, (px, py, ROOF_Z + dims[2] / 2),
                    mat=pbr_mat(f"ACMat_{i}", (0.05, 0.052, 0.06),
                                roughness=0.55, metallic=0.5))
        apply_scale(body)
        add_bevel(body, 0.05, 2)
        cube(f"ACVent_{i}", (dims[0] * 0.7, dims[1] * 0.7, 0.06),
             (px, py, ROOF_Z + dims[2] + 0.02),
             mat=emission_mat(f"ACGlow_{i}", (0.15, 0.9, 1.0), 5.0))

    # mast with a red beacon
    mast_mat = pbr_mat("Mast", (0.06, 0.06, 0.07), roughness=0.4, metallic=0.8)
    cylinder("Mast", 0.20, 9.0, (8.6, -8.4, ROOF_Z + 4.5), mat=mast_mat, verts=10)
    sphere("MastBeacon", 0.30, (8.6, -8.4, ROOF_Z + 9.1),
           mat=emission_mat("Beacon", (1.0, 0.15, 0.2), 30.0))

    # neon sign standing on the front edge, reading TRACEORA
    sign_mat = emission_mat("SignMagenta", (1.0, 0.12, 0.62), strength=28.0)
    frame_mat = pbr_mat("SignFrame", (0.03, 0.03, 0.035), roughness=0.5,
                        metallic=0.7)
    bpy.ops.object.text_add(location=(0, -9.9, ROOF_Z + 0.15))
    txt = bpy.context.object
    txt.name = "SignText"
    txt.data.body = "TRACEORA"
    txt.data.align_x = "CENTER"
    txt.data.align_y = "CENTER"
    txt.data.size = 2.5
    txt.data.extrude = 0.10
    txt.rotation_euler = (math.radians(90), 0, 0)
    txt.data.materials.append(sign_mat)
    activate(txt)
    bpy.ops.object.convert(target="MESH")

    cube("SignBack", (17.0, 0.35, 3.6), (0, -10.35, ROOF_Z + 2.1),
         mat=frame_mat)
    for i, sx in enumerate((-1, 1)):
        cube(f"SignPost_{i}", (0.25, 0.25, 3.4), (sx * 7.2, -10.3, ROOF_Z + 1.7),
             mat=frame_mat)


build_rooftop()

# ======================================================================
# HERO CAR
# ======================================================================
CAR_Z = ROOF_Z               # wheels touch the roof


def build_car():
    paint = pbr_mat("CarPaint", (0.015, 0.016, 0.02), roughness=0.12,
                    metallic=1.0)
    glass = pbr_mat("CarGlass", (0.02, 0.035, 0.05), roughness=0.03,
                    metallic=0.4)
    rubber = pbr_mat("CarRubber", (0.008, 0.008, 0.01), roughness=0.85,
                     metallic=0.0)
    chrome = pbr_mat("CarChrome", (0.55, 0.58, 0.65), roughness=0.16,
                     metallic=1.0)
    underglow = emission_mat("CarUnderglow", (0.62, 0.05, 1.0), strength=16.0)
    head = emission_mat("CarHeadlight", (0.55, 0.85, 1.0), strength=45.0)
    tail = emission_mat("CarTail", (1.0, 0.06, 0.35), strength=35.0)

    parts = []

    # main body + wedge nose + tapered cabin
    parts.append(cube("Body", (4.30, 1.92, 0.62), (0.0, 0.0, CAR_Z + 0.62),
                      mat=paint))
    parts.append(cube("Nose", (1.10, 1.80, 0.40), (2.30, 0.0, CAR_Z + 0.50),
                      mat=paint))
    parts.append(cube("Cabin", (2.25, 1.66, 0.52), (-0.35, 0.0, CAR_Z + 1.16),
                      mat=glass))
    parts.append(cube("Roof", (1.90, 1.50, 0.10), (-0.45, 0.0, CAR_Z + 1.45),
                      mat=paint))
    parts.append(cube("Trunk", (0.95, 1.85, 0.24), (-2.30, 0.0, CAR_Z + 0.86),
                      mat=paint))
    parts.append(cube("Splitter", (0.55, 1.98, 0.10), (2.55, 0.0, CAR_Z + 0.30),
                      mat=chrome))
    parts.append(cube("Wing", (0.45, 1.80, 0.07), (-2.45, 0.0, CAR_Z + 1.06),
                      mat=paint))

    # wheels: tyre + glowing rim face
    for wx in (-1.42, 1.42):
        for wy in (-0.93, 0.93):
            parts.append(cylinder("Tyre", 0.44, 0.30, (wx, wy, CAR_Z + 0.44),
                                  rot=(math.radians(90), 0, 0), mat=rubber,
                                  verts=28))
            rim = cylinder("Rim", 0.26, 0.34, (wx, wy, CAR_Z + 0.44),
                           rot=(math.radians(90), 0, 0),
                           mat=emission_mat("RimGlow",
                                            RNG.choice([(0.1, 0.9, 1.0),
                                                        (1.0, 0.1, 0.6)]),
                                            12.0), verts=20)
            parts.append(rim)

    # underglow slab + light bars
    parts.append(cube("Underglow", (4.05, 1.72, 0.05), (0.0, 0.0, CAR_Z + 0.10),
                      mat=underglow))
    for wy in (-0.62, 0.62):
        parts.append(cube("Headlight", (0.10, 0.42, 0.16),
                          (2.85, wy, CAR_Z + 0.62), mat=head))
    parts.append(cube("TailBar", (0.08, 1.62, 0.11), (-2.80, 0.0, CAR_Z + 0.78),
                      mat=tail))

    car = join(parts, "HeroCar")
    apply_scale(car)
    add_bevel(car, 0.045, 2, 34.0)
    return car


hero_car = build_car()
CAR_TOP = CAR_Z + 1.50       # roof panel top

# ======================================================================
# SEATED MAN
# ======================================================================
def build_seated_man(base_z):
    jacket = pbr_mat("ManJacket", (0.028, 0.030, 0.036), roughness=0.55,
                     metallic=0.15)
    pants = pbr_mat("ManPants", (0.045, 0.048, 0.058), roughness=0.7,
                    metallic=0.05)
    skin = pbr_mat("ManSkin", (0.42, 0.27, 0.20), roughness=0.55,
                   metallic=0.0)
    hair = pbr_mat("ManHair", (0.02, 0.018, 0.02), roughness=0.75,
                   metallic=0.1)
    trim = emission_mat("ManTrim", (1.0, 0.10, 0.55), strength=18.0)
    boot = pbr_mat("ManBoot", (0.015, 0.015, 0.018), roughness=0.4,
                   metallic=0.3)

    parts = []
    # pelvis sits on the car roof, torso leans forward (+X), facing +X
    parts.append(cube("Pelvis", (0.42, 0.44, 0.22), (0.0, 0.0, base_z + 0.11),
                      mat=pants))
    parts.append(cube("Torso", (0.40, 0.48, 0.62), (0.06, 0.0, base_z + 0.52),
                      rot=(0, math.radians(9), 0), mat=jacket))
    # glowing zip line down the jacket
    parts.append(cube("Zip", (0.03, 0.05, 0.56), (0.27, 0.0, base_z + 0.52),
                      rot=(0, math.radians(9), 0), mat=trim))
    parts.append(cube("Collar", (0.30, 0.40, 0.09), (0.14, 0.0, base_z + 0.84),
                      mat=trim))

    # neck + head + hair
    parts.append(cylinder("Neck", 0.075, 0.13, (0.13, 0.0, base_z + 0.92),
                          mat=skin, verts=12))
    parts.append(sphere("Head", 0.145, (0.15, 0.0, base_z + 1.06), mat=skin))
    hair_obj = sphere("Hair", 0.152, (0.11, 0.0, base_z + 1.10), mat=hair)
    hair_obj.scale = (1.0, 1.0, 0.85)
    parts.append(hair_obj)

    # thighs forward, shins hanging off the front of the cabin
    for side in (-0.13, 0.13):
        parts.append(cube("Thigh", (0.52, 0.17, 0.17),
                          (0.30, side, base_z + 0.11), mat=pants))
        parts.append(cube("Shin", (0.17, 0.16, 0.56),
                          (0.55, side, base_z - 0.24),
                          rot=(0, math.radians(-12), 0), mat=pants))
        parts.append(cube("Boot", (0.30, 0.16, 0.13),
                          (0.62, side, base_z - 0.55), mat=boot))
        # arms propped back behind him
        parts.append(cube("Arm", (0.50, 0.13, 0.13),
                          (-0.14, side * 1.35, base_z + 0.34),
                          rot=(0, math.radians(-38), 0), mat=jacket))
        parts.append(sphere("Hand", 0.075, (-0.36, side * 1.6, base_z + 0.20),
                            mat=skin, segments=12, rings=8))

    man = join(parts, "SeatedMan")
    apply_scale(man)
    add_bevel(man, 0.02, 2, 40.0)
    return man


seated_man = build_seated_man(CAR_TOP)
# rotational drift so he is not bolt-straight against the skyline
seated_man.rotation_euler = (0, 0, math.radians(-14))
seated_man.location = (0.0, 0.0, 0.0)

# ======================================================================
# WORLD + HAZE
# ======================================================================
world = bpy.data.worlds.new("CyberWorld")
scene.world = world
world.use_nodes = True
wnt = world.node_tree
wnt.nodes.clear()
wout = wnt.nodes.new("ShaderNodeOutputWorld")
wout.location = (400, 0)
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.location = (150, 120)
wbg.inputs["Color"].default_value = (0.012, 0.013, 0.028, 1.0)
wbg.inputs["Strength"].default_value = 0.55
wnt.links.new(wbg.outputs["Background"], wout.inputs["Surface"])

# homogeneous volumetric haze -> the neon halos / atmospheric depth
haze = wnt.nodes.new("ShaderNodeVolumeScatter")
haze.location = (150, -160)
haze.inputs["Color"].default_value = (0.42, 0.52, 0.85, 1.0)
haze.inputs["Density"].default_value = 0.0075
if "Anisotropy" in haze.inputs:
    haze.inputs["Anisotropy"].default_value = 0.45
wnt.links.new(haze.outputs["Volume"], wout.inputs["Volume"])

# ======================================================================
# LIGHTS
# ======================================================================
def add_area(name, loc, color, energy, size, target=(0, 0, CAR_Z + 0.9)):
    light = bpy.data.lights.new(name, type="AREA")
    light.color = color
    light.energy = energy
    light.size = size
    obj = bpy.data.objects.new(name, light)
    obj.location = loc
    direction = (target[0] - loc[0], target[1] - loc[1], target[2] - loc[2])
    from mathutils import Vector
    obj.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(obj)
    return obj


# magenta key from camera side, cyan rim behind, violet fill from above
add_area("KeyMagenta", (7.0, -9.0, CAR_Z + 6.0), (1.0, 0.35, 0.72), 2600, 7.0)
add_area("RimCyan", (-9.5, 9.5, CAR_Z + 4.5), (0.25, 0.85, 1.0), 3200, 6.0)
add_area("FillViolet", (9.0, 8.0, CAR_Z + 3.0), (0.55, 0.30, 1.0), 900, 8.0)
add_area("TopFill", (0.0, 0.0, CAR_Z + 9.0), (0.60, 0.75, 1.0), 1200, 10.0,
         target=(0, 0, CAR_Z))

# faint moonlight
sun_data = bpy.data.lights.new("MoonSun", type="SUN")
sun_data.energy = 0.45
sun_data.color = (0.42, 0.55, 1.0)
sun_data.angle = math.radians(8)
sun_obj = bpy.data.objects.new("MoonSun", sun_data)
scene.collection.objects.link(sun_obj)
sun_obj.rotation_euler = (math.radians(58), 0, math.radians(35))

# ======================================================================
# DRONE CAMERA
# ======================================================================
from mathutils import Vector  # noqa: E402

cam_data = bpy.data.cameras.new("DroneCam")
cam_data.lens = 24.0
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.1
cam_data.clip_end = 900.0
cam_obj = bpy.data.objects.new("DroneCam", cam_data)
scene.collection.objects.link(cam_obj)
scene.camera = cam_obj

# depth of field locked to the man for a cinematic falloff
focus = bpy.data.objects.new("FocusTarget", None)
focus.location = (0.0, 0.0, CAR_TOP + 0.9)
scene.collection.objects.link(focus)
cam_data.dof.use_dof = True
cam_data.dof.focus_object = focus
cam_data.dof.aperture_fstop = 4.0

# smoother-than-bezier "drone" motion curve: sample the analytic path
prefs = bpy.context.preferences.edit
for attr, val in (("keyframe_new_interpolation_type", "BEZIER"),
                  ("keyframe_new_handle_type", "AUTO_CLAMPED")):
    try:
        setattr(prefs, attr, val)
    except Exception:
        pass


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def camera_pose(t):
    """t in 0..1 -> (location, look-at target) for the flyby."""
    e = smoothstep(t)
    angle = math.radians(203.0 + (338.0 - 203.0) * e)
    radius = 62.0 - 42.0 * e
    height = CAR_Z + 30.0 - 27.0 * e
    # gentle drone drift / bob so the move never feels robotic
    angle += math.radians(1.6 * math.sin(t * math.pi * 2.1))
    height += 0.55 * math.sin(t * math.pi * 3.3)
    radius += 0.9 * math.sin(t * math.pi * 2.7)
    loc = Vector((radius * math.cos(angle), radius * math.sin(angle), height))
    target = Vector((0.0, 0.0, CAR_Z + 1.05 + 0.5 * (1.0 - e)))
    return loc, target


PATH_KEYS = 26
for i in range(PATH_KEYS):
    t = i / (PATH_KEYS - 1)
    frame = FRAME_START + round(t * (FRAME_END - FRAME_START))
    loc, target = camera_pose(t)
    cam_obj.location = loc
    cam_obj.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    # subtle banking, like a drone leaning into the arc
    cam_obj.rotation_euler.rotate_axis("Z", math.radians(-2.4 * math.sin(t * math.pi)))
    cam_obj.keyframe_insert(data_path="location", frame=frame)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# ======================================================================
# RENDER SETTINGS
# ======================================================================
scene.render.resolution_x = RES_X
scene.render.resolution_y = RES_Y
scene.render.resolution_percentage = ARGS.percent
scene.render.fps = 24
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False
scene.render.use_file_extension = False  # we always pass explicit *.png paths
scene.render.use_persistent_data = True
scene.render.filepath = os.path.join(ARGS.out, "frame_")

# colour management: filmic-ish night grade
for vt in ("AgX", "Filmic", "Standard"):
    try:
        scene.view_settings.view_transform = vt
        break
    except Exception:
        continue
try:
    scene.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    pass
try:
    scene.view_settings.exposure = 0.55
except Exception:
    pass


def configure_cycles():
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.device = "CPU"
    cy.samples = ARGS.samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.02
    cy.use_denoising = True
    for denoiser in ("OPENIMAGEDENOISE", "OPTIX"):
        try:
            cy.denoiser = denoiser
            break
        except Exception:
            continue
    cy.max_bounces = 6
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 3
    cy.transmission_bounces = 2
    cy.volume_bounces = 1
    cy.transparent_max_bounces = 4
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.sample_clamp_indirect = 12.0
    cy.use_light_tree = True
    try:
        cy.volume_step_rate = 2.0
        cy.volume_max_steps = 96
    except Exception:
        pass


def configure_eevee():
    engines = [e.identifier for e in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for name in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if name in engines:
            scene.render.engine = name
            break
    ee = scene.eevee
    for attr, val in (("taa_render_samples", ARGS.samples),
                      ("use_gtao", True), ("use_soft_shadows", True),
                      ("use_volumetric_lights", True),
                      ("volumetric_tile_size", "8"),
                      ("volumetric_samples", 64),
                      ("use_raytracing", True)):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
    # legacy EEVEE bloom (removed in 4.2+)
    try:
        ee.use_bloom = True
        ee.bloom_threshold = 0.85
        ee.bloom_intensity = 0.06
        ee.bloom_radius = 7.0
    except Exception:
        pass


def configure_glare():
    """Compositor bloom — API moved around between 4.x and 5.x, so try all."""
    try:
        if hasattr(scene, "use_nodes"):
            scene.use_nodes = True
        tree = getattr(scene, "node_tree", None)
        if tree is None:
            print("[glare] no legacy compositor node tree; skipping")
            return
        tree.nodes.clear()
        rl = tree.nodes.new("CompositorNodeRLayers")
        rl.location = (-300, 0)
        glare = tree.nodes.new("CompositorNodeGlare")
        glare.location = (0, 0)
        for attr, val in (("glare_type", "FOG_GLOW"), ("quality", "HIGH"),
                          ("threshold", 0.85), ("size", 7),
                          ("mix", -0.35)):
            try:
                setattr(glare, attr, val)
            except Exception:
                pass
        comp = tree.nodes.new("CompositorNodeComposite")
        comp.location = (300, 0)
        tree.links.new(rl.outputs["Image"], glare.inputs[0])
        tree.links.new(glare.outputs[0], comp.inputs["Image"])
        print("[glare] compositor glare enabled")
    except Exception as exc:  # pragma: no cover
        print(f"[glare] unavailable on this build ({exc}); relying on post bloom")


print(f"[scene] engine requested: {ARGS.engine}")
if ARGS.engine == "eevee":
    configure_eevee()
else:
    configure_cycles()
if ARGS.glare:
    configure_glare()
scene.frame_set(FRAME_START)

# ======================================================================
# STATS + OPTIONAL RENDER
# ======================================================================
objs = len(scene.objects)
tris = sum(len(o.data.polygons) for o in scene.objects if o.type == "MESH")
print(f"[scene] {objs} objects, {tris} faces, frames {FRAME_START}-{FRAME_END}, "
      f"{scene.render.resolution_x}x{scene.render.resolution_y}")
print(f"[scene] engine: {scene.render.engine}, samples: {ARGS.samples}")

if ARGS.render:
    out_dir = os.path.abspath(ARGS.out)
    os.makedirs(out_dir, exist_ok=True)
    total = FRAME_END - FRAME_START + 1
    t_start = time.time()
    for i, frame in enumerate(range(FRAME_START, FRAME_END + 1), start=1):
        t0 = time.time()
        scene.frame_set(frame)
        scene.render.filepath = os.path.join(out_dir, f"frame_{frame:04d}.png")
        bpy.ops.render.render(write_still=True)
        done = time.time() - t_start
        eta = (done / i) * (total - i)
        print(f"[render] frame {frame} ({i}/{total}) "
              f"{time.time() - t0:.1f}s  elapsed {done / 60:.1f}m  "
              f"eta {eta / 60:.1f}m", flush=True)
    print(f"[render] done in {(time.time() - t_start) / 60:.2f} min -> {out_dir}")
else:
    print("[scene] build only (pass --render to render frames)")
