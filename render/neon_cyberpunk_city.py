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
    Blender > Scripting tab > open this file > Run Script.
    Then Render > Render Animation.

Headless (what the GitHub Actions workflow does):
    blender -b --factory-startup --python render/neon_cyberpunk_city.py -- \
        --render --out frames --res 1280x720 --samples 32 --frames 1-150

Options (after the "--"):
    --engine cycles|eevee   render engine                  (default: cycles)
    --res  WxH              resolution                     (default: 1920x1080)
    --percent N             resolution percentage          (default: 100)
    --samples N             samples / TAA samples          (default: 32)
    --frames A-B            frame range                    (default: 1-150)
    --out DIR               PNG output directory           (default: render_out)
    --render                render the frame range (else scene only)
    --variants              benchmark look/timing variants of one frame
    --profile NAME          full | thin | thin_hero | none (default: thin_hero)
    --glare                 add compositor bloom/glare (version dependent)
    --seed N                random seed                    (default: 42)
"""

import bpy
import math
import os
import random
import sys
import time

try:
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
    p.add_argument("--shot", default="")
    p.add_argument("--out", default="render_out")
    p.add_argument("--render", action="store_true")
    p.add_argument("--variants", action="store_true")
    p.add_argument("--profile", default="thin_hero")
    p.add_argument("--glare", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args(argv)


ARGS = parse_args() or type(
    "D", (), dict(engine="cycles", res="1920x1080", percent=100, samples=32,
                  frames="1-150", shot="", out="render_out", render=False,
                  variants=False, profile="thin_hero", glare=False, seed=42)
)()

RES_X, RES_Y = (int(v) for v in ARGS.res.lower().split("x"))
# FRAME_START/END = what this process renders, SHOT_START/END = the full shot
# the camera path is authored over (so the shot can be rendered in shards).
FRAME_START, FRAME_END = (int(v) for v in ARGS.frames.split("-"))
SHOT_START, SHOT_END = (int(v) for v in (ARGS.shot or ARGS.frames).split("-"))
RNG = random.Random(ARGS.seed)


# ======================================================================
# SCENE HELPERS
# ======================================================================
def clear_scene():
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
    return mod


def cube(name, dims, loc, rot=(0, 0, 0), mat=None):
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
# Materials whose emission should stay light-emitting (sampled by Cycles) even
# in the fast profiles - these are the ones actually lighting the hero shot.
HERO_EMITTERS = ("RimCyan", "RimMagenta", "CarUnderglow", "CarHeadlight",
                 "CarTail", "SignMagenta", "ManTrim", "RimGlow")


def tag_emitter(mat, hero=False):
    try:
        mat.cycles.emission_sampling = "AUTO" if hero else "AUTO"
    except Exception:
        pass
    return mat


def emission_mat(name, color, strength=8.0, hero=False):
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
    tag_emitter(mat, hero)
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


def facade_material(name, window_strength=4.5):
    """
    Dark curtain-wall tower with a punched grid of lit windows.

    Brick textures are 2D, so an axis-aligned box needs one projection per
    wall direction: (y,z) for X-facing walls and (x,z) for Y-facing walls,
    blended by the surface normal. World-space position keeps the window
    size identical on every building regardless of its scale.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    L = nt.links

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (1100, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (700, -260)
    bsdf.inputs["Base Color"].default_value = (0.012, 0.014, 0.022, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.20
    bsdf.inputs["Metallic"].default_value = 0.80

    geo = nt.nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1200, 0)
    psep = nt.nodes.new("ShaderNodeSeparateXYZ")
    psep.location = (-1020, 120)
    L.new(geo.outputs["Position"], psep.inputs["Vector"])
    nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nsep.location = (-1020, -420)
    L.new(geo.outputs["Normal"], nsep.inputs["Vector"])

    def brick_mask(src_a, src_b, y):
        """1.0 on window glass, 0.0 on mullions/spandrels."""
        comb = nt.nodes.new("ShaderNodeCombineXYZ")
        comb.location = (-840, y)
        L.new(src_a, comb.inputs["X"])
        L.new(src_b, comb.inputs["Y"])
        mapping = nt.nodes.new("ShaderNodeMapping")
        mapping.location = (-660, y)
        mapping.inputs["Scale"].default_value = (0.35, 0.35, 0.35)
        L.new(comb.outputs["Vector"], mapping.inputs["Vector"])
        brick = nt.nodes.new("ShaderNodeTexBrick")
        brick.location = (-470, y)
        brick.offset = 0.5
        brick.offset_frequency = 2
        brick.squash = 1.0
        brick.inputs["Color1"].default_value = (1, 1, 1, 1)
        brick.inputs["Color2"].default_value = (1, 1, 1, 1)
        brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
        for sock, val in (("Scale", 1.0), ("Mortar Size", 0.11),
                          ("Mortar Smooth", 0.1), ("Bias", 0.0),
                          ("Brick Width", 0.34), ("Row Height", 0.30)):
            if sock in brick.inputs:
                brick.inputs[sock].default_value = val
        L.new(mapping.outputs["Vector"], brick.inputs["Vector"])
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.location = (-250, y)
        inv.inputs[0].default_value = 1.0
        L.new(brick.outputs["Fac"], inv.inputs[1])
        return inv.outputs["Value"]

    mask_x = brick_mask(psep.outputs["Y"], psep.outputs["Z"], 220)
    mask_y = brick_mask(psep.outputs["X"], psep.outputs["Z"], -60)

    abs_nx = nt.nodes.new("ShaderNodeMath")
    abs_nx.operation = "ABSOLUTE"
    abs_nx.location = (-660, -420)
    L.new(nsep.outputs["X"], abs_nx.inputs[0])
    abs_ny = nt.nodes.new("ShaderNodeMath")
    abs_ny.operation = "ABSOLUTE"
    abs_ny.location = (-660, -520)
    L.new(nsep.outputs["Y"], abs_ny.inputs[0])
    pick = nt.nodes.new("ShaderNodeMath")
    pick.operation = "GREATER_THAN"
    pick.location = (-470, -470)
    L.new(abs_nx.outputs["Value"], pick.inputs[0])
    L.new(abs_ny.outputs["Value"], pick.inputs[1])

    # windows = mask_x*pick + mask_y*(1-pick)  (pure math, no Mix node so it
    # works identically on 4.2 LTS and 5.x where legacy MixRGB is gone)
    inv_pick = nt.nodes.new("ShaderNodeMath")
    inv_pick.operation = "SUBTRACT"
    inv_pick.location = (-250, -520)
    inv_pick.inputs[0].default_value = 1.0
    L.new(pick.outputs["Value"], inv_pick.inputs[1])
    wx = nt.nodes.new("ShaderNodeMath")
    wx.operation = "MULTIPLY"
    wx.location = (-60, 220)
    L.new(mask_x.outputs["Value"], wx.inputs[0])
    L.new(pick.outputs["Value"], wx.inputs[1])
    wy = nt.nodes.new("ShaderNodeMath")
    wy.operation = "MULTIPLY"
    wy.location = (-60, 20)
    L.new(mask_y.outputs["Value"], wy.inputs[0])
    L.new(inv_pick.outputs["Value"], wy.inputs[1])
    windows = nt.nodes.new("ShaderNodeMath")
    windows.operation = "ADD"
    windows.location = (120, 120)
    L.new(wx.outputs["Value"], windows.inputs[0])
    L.new(wy.outputs["Value"], windows.inputs[1])

    # large clumps of unlit windows
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.location = (-470, -220)
    noise.inputs["Scale"].default_value = 0.30
    if "Detail" in noise.inputs:
        noise.inputs["Detail"].default_value = 3.0
    L.new(geo.outputs["Position"], noise.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.location = (-250, -220)
    ramp.color_ramp.elements[0].position = 0.44
    ramp.color_ramp.elements[1].position = 0.58
    L.new(noise.outputs["Fac"], ramp.inputs["Fac"])

    mask = nt.nodes.new("ShaderNodeMath")
    mask.operation = "MULTIPLY"
    mask.location = (220, 60)
    L.new(windows.outputs["Value"], mask.inputs[0])
    L.new(ramp.outputs["Color"], mask.inputs[1])

    strength = nt.nodes.new("ShaderNodeMath")
    strength.operation = "MULTIPLY"
    strength.location = (400, 140)
    strength.inputs[1].default_value = window_strength
    L.new(mask.outputs["Value"], strength.inputs[0])

    # per-building window tint
    info = nt.nodes.new("ShaderNodeObjectInfo")
    info.location = (-470, -620)
    tint = nt.nodes.new("ShaderNodeValToRGB")
    tint.location = (-250, -620)
    cr = tint.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.10, 0.30, 0.60, 1)     # cold cyan
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.62, 0.36, 0.12, 1)     # warm tungsten
    e = cr.elements.new(0.6)
    e.color = (0.52, 0.09, 0.32, 1)                  # magenta
    L.new(info.outputs["Random"], tint.inputs["Fac"])

    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (560, 180)
    L.new(tint.outputs["Color"], em.inputs["Color"])
    L.new(strength.outputs["Value"], em.inputs["Strength"])

    add = nt.nodes.new("ShaderNodeAddShader")
    add.location = (880, 0)
    L.new(bsdf.outputs["BSDF"], add.inputs[0])
    L.new(em.outputs["Emission"], add.inputs[1])
    L.new(add.outputs["Shader"], out.inputs["Surface"])
    return mat


