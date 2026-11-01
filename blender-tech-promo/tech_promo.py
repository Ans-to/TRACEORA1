"""Vertical 15-second Blender tech promo. Render with: blender -b -t 2 --python tech_promo.py -- --render"""
import bpy
import bmesh
import math
import sys
from pathlib import Path

# CONFIGURATION — faithfully adapted from the supplied script.
RESOLUTION_X, RESOLUTION_Y, FPS = 1080, 1920, 30
FRAME_START, FRAME_END = 1, 450
OUTPUT_FILEPATH = str(Path(__file__).resolve().parent / 'render' / 'tech_promo_15s.mp4')
COLOR_BACKGROUND = (.03, .03, .05, 1)
COLOR_PRIMARY = (.10, .65, 1, 1)
COLOR_ACCENT = (1, .25, .45, 1)
COLOR_SUCCESS = (.20, .90, .45, 1)
COLOR_PANEL_DARK = (.08, .08, .10, 1)
COLOR_TEXT_MAIN = (1, 1, 1, 1)
VOICEOVER_LINES = {
    'scene_1': 'Stop writing boring Python scripts by hand.',
    'scene_2': 'Just describe the task.',
    'scene_3': 'The agent writes it, tests it, and runs it.',
    'scene_4': 'Rename files, clean data, export reports, done in seconds.',
    'scene_5': 'Try your first automation free today.',
}
CAPTIONS = [
    'Manual Python = slow',
    'Describe it in plain English',
    'Write  >  Test  >  Run',
    'Done in seconds',
    'Try your first automation free  >',
]
SHOTS = [(1, 90), (91, 180), (181, 270), (271, 360), (361, 450)]


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)


def emission(name, color, strength=1):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    em = nodes.new('ShaderNodeEmission')
    em.inputs['Color'].default_value = color
    em.inputs['Strength'].default_value = strength
    mat.node_tree.links.new(em.outputs[0], out.inputs['Surface'])
    return mat


def visible_in(obj, first, last, reveal=8):
    """Hide each shot's elements before/after its time; scale reveal within the shot."""
    if first > 1:
        obj.scale = (0, 0, 0)
        obj.keyframe_insert(data_path='scale', frame=first-1)
    obj.scale = (0, 0, 0)
    obj.keyframe_insert(data_path='scale', frame=first)
    obj.scale = (1, 1, 1)
    obj.keyframe_insert(data_path='scale', frame=first+reveal)
    obj.keyframe_insert(data_path='scale', frame=last)
    if last < FRAME_END:
        obj.scale = (0, 0, 0)
        obj.keyframe_insert(data_path='scale', frame=last+1)
    if obj.animation_data and obj.animation_data.action:
        # Blender 4.x action API; 5.x may have layered actions without .fcurves.
        for curve in getattr(obj.animation_data.action, 'fcurves', []):
            for key in curve.keyframe_points:
                key.interpolation = 'SINE'
    return obj


def text(name, body, x, z, size, shot, color=COLOR_TEXT_MAIN, align='CENTER', depth=-.13):
    curve = bpy.data.curves.new(name, 'FONT')
    curve.body = body
    curve.size = size
    curve.align_x = align
    curve.align_y = 'CENTER'
    curve.space_character = 1.1
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    # Font faces camera at negative Y; the original script left it edge-on.
    obj.rotation_euler = (math.pi/2, 0, 0)
    obj.location = (x, depth, z)
    curve.materials.append(emission(name+'_glow', color, 1.3))
    return visible_in(obj, *SHOTS[shot], reveal=8)


def panel(name, x, z, width, height, shot, mat, depth=.10):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(-width/2, -height/2, 0), (width/2, -height/2, 0),
                      (width/2, height/2, 0), (-width/2, height/2, 0)],
                     [], [(0, 1, 2, 3)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = (math.pi/2, 0, 0)
    obj.location = (x, depth, z)
    mesh.materials.append(mat)
    return visible_in(obj, *SHOTS[shot], reveal=8)


def circle(name, x, z, radius, shot, color, depth=-.04):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=64)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.rotation_euler = (math.pi/2, 0, 0)
    obj.location = (x, depth, z)
    mesh.materials.append(emission(name+'_mat', color, 1.5))
    return visible_in(obj, *SHOTS[shot], reveal=15)


def setup():
    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items.keys() else 'BLENDER_EEVEE'
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION_X, RESOLUTION_Y
    scene.render.resolution_percentage = 100
    scene.render.fps, scene.frame_start, scene.frame_end = FPS, FRAME_START, FRAME_END
    # Blender 5 on GitHub runners is built without its FFmpeg image output.
    # Render lossless PNG frames; the workflow muxes them into H.264.
    scene.render.image_settings.file_format = 'PNG'
    scene.render.filepath = str(Path(OUTPUT_FILEPATH).parent / 'frames' / 'frame_')
    scene.render.film_transparent = False
    world = bpy.data.worlds.new('Night / navy background')
    world.use_nodes = True
    world.node_tree.nodes.get('Background').inputs[0].default_value = COLOR_BACKGROUND
    scene.world = world
    cam_data = bpy.data.cameras.new('Portrait camera')
    cam = bpy.data.objects.new('Portrait camera', cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0, -12, 0)
    cam.rotation_euler = (math.pi/2, 0, 0)
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = 10.2  # visible width 5.74, height 10.2
    scene.camera = cam
    return scene


