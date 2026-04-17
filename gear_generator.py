# gear_generator.py
import bpy
import bmesh
import math

bl_info = {
    "name": "Parametric Gear Generator",
    "author": "Du + Grok",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Erstellen",
    "description": "Erstellt parametrische Zahnräder mit GUI im N-Panel",
    "category": "Add Mesh",
}


# ================================================================
# PROPERTIES (werden in der Szene gespeichert)
# ================================================================
def register_properties():
    bpy.types.Scene.gear_radius = bpy.props.FloatProperty(
        name="Radius (Teilkreis)",
        description="Teilkreisradius des Zahnrads",
        default=1.0,
        min=0.1,
        unit='LENGTH'
    )
    bpy.types.Scene.gear_teeth = bpy.props.IntProperty(
        name="Anzahl Zähne",
        description="Wie viele Zähne das Rad haben soll",
        default=24,
        min=6,
        max=200
    )
    bpy.types.Scene.gear_thickness = bpy.props.FloatProperty(
        name="Dicke",
        description="Dicke des Zahnrads",
        default=0.3,
        min=0.01,
        unit='LENGTH'
    )
    bpy.types.Scene.gear_tooth_depth = bpy.props.FloatProperty(
        name="Zahntiefe",
        description="Höhe eines Zahns (von Fuß bis Kopf)",
        default=0.25,
        min=0.05,
        unit='LENGTH'
    )


def unregister_properties():
    del bpy.types.Scene.gear_radius
    del bpy.types.Scene.gear_teeth
    del bpy.types.Scene.gear_thickness
    del bpy.types.Scene.gear_tooth_depth


# ================================================================
# MESH ERSTELLUNG (verbesserte Zahnrad-Geometrie)
# ================================================================
def create_gear_obj(radius=1.0, teeth=24, thickness=0.3, tooth_depth=0.25):
    mesh = bpy.data.meshes.new("Zahnrad")
    obj = bpy.data.objects.new("Zahnrad", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # Radien berechnen
    pitch_radius = radius
    root_radius = pitch_radius - tooth_depth * 0.6
    tip_radius = pitch_radius + tooth_depth * 0.4

    tooth_angle = 2 * math.pi / teeth
    half_pitch = math.pi / teeth

    # Trapez-Zahn: breiter am Fuß, schmaler am Kopf
    half_root = half_pitch * 0.55
    half_tip = half_pitch * 0.35

    verts_list = []

    for i in range(teeth):
        ang = i * tooth_angle

        # Reihenfolge wichtig für geschlossenes Polygon (gegen Uhrzeigersinn)
        # Links Fuß → Links Kopf → Rechts Kopf → Rechts Fuß
        verts_list.append(bm.verts.new((
            root_radius * math.cos(ang - half_root),
            root_radius * math.sin(ang - half_root),
            0.0
        )))
        verts_list.append(bm.verts.new((
            tip_radius * math.cos(ang - half_tip),
            tip_radius * math.sin(ang - half_tip),
            0.0
        )))
        verts_list.append(bm.verts.new((
            tip_radius * math.cos(ang + half_tip),
            tip_radius * math.sin(ang + half_tip),
            0.0
        )))
        verts_list.append(bm.verts.new((
            root_radius * math.cos(ang + half_root),
            root_radius * math.sin(ang + half_root),
            0.0
        )))

    # Ein einziges Face für das komplette Zahnrad-Profil
    bm.faces.new(verts_list)

    # Extrudieren für 3D-Dicke
    extrude_result = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    new_verts = [el for el in extrude_result['geom'] if isinstance(el, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=new_verts)

    bm.to_mesh(mesh)
    bm.free()

    # Objekt aktivieren
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


# ================================================================
# OPERATOR
# ================================================================
class MESH_OT_create_gear(bpy.types.Operator):
    """Erstellt ein parametrisches Zahnrad"""
    bl_idname = "mesh.create_gear"
    bl_label = "Zahnrad erstellen"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        create_gear_obj(
            radius=scene.gear_radius,
            teeth=scene.gear_teeth,
            thickness=scene.gear_thickness,
            tooth_depth=scene.gear_tooth_depth
        )
        self.report({'INFO'}, f"Zahnrad mit {scene.gear_teeth} Zähnen erstellt!")
        return {'FINISHED'}


# ================================================================
# PANEL (N-Panel)
# ================================================================
class VIEW3D_PT_gear_generator(bpy.types.Panel):
    """Zahnrad Generator im Sidebar"""
    bl_label = "Zahnrad Generator"
    bl_idname = "VIEW3D_PT_gear_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Erstellen"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Parameter:", icon='MOD_ARRAY')
        layout.prop(scene, "gear_radius")
        layout.prop(scene, "gear_teeth")
        layout.prop(scene, "gear_thickness")
        layout.prop(scene, "gear_tooth_depth")

        layout.separator()
        layout.operator("mesh.create_gear", icon='MESH_CIRCLE')


# ================================================================
# REGISTER / UNREGISTER
# ================================================================
def register():
    register_properties()
    bpy.utils.register_class(MESH_OT_create_gear)
    bpy.utils.register_class(VIEW3D_PT_gear_generator)


def unregister():
    unregister_properties()
    bpy.utils.unregister_class(MESH_OT_create_gear)
    bpy.utils.unregister_class(VIEW3D_PT_gear_generator)


if __name__ == "__main__":
    register()