def screen_material(name, color_a, color_b, strength=5.0):
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
    wave.inputs["Scale"].default_value = 2.0
    if "Distortion" in wave.inputs:
        wave.inputs["Distortion"].default_value = 3.0
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
    (0.00, 0.85, 1.00),   # cyan
    (1.00, 0.05, 0.55),   # magenta
    (0.50, 0.08, 1.00),   # violet
    (0.10, 1.00, 0.40),   # acid green
    (1.00, 0.38, 0.03),   # amber
    (0.15, 0.40, 1.00),   # electric blue
]

# ======================================================================
# BUILD THE CITY
# ======================================================================
clear_scene()
scene = bpy.context.scene

BUILDING_MATS = [facade_material(f"Facade_{i}", window_strength=s)
                 for i, s in enumerate((4.5, 7.0, 5.5))]
ROOF_MAT = pbr_mat("RoofDeck", (0.018, 0.019, 0.024), roughness=0.8, metallic=0.2)
STRIP_MATS = [emission_mat(f"NeonStrip_{i}", c, strength=9.0)
              for i, c in enumerate(NEON)]
BAND_MATS = [emission_mat(f"NeonBand_{i}", c, strength=5.0)
             for i, c in enumerate(NEON)]


def two_tone_facade(obj, facade, roof):
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
        cube("Strip", (0.12, 0.12, h * RNG.uniform(0.55, 0.98)),
             (x + sx * (w / 2 + 0.02), y + sy * (d / 2 + 0.02),
              h * RNG.uniform(0.5, 0.62)), mat=strip_mat)

    # glowing crown band
    cube("Band", (w * 1.02, d * 1.02, RNG.uniform(0.18, 0.42)),
         (x, y, h * RNG.uniform(0.82, 0.95)), mat=RNG.choice(BAND_MATS))

    if h > 30 and RNG.random() < 0.5:
        cylinder("Antenna", 0.16, RNG.uniform(4, 11),
                 (x + RNG.uniform(-w / 3, w / 3), y + RNG.uniform(-d / 3, d / 3),
                  h + RNG.uniform(2, 5.5)), mat=ROOF_MAT, verts=8)
        sphere("AntennaTip", 0.22, (x, y, h + RNG.uniform(6, 10)),
               mat=emission_mat("TipRed", (1.0, 0.10, 0.12), 14.0),
               segments=8, rings=6)
    return obj