def build():
    scene = setup()
    blue = emission('Electric blue', COLOR_PRIMARY, 1.3)
    pink = emission('Action pink', COLOR_ACCENT, 1.5)
    green = emission('Success green', COLOR_SUCCESS, 1.3)
    dark = emission('Console card', COLOR_PANEL_DARK)
    text('TopLabel', 'AUTOMATION  /  001', 0, 4.30, .18, 0, COLOR_PRIMARY)
    for s in range(5):
        text('Series_'+str(s), 'TECH PROMO   /   %02d' % (s+1), 0, 4.36, .16, s, COLOR_PRIMARY)
        # Captions sit safely inside portrait frame; font auto-fit for long copy.
        size = .31 if len(CAPTIONS[s]) > 31 else .39
        text('Caption_'+str(s), CAPTIONS[s], 0, -4.38, size, s,
             COLOR_ACCENT if s in (0,4) else COLOR_SUCCESS if s in (2,3) else COLOR_PRIMARY)
    # 1 / HOOK: manual, messy terminal windows.
    text('Scene1_Title', 'STOP THE BUSYWORK', 0, 3.0, .43, 0)
    for i, string in enumerate(('> rename_001.py', 'for file in files:', '  # still debugging...')):
        panel('Terminal_'+str(i), 0, 1.55-i*.85, 4.45, .69, 0, dark)
        text('Code_'+str(i), string, -1.94, 1.55-i*.85, .24, 0,
             COLOR_ACCENT if i == 2 else COLOR_TEXT_MAIN, 'LEFT', depth=-.16)
    text('Scene1_Foot', 'SCRIPTS SHOULD NOT TAKE ALL DAY', 0, -2.1, .27, 0)
    # 2 / REVEAL: prompt -> AI core.
    text('Scene2_Title', 'JUST DESCRIBE IT', 0, 3.0, .49, 1)
    panel('PromptBox', 0, .67, 4.7, 1.48, 1, dark)
    text('PromptLabel', 'YOUR REQUEST', -1.92, 1.13, .18, 1, COLOR_PRIMARY, 'LEFT', -.18)
    text('PromptLine1', 'Rename 500 files', -1.92, .71, .33, 1, COLOR_TEXT_MAIN, 'LEFT', -.18)
    text('PromptLine2', 'and export CSV', -1.92, .24, .33, 1, COLOR_TEXT_MAIN, 'LEFT', -.18)
    circle('AI_Core', 0, -1.83, .67, 1, COLOR_PRIMARY)
    text('AI_Glyph', 'AI', 0, -1.83, .43, 1, COLOR_TEXT_MAIN, depth=-.23)
    # 3 / PROCESS: portrait-friendly vertically stacked cards.
    text('Scene3_Title', 'YOUR AGENT GETS TO WORK', 0, 3.08, .37, 2)
    for i, (label, note) in enumerate((('01  WRITE', 'Generate the script'),
                                       ('02  TEST', 'Check every step'),
                                       ('03  RUN', 'Finish the task'))):
        z = 1.61-i*1.61
        panel('ProcessCard_'+label, 0, z, 4.65, 1.26, 2, dark)
        panel('CardAccent_'+label, -2.19, z, .045, 1.03, 2,
              (blue, pink, green)[i], depth=-.04)
        text('ProcessLabel_'+label, label, -1.89, z+.18, .40, 2,
             (COLOR_PRIMARY, COLOR_ACCENT, COLOR_SUCCESS)[i], 'LEFT', -.19)
        text('ProcessNote_'+label, note, -1.89, z-.26, .22, 2,
             COLOR_TEXT_MAIN, 'LEFT', -.19)
    # 4 / RESULT: real visual proof, not persistent objects from earlier shots.
    text('Scene4_Title', 'FINISHED IN SECONDS', 0, 3.0, .45, 3)
    panel('ResultFiles', 0, 1.34, 4.65, 1.52, 3, dark)
    panel('ResultCSV', 0, -.61, 4.65, 1.52, 3, dark)
    text('Renamed', '500 FILES RENAMED', 0, 1.49, .42, 3, COLOR_SUCCESS)
    text('FileExample', 'image_001  ...  image_500', 0, 1.02, .22, 3)
    text('Report', 'CSV REPORT READY', 0, -.46, .42, 3, COLOR_SUCCESS)
    text('ReportExample', 'download  /  report.csv', 0, -.96, .23, 3)
    text('Timer', '00:08', 0, -2.36, .79, 3, COLOR_SUCCESS)
    # 5 / CTA: logo placeholder retained as in source.
    circle('Logo', 0, 1.85, .70, 4, COLOR_PRIMARY)
    text('LogoMark', '>', 0, 1.86, .64, 4, COLOR_TEXT_MAIN, depth=-.22)
    text('ProductName', '[PRODUCT NAME]', 0, .39, .53, 4)
    text('CallToAction', 'AUTOMATE THE BORING STUFF', 0, -.62, .30, 4)
    panel('Button', 0, -1.70, 3.38, .90, 4, pink)
    text('ButtonText', 'START FREE', 0, -1.70, .35, 4,
         COLOR_TEXT_MAIN, depth=-.20)
    return scene


if __name__ == '__main__':
    scene = build()
    if '--preview' in sys.argv:
        scene.frame_set(315)
        scene.render.image_settings.file_format = 'PNG'
        scene.render.filepath = str(Path(__file__).resolve().parent / 'render' / 'preview.png')
        bpy.ops.render.render(write_still=True)
    elif '--render' in sys.argv:
        (Path(OUTPUT_FILEPATH).parent / 'frames').mkdir(parents=True, exist_ok=True)
        bpy.ops.render.render(animation=True)
    else:
        print('Scene built. Pass -- --render to export the 15s MP4.')