def build_city(cells=6, cell=19.0, hero_clear=27.0, corridor=68.0):
    for ix in range(-cells, cells + 1):
        for iy in range(-cells, cells + 1):
            x = ix * cell + RNG.uniform(-1.6, 1.6)
            y = iy * cell + RNG.uniform(-1.6, 1.6)
            dist = math.hypot(x, y)
            if dist < hero_clear:
                continue
            w = min(RNG.uniform(8.5, 14.5), cell - 5.0)
            d = min(RNG.uniform(8.5, 14.5), cell - 5.0)
            h = RNG.uniform(16, 46) * (1.0 + 1.15 * math.exp(-dist / 70.0))
            if dist < corridor:
                h = min(h, 44.0)
            add_building(x, y, w, d, h)

    for ang, radius, w, d, h in ((12, 100, 18, 18, 120), (105, 92, 15, 15, 98),
                                 (198, 96, 20, 16, 132), (287, 88, 14, 14, 90)):
        a = math.radians(ang)
        add_building(radius * math.cos(a), radius * math.sin(a), w, d, h)


def build_billboards():
    specs = [
        (-62, -56, math.radians(38), 26, 15, (0.02, 0.7, 1.0), (0.45, 0.02, 1.0)),
        (72, -34, math.radians(-120), 22, 13, (1.0, 0.05, 0.45), (1.0, 0.45, 0.05)),
        (-22, 88, math.radians(200), 30, 17, (0.35, 0.02, 1.0), (0.05, 0.8, 0.6)),
    ]
    for i, (x, y, rot, w, h, ca, cb) in enumerate(specs):
        mat = screen_material(f"Billboard_{i}", ca, cb, strength=4.0)
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
ROOF_H = 40.0
SLAB = 0.35
ROOF_Z = ROOF_H + SLAB
ROOF_HALF = 8.0          # hero tower footprint is 16 x 16 m
PARAPET_H = 0.95


def build_rooftop():
    """16x16 roof box: parapet with neon cap, AC units, access hut, mast and
    the TRACEORA sign standing on the front edge."""
    tower = cube("HeroTower", (16, 16, ROOF_H), (0, 0, ROOF_H / 2))
    two_tone_facade(tower, BUILDING_MATS[1], ROOF_MAT)

    cube("RoofSlab", (16.7, 16.7, SLAB), (0, 0, ROOF_H + SLAB / 2),
         mat=pbr_mat("RoofSlabMat", (0.020, 0.021, 0.028), roughness=0.35,
                     metallic=0.4))

    # parapet walls around the edge
    wall_mat = pbr_mat("Parapet", (0.028, 0.029, 0.036), roughness=0.5,
                       metallic=0.3)
    for i, (dx, dy, sx, sy) in enumerate(((0, 1, 1, 0), (0, -1, 1, 0),
                                          (1, 0, 0, 1), (-1, 0, 0, 1))):
        cube(f"Parapet_{i}",
             (16.4 if sx else 0.32, 16.4 if sy else 0.32, PARAPET_H),
             (dx * 8.05, dy * 8.05, ROOF_Z + PARAPET_H / 2), mat=wall_mat)

    # neon cap running along the top of the parapet
    rim_mat = emission_mat("RimCyan", (0.05, 0.80, 1.0), strength=12.0, hero=True)
    for i, (dx, dy, sx, sy) in enumerate(((0, 1, 1, 0), (0, -1, 1, 0),
                                          (1, 0, 0, 1), (-1, 0, 0, 1))):
        cube(f"Rim_{i}", (16.3 if sx else 0.14, 16.3 if sy else 0.14, 0.09),
             (dx * 8.05, dy * 8.05, ROOF_Z + PARAPET_H + 0.02), mat=rim_mat)

    # magenta floor strips washing the deck
    floor_mat = emission_mat("RimMagenta", (1.0, 0.06, 0.5), strength=10.0,
                             hero=True)
    for i, dx in enumerate((-1, 1)):
        cube(f"FloorStrip_{i}", (0.14, 12.0, 0.06),
             (dx * 5.6, 1.4, ROOF_Z + 0.04), mat=floor_mat)

    # rooftop machinery
    ac_mat = pbr_mat("ACMat", (0.04, 0.042, 0.05), roughness=0.55, metallic=0.5)
    for i, (px, py, dims) in enumerate(((5.1, -4.9, (2.6, 1.9, 1.15)),
                                        (-5.0, 5.2, (2.0, 2.9, 0.95)),
                                        (5.3, 5.1, (2.2, 2.2, 1.35)))):
        body = cube(f"AC_{i}", dims, (px, py, ROOF_Z + dims[2] / 2), mat=ac_mat)
        apply_scale(body)
        add_bevel(body, 0.05, 2)
        cube(f"ACVent_{i}", (dims[0] * 0.72, dims[1] * 0.72, 0.05),
             (px, py, ROOF_Z + dims[2] + 0.02),
             mat=emission_mat(f"ACGlow_{i}", (0.10, 0.80, 1.0), 2.6))

    # stair / access hut in the back-left corner with a lit door frame
    hut = cube("Hut", (3.4, 2.8, 2.5), (-5.4, -4.9, ROOF_Z + 1.25),
               mat=pbr_mat("HutMat", (0.05, 0.05, 0.058), roughness=0.6,
                           metallic=0.35))
    apply_scale(hut)
    add_bevel(hut, 0.04, 2)
    cube("HutDoor", (0.9, 0.06, 1.9), (-4.7, -6.32, ROOF_Z + 0.95),
         mat=emission_mat("HutDoorGlow", (0.9, 0.45, 0.15), 2.2))

    # mast with a red beacon
    mast_mat = pbr_mat("Mast", (0.05, 0.05, 0.06), roughness=0.4, metallic=0.8)
    cylinder("Mast", 0.16, 7.5, (6.6, -6.2, ROOF_Z + 3.75), mat=mast_mat, verts=10)
    sphere("MastBeacon", 0.26, (6.6, -6.2, ROOF_Z + 7.6),
           mat=emission_mat("Beacon", (1.0, 0.12, 0.16), 12.0))

    # TRACEORA neon sign on the front parapet
    sign_mat = emission_mat("SignMagenta", (1.0, 0.10, 0.55), strength=7.0,
                            hero=True)
    frame_mat = pbr_mat("SignFrame", (0.02, 0.02, 0.025), roughness=0.5,
                        metallic=0.7)
    bpy.ops.object.text_add(location=(0, -8.28, ROOF_Z + 0.55))
    txt = bpy.context.object
    txt.name = "SignText"
    txt.data.body = "TRACEORA"
    txt.data.align_x = "CENTER"
    txt.data.align_y = "CENTER"
    txt.data.size = 1.9
    txt.data.extrude = 0.09
    txt.rotation_euler = (math.radians(90), 0, 0)
    txt.data.materials.append(sign_mat)
    activate(txt)
    bpy.ops.object.convert(target="MESH")

    cube("SignBack", (12.6, 0.30, 2.7), (0, -8.55, ROOF_Z + 1.75), mat=frame_mat)
    for i, sx in enumerate((-1, 1)):
        cube(f"SignPost_{i}", (0.22, 0.22, 2.6), (sx * 5.4, -8.5, ROOF_Z + 1.3),
             mat=frame_mat)


build_rooftop()

# ======================================================================
# HERO CAR
# ======================================================================
CAR_Z = ROOF_Z


def build_car():
    paint = pbr_mat("CarPaint", (0.012, 0.013, 0.017), roughness=0.10,
                    metallic=1.0)
    glass = pbr_mat("CarGlass", (0.015, 0.025, 0.04), roughness=0.02,
                    metallic=0.5)
    rubber = pbr_mat("CarRubber", (0.006, 0.006, 0.008), roughness=0.85,
                     metallic=0.0)
    chrome = pbr_mat("CarChrome", (0.5, 0.54, 0.62), roughness=0.14,
                     metallic=1.0)
    underglow = emission_mat("CarUnderglow", (0.55, 0.03, 1.0), strength=12.0,
                             hero=True)
    head = emission_mat("CarHeadlight", (0.55, 0.85, 1.0), strength=30.0,
                        hero=True)
    tail = emission_mat("CarTail", (1.0, 0.05, 0.3), strength=24.0, hero=True)

    parts = []
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

    for wx in (-1.42, 1.42):
        for wy in (-0.93, 0.93):
            parts.append(cylinder("Tyre", 0.44, 0.30, (wx, wy, CAR_Z + 0.44),
                                  rot=(math.radians(90), 0, 0), mat=rubber,
                                  verts=28))
            parts.append(cylinder("Rim", 0.26, 0.34, (wx, wy, CAR_Z + 0.44),
                                  rot=(math.radians(90), 0, 0),
                                  mat=emission_mat("RimGlow",
                                                   RNG.choice([(0.1, 0.85, 1.0),
                                                               (1.0, 0.08, 0.5)]),
                                                   9.0, hero=True), verts=20))

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
CAR_TOP = CAR_Z + 1.50

# ======================================================================
# SEATED MAN
# ======================================================================
def build_seated_man(base_z):
    jacket = pbr_mat("ManJacket", (0.022, 0.024, 0.03), roughness=0.5,
                     metallic=0.2)
    pants = pbr_mat("ManPants", (0.035, 0.038, 0.048), roughness=0.7,
                    metallic=0.05)
    skin = pbr_mat("ManSkin", (0.40, 0.26, 0.20), roughness=0.5, metallic=0.0)
    hair = pbr_mat("ManHair", (0.015, 0.014, 0.016), roughness=0.75,
                   metallic=0.1)
    trim = emission_mat("ManTrim", (1.0, 0.08, 0.5), strength=10.0, hero=True)
    boot = pbr_mat("ManBoot", (0.012, 0.012, 0.015), roughness=0.4,
                   metallic=0.3)

    parts = []
    parts.append(cube("Pelvis", (0.42, 0.44, 0.22), (0.0, 0.0, base_z + 0.11),
                      mat=pants))
    parts.append(cube("Torso", (0.40, 0.48, 0.62), (0.06, 0.0, base_z + 0.52),
                      rot=(0, math.radians(9), 0), mat=jacket))
    parts.append(cube("Zip", (0.03, 0.05, 0.56), (0.27, 0.0, base_z + 0.52),
                      rot=(0, math.radians(9), 0), mat=trim))
    parts.append(cube("Collar", (0.30, 0.40, 0.09), (0.14, 0.0, base_z + 0.84),
                      mat=trim))
    parts.append(cylinder("Neck", 0.075, 0.13, (0.13, 0.0, base_z + 0.92),
                          mat=skin, verts=12))
    parts.append(sphere("Head", 0.145, (0.15, 0.0, base_z + 1.06), mat=skin))
    hair_obj = sphere("Hair", 0.152, (0.11, 0.0, base_z + 1.10), mat=hair)
    hair_obj.scale = (1.0, 1.0, 0.85)
    parts.append(hair_obj)

    for side in (-0.13, 0.13):
        parts.append(cube("Thigh", (0.52, 0.17, 0.17),
                          (0.30, side, base_z + 0.11), mat=pants))
        parts.append(cube("Shin", (0.17, 0.16, 0.56),
                          (0.55, side, base_z - 0.24),
                          rot=(0, math.radians(-12), 0), mat=pants))
        parts.append(cube("Boot", (0.30, 0.16, 0.13),
                          (0.62, side, base_z - 0.55), mat=boot))
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
seated_man.rotation_euler = (0, 0, math.radians(-14))

# ======================================================================
# WORLD + HAZE
# ======================================================================
world = bpy.data.worlds.new("CyberWorld")
scene.world = world
world.use_nodes = True
WNT = world.node_tree
WNT.nodes.clear()
wout = WNT.nodes.new("ShaderNodeOutputWorld")
wout.location = (400, 0)
wbg = WNT.nodes.new("ShaderNodeBackground")
wbg.location = (150, 160)
wbg.inputs["Strength"].default_value = 1.25

# dusk gradient: deep indigo zenith, magenta/amber light-pollution haze on the
# horizon so the skyline has something to sit against.
wtc = WNT.nodes.new("ShaderNodeTexCoord")
wtc.location = (-700, 300)
wsep = WNT.nodes.new("ShaderNodeSeparateXYZ")
wsep.location = (-520, 300)
WNT.links.new(wtc.outputs["Generated"], wsep.inputs["Vector"])
wramp = WNT.nodes.new("ShaderNodeValToRGB")
wramp.location = (-320, 300)
wcr = wramp.color_ramp
wcr.elements[0].position = 0.30
wcr.elements[0].color = (0.004, 0.005, 0.015, 1)
wcr.elements[1].position = 0.62
wcr.elements[1].color = (0.055, 0.035, 0.090, 1)
mid = wcr.elements.new(0.49)
mid.color = (0.11, 0.045, 0.085, 1)       # light pollution at horizon
horizon = wcr.elements.new(0.455)
horizon.color = (0.21, 0.075, 0.115, 1)
WNT.links.new(wsep.outputs["Z"], wramp.inputs["Fac"])
WNT.links.new(wramp.outputs["Color"], wbg.inputs["Color"])
WNT.links.new(wbg.outputs["Background"], wout.inputs["Surface"])

HAZE = WNT.nodes.new("ShaderNodeVolumeScatter")
HAZE.location = (150, -160)
HAZE.inputs["Color"].default_value = (0.34, 0.42, 0.75, 1.0)
HAZE.inputs["Density"].default_value = 0.0016
if "Anisotropy" in HAZE.inputs:
    HAZE.inputs["Anisotropy"].default_value = 0.55


def set_haze(density):
    """0 disables the world volume entirely (big Cycles speed win)."""
    for link in list(WNT.links):
        if link.to_socket == wout.inputs["Volume"]:
            WNT.links.remove(link)
    if density > 0:
        HAZE.inputs["Density"].default_value = density
        WNT.links.new(HAZE.outputs["Volume"], wout.inputs["Volume"])
    print(f"[scene] haze density = {density}")


def set_emission_sampling(mode):
    """'auto' every emitter is a real light, 'none' none of them are,
    'hero' only the handful that light the hero shot are."""
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        if mode == "auto":
            sample = True
        elif mode == "none":
            sample = False
        else:
            sample = mat.name.startswith(HERO_EMITTERS)
        try:
            mat.cycles.emission_sampling = "AUTO" if sample else "NONE"
        except Exception:
            pass
    print(f"[scene] emission sampling = {mode}")


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
    from mathutils import Vector
    obj.rotation_euler = Vector((target[0] - loc[0], target[1] - loc[1],
                                 target[2] - loc[2])).to_track_quat(
        "-Z", "Y").to_euler()
    scene.collection.objects.link(obj)
    return obj


add_area("KeyMagenta", (5.5, -6.5, CAR_Z + 3.4), (1.0, 0.32, 0.70), 820, 4.0)
add_area("RimCyan", (-6.5, 6.5, CAR_Z + 3.0), (0.20, 0.80, 1.0), 1500, 3.5)
add_area("FillViolet", (7.5, 7.0, CAR_Z + 2.0), (0.48, 0.24, 1.0), 430, 6.0)
add_area("TopFill", (0.0, 0.0, CAR_Z + 7.0), (0.55, 0.72, 1.0), 520, 8.0,
         target=(0, 0, CAR_Z))
# tight kicker so the man's face/silhouette reads against the skyline
add_area("FaceKicker", (2.6, -3.4, CAR_TOP + 1.4), (0.75, 0.90, 1.0), 150, 1.4,
         target=(0.2, 0.0, CAR_TOP + 0.9))

sun_data = bpy.data.lights.new("MoonSun", type="SUN")
sun_data.energy = 0.35
sun_data.color = (0.40, 0.52, 1.0)
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

focus = bpy.data.objects.new("FocusTarget", None)
focus.location = (0.0, 0.0, CAR_TOP + 0.9)
scene.collection.objects.link(focus)
cam_data.dof.use_dof = True
cam_data.dof.focus_object = focus
cam_data.dof.aperture_fstop = 4.0

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
    """Slow descending drone arc from a wide establishing view to a close
    three-quarter of the car + man."""
    e = smoothstep(t)
    angle = math.radians(200.0 + (350.0 - 200.0) * e)
    radius = 56.0 - 39.5 * e
    height = CAR_Z + 21.0 - 17.6 * e
    angle += math.radians(1.4 * math.sin(t * math.pi * 2.1))
    height += 0.5 * math.sin(t * math.pi * 3.3)
    radius += 0.8 * math.sin(t * math.pi * 2.7)
    loc = Vector((radius * math.cos(angle), radius * math.sin(angle), height))
    target = Vector((0.0, 0.0, CAR_Z + 1.0 + 1.1 * (1.0 - e)))
    return loc, target


PATH_KEYS = 30
for i in range(PATH_KEYS):
    t = i / (PATH_KEYS - 1)
    frame = SHOT_START + round(t * (SHOT_END - SHOT_START))
    loc, target = camera_pose(t)
    cam_obj.location = loc
    cam_obj.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    cam_obj.rotation_euler.rotate_axis("Z", math.radians(-2.2 * math.sin(t * math.pi)))
    cam_obj.keyframe_insert(data_path="location", frame=frame)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame)

# ======================================================================
# RENDER SETTINGS
# ======================================================================
scene.render.resolution_x = RES_X
scene.render.resolution_y = RES_Y
scene.render.resolution_percentage = ARGS.percent
scene.render.fps = 24
scene.frame_start = SHOT_START
scene.frame_end = SHOT_END
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGB"
scene.render.image_settings.color_depth = "8"
scene.render.film_transparent = False
scene.render.use_file_extension = False  # explicit *.png paths are passed in
scene.render.use_persistent_data = True
scene.render.filepath = os.path.join(ARGS.out, "frame_")

for vt in ("AgX", "Filmic", "Standard"):
    try:
        scene.view_settings.view_transform = vt
        break
    except Exception:
        continue
for look in ("AgX - Punchy", "AgX - Medium High Contrast"):
    try:
        scene.view_settings.look = look
        break
    except Exception:
        continue
try:
    scene.view_settings.exposure = 0.45
except Exception:
    pass


def configure_cycles():
    scene.render.engine = "CYCLES"
    cy = scene.cycles
    cy.device = "CPU"
    cy.samples = ARGS.samples
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = 0.015
    cy.use_denoising = True
    for denoiser in ("OPENIMAGEDENOISE", "OPTIX"):
        try:
            cy.denoiser = denoiser
            break
        except Exception:
            continue
    cy.max_bounces = 4
    cy.diffuse_bounces = 2
    cy.glossy_bounces = 2
    cy.transmission_bounces = 1
    cy.volume_bounces = 1
    cy.transparent_max_bounces = 4
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = 1.0
    cy.sample_clamp_indirect = 8.0
    cy.use_light_tree = True
    try:
        cy.volume_step_rate = 4.0
        cy.volume_max_steps = 32
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
                      ("volumetric_samples", 32),
                      ("use_raytracing", True)):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
    try:
        ee.use_bloom = True
        ee.bloom_threshold = 0.8
        ee.bloom_intensity = 0.05
        ee.bloom_radius = 7.0
    except Exception:
        pass


def configure_glare():
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
                          ("threshold", 0.8), ("size", 7), ("mix", -0.3)):
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
        print(f"[glare] unavailable ({exc}); relying on post bloom")


def apply_profile(name):
    """Quality profiles that trade atmospherics for render speed."""
    if name == "full":
        set_haze(0.006)
        set_emission_sampling("auto")
    elif name == "thin":
        set_haze(0.0016)
        set_emission_sampling("auto")
    elif name == "thin_hero":
        set_haze(0.0016)
        set_emission_sampling("hero")
    elif name == "none":
        set_haze(0.0)
        set_emission_sampling("hero")
    elif name == "none_auto":
        set_haze(0.0)
        set_emission_sampling("auto")
    else:
        raise SystemExit(f"unknown profile: {name}")


print(f"[scene] engine requested: {ARGS.engine}, profile: {ARGS.profile}")
if ARGS.engine == "eevee":
    configure_eevee()
else:
    configure_cycles()
if ARGS.glare:
    configure_glare()
apply_profile(ARGS.profile)
scene.frame_set(FRAME_START)

# ======================================================================
# STATS + OPTIONAL RENDER
# ======================================================================
objs = len(scene.objects)
faces = sum(len(o.data.polygons) for o in scene.objects if o.type == "MESH")
print(f"[scene] {objs} objects, {faces} faces, shot {SHOT_START}-{SHOT_END}, "
      f"rendering {FRAME_START}-{FRAME_END}, "
      f"{scene.render.resolution_x}x{scene.render.resolution_y}")
print(f"[scene] engine: {scene.render.engine}, samples: {ARGS.samples}")


def image_stats(path):
    """Cheap sanity metrics so CI can prove a frame is not black/blown out."""
    try:
        import numpy as np
        img = bpy.data.images.load(path, check_existing=False)
        px = np.array(img.pixels[:], dtype="float32").reshape(-1, img.channels)
        rgb = px[:, :3]
        bpy.data.images.remove(img)
        hi = float((rgb.max(axis=1) > 0.6).mean() * 100.0)
        lo = float((rgb.max(axis=1) < 0.02).mean() * 100.0)
        return (f"mean={rgb.mean():.4f} p50={np.percentile(rgb, 50):.3f} "
                f"p99={np.percentile(rgb, 99):.3f} bright={hi:.2f}% dark={lo:.2f}%")
    except Exception as exc:  # pragma: no cover
        return f"stats unavailable ({exc})"


def render_still(frame, path):
    scene.frame_set(frame)
    scene.render.filepath = path
    t0 = time.time()
    bpy.ops.render.render(write_still=True)
    return time.time() - t0


out_dir = os.path.abspath(ARGS.out)

if ARGS.variants:
    os.makedirs(out_dir, exist_ok=True)
    variants = ["none_auto", "none", "thin_hero", "thin", "full"]
    for name in variants:
        apply_profile(name)
        path = os.path.join(out_dir, f"variant_{name}.png")
        try:
            secs = render_still(FRAME_START, path)
            print(f"[variant] {name} {secs:.1f}s {image_stats(path)}", flush=True)
        except Exception as exc:  # pragma: no cover
            print(f"[variant] {name} FAILED: {exc}", flush=True)
    apply_profile(ARGS.profile)
elif ARGS.render:
    os.makedirs(out_dir, exist_ok=True)
    total = FRAME_END - FRAME_START + 1
    t_start = time.time()
    for i, frame in enumerate(range(FRAME_START, FRAME_END + 1), start=1):
        path = os.path.join(out_dir, f"frame_{frame:04d}.png")
        secs = render_still(frame, path)
        done = time.time() - t_start
        eta = (done / i) * (total - i)
        print(f"[render] frame {frame} ({i}/{total}) {secs:.1f}s "
              f"elapsed {done / 60:.1f}m eta {eta / 60:.1f}m", flush=True)
        print(f"[stats] frame {frame} {image_stats(path)}", flush=True)
    print(f"[render] done in {(time.time() - t_start) / 60:.2f} min -> {out_dir}")
else:
    print("[scene] build only (pass --render to render frames)")
