import bpy
import bmesh
import math

bl_info = {
    "name": "Parametric Evolvent Gear Generator",
    "author": "Du + KI-Assistent",
    "version": (3, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Erstellen",
    "description": "Erstellt Zahnraeder mit echter Evolventenverzahnung (DIN-konform).",
    "category": "Add Mesh",
}


# ================================================================
# EVOLVENTEN-MATHEMATIK (hochwertig, DIN-3960-konform)
# ================================================================

def inv(alpha):
    """Klassische Evolventenfunktion inv(alpha) = tan(alpha) - alpha."""
    return math.tan(alpha) - alpha


def involute_xy(base_radius, t):
    """
    Punkt auf der Evolvente des Grundkreises bei Abwickelparameter t.
    Achs-orientierte Form: Evolvente startet auf der x-Achse (t=0 -> (r_b, 0))
    und wickelt sich gegen den Uhrzeigersinn ab.
    """
    return (
        base_radius * (math.cos(t) + t * math.sin(t)),
        base_radius * (math.sin(t) - t * math.cos(t)),
    )


def involute_t_at_radius(base_radius, radius):
    """Abwickelparameter t, fuer den die Evolvente den gegebenen Radius erreicht."""
    ratio = radius / base_radius
    if ratio <= 1.0:
        return 0.0
    return math.sqrt(ratio * ratio - 1.0)


def rotate_xy(x, y, angle):
    c = math.cos(angle)
    s = math.sin(angle)
    return (x * c - y * s, x * s + y * c)


def build_tooth_flank(base_radius, start_radius, tip_radius, samples):
    """
    Erzeugt Punkte einer einzelnen Evolventenflanke vom Startradius bis zum Kopfkreis.
    Punkte sind in Achslage des Grundkreises (Evolvente startet bei (r_b, 0)).
    """
    t_start = involute_t_at_radius(base_radius, max(start_radius, base_radius))
    t_end = involute_t_at_radius(base_radius, tip_radius)
    if t_end <= t_start:
        return [involute_xy(base_radius, t_start)]
    pts = []
    for i in range(samples + 1):
        # Leicht verzerrte Verteilung -> dichter am Fuss, ohne Punkte zu duplizieren.
        u = i / samples
        t = t_start + (t_end - t_start) * (u ** 1.15)
        pts.append(involute_xy(base_radius, t))
    return pts


def build_root_fillet(involute_start, root_radius, fillet_samples):
    """
    Erzeugt einen tangentialen Kreisbogen-Fillet zwischen dem ersten Evolventenpunkt
    und dem Fusskreis. Das ist eine sehr gute Naeherung der echten Trochoide,
    solange root_radius < base_radius (Standardfall).
    """
    ix, iy = involute_start
    inv_radius = math.hypot(ix, iy)
    inv_angle = math.atan2(iy, ix)
    # Wenn die Evolvente bereits unterhalb / am Fusskreis startet, kein Fillet noetig.
    if inv_radius <= root_radius + 1e-9:
        return []
    pts = []
    # Kreisbogen mit Mittelpunkt auf der Tangentialen am Evolventenstartpunkt,
    # tangential abfallend zum Fusskreis am gleichen Polarwinkel.
    foot_x = root_radius * math.cos(inv_angle)
    foot_y = root_radius * math.sin(inv_angle)
    for i in range(1, fillet_samples + 1):
        u = i / (fillet_samples + 1)
        # Glatte cosinus-basierte Interpolation -> tangential an beiden Enden.
        s = 0.5 - 0.5 * math.cos(math.pi * u)
        x = foot_x * (1.0 - s) + ix * s
        y = foot_y * (1.0 - s) + iy * s
        # Auf einen interpolierten Radius projizieren, damit der Bogen sauber bleibt.
        r_target = root_radius + (inv_radius - root_radius) * s
        cur_r = math.hypot(x, y)
        if cur_r > 1e-12:
            x *= r_target / cur_r
            y *= r_target / cur_r
        pts.append((x, y))
    return pts


def build_arc(radius, start_angle, end_angle, samples):
    """Polygonzug auf einem Kreisbogen, exklusive Start- und Endpunkt."""
    pts = []
    if samples <= 0:
        return pts
    span = end_angle - start_angle
    for i in range(1, samples + 1):
        u = i / (samples + 1)
        ang = start_angle + span * u
        pts.append((radius * math.cos(ang), radius * math.sin(ang)))
    return pts


def build_gear_profile(
    pitch_radius,
    teeth,
    pressure_angle_deg,
    addendum_coeff=1.0,
    dedendum_coeff=1.25,
    flank_samples=20,
    fillet_samples=6,
    tip_samples=4,
    root_samples=4,
):
    """
    Erzeugt das geschlossene 2D-Profil eines Evolventen-Zahnrads als geordnete
    Liste von (x, y)-Punkten gegen den Uhrzeigersinn.
    """
    if teeth < 4:
        raise ValueError("Zaehnezahl muss >= 4 sein.")

    pressure_angle = math.radians(pressure_angle_deg)
    module = 2.0 * pitch_radius / teeth
    base_radius = pitch_radius * math.cos(pressure_angle)
    tip_radius = pitch_radius + addendum_coeff * module
    root_radius = max(pitch_radius - dedendum_coeff * module, 0.05 * pitch_radius)

    angular_pitch = 2.0 * math.pi / teeth
    # Halbe Zahndickenwinkel auf dem Teilkreis (Standard ohne Profilverschiebung).
    half_tooth_at_pitch = math.pi / (2.0 * teeth)
    # Auf der Symmetrieachse des Zahns liegt die Mitte. Der Polarwinkel der Evolvente
    # waechst beim Aufwickeln um inv(alpha). Damit der Schnittpunkt mit dem Teilkreis
    # bei +/- half_tooth_at_pitch liegt, muss die Evolvente um folgenden Wert versetzt sein:
    flank_offset = half_tooth_at_pitch + inv(pressure_angle)

    # Eine Referenzflanke (rechte Seite) im lokalen Koordinatensystem des Zahns:
    raw_flank = build_tooth_flank(base_radius, root_radius, tip_radius, flank_samples)
    raw_fillet = build_root_fillet(raw_flank[0], root_radius, fillet_samples)

    # Rechte Flanke: Evolvente liegt nach Drehung um -flank_offset rechts der Mittelachse.
    right_flank = [rotate_xy(x, y, -flank_offset) for (x, y) in raw_flank]
    right_fillet = [rotate_xy(x, y, -flank_offset) for (x, y) in raw_fillet]

    # Linke Flanke: Spiegelung an der Mittelachse (y-Vorzeichen flip).
    left_flank = [(x, -y) for (x, y) in right_flank]
    left_fillet = [(x, -y) for (x, y) in right_fillet]

    # Polarwinkel der Flanken-Anschlusspunkte am Fusskreis (fuer Fusskreisbogen).
    if right_fillet:
        right_root_pt = right_fillet[-1]
    else:
        right_root_pt = right_flank[0]
    right_root_angle = math.atan2(right_root_pt[1], right_root_pt[0])
    left_root_angle = -right_root_angle  # Symmetrie

    # Polarwinkel an der Kopfkreis-Anschlussstelle (fuer Kopfkreisbogen).
    right_tip_angle = math.atan2(right_flank[-1][1], right_flank[-1][0])
    left_tip_angle = -right_tip_angle

    profile = []
    for i in range(teeth):
        center_angle = i * angular_pitch
        # Anschlussbogen am Fusskreis vom vorherigen Zahn -> rechter Fillet-Anfang.
        # Negative Indizes funktionieren hier rechnerisch korrekt: fuer i=0 ergibt
        # (i-1)*angular_pitch ein negativer Startwinkel, der curr_right_root_world
        # mit dem korrekten Bogen-Span ueberbrueckt.
        prev_left_root_world = (i - 1) * angular_pitch + left_root_angle
        curr_right_root_world = center_angle + right_root_angle
        for x, y in build_arc(root_radius, prev_left_root_world, curr_right_root_world, root_samples):
            profile.append((x, y))

        # Rechter Fillet (Fuss -> Evolventenstart).
        for x, y in right_fillet:
            xr, yr = rotate_xy(x, y, center_angle)
            profile.append((xr, yr))

        # Rechte Evolventenflanke (Evolventenstart -> Kopf).
        for x, y in right_flank:
            xr, yr = rotate_xy(x, y, center_angle)
            profile.append((xr, yr))

        # Kopfkreisbogen (rechter Kopfpunkt -> linker Kopfpunkt).
        tip_start = center_angle + right_tip_angle
        tip_end = center_angle + left_tip_angle
        for x, y in build_arc(tip_radius, tip_start, tip_end, tip_samples):
            profile.append((x, y))

        # Linke Evolventenflanke (Kopf -> Evolventenstart, also reversed).
        for x, y in reversed(left_flank):
            xr, yr = rotate_xy(x, y, center_angle)
            profile.append((xr, yr))

        # Linker Fillet (Evolventenstart -> Fuss, also reversed).
        for x, y in reversed(left_fillet):
            xr, yr = rotate_xy(x, y, center_angle)
            profile.append((xr, yr))

    # Adjazente Punkte zusammenfuehren, die durch Sampling/Rundung nahezu zusammenfallen.
    eps_sq = (1e-6 * pitch_radius) ** 2
    cleaned = [profile[0]]
    for x, y in profile[1:]:
        px, py = cleaned[-1]
        if (x - px) ** 2 + (y - py) ** 2 > eps_sq:
            cleaned.append((x, y))
    # Auch Schliesskante pruefen: Anfang darf nicht auf Ende fallen.
    if (cleaned[0][0] - cleaned[-1][0]) ** 2 + (cleaned[0][1] - cleaned[-1][1]) ** 2 <= eps_sq:
        cleaned.pop()

    return cleaned, root_radius, tip_radius


# ================================================================
# MESH-AUFBAU
# ================================================================

def create_gear_mesh(radius, teeth, thickness, pressure_angle_deg):
    profile, _root_radius, _tip_radius = build_gear_profile(
        pitch_radius=radius,
        teeth=teeth,
        pressure_angle_deg=pressure_angle_deg,
    )

    mesh = bpy.data.meshes.new("Zahnrad")
    obj = bpy.data.objects.new("Zahnrad", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    verts = [bm.verts.new((x, y, 0.0)) for (x, y) in profile]
    bm.faces.new(verts)

    extrude_result = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
    new_verts = [el for el in extrude_result["geom"] if isinstance(el, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, vec=(0.0, 0.0, thickness), verts=new_verts)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    bm.to_mesh(mesh)
    bm.free()

    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


# ================================================================
# PROPERTIES (PropertyGroup -> umgeht 'readonly state' Fehler)
# ================================================================

class GearGeneratorProperties(bpy.types.PropertyGroup):
    radius: bpy.props.FloatProperty(
        name="Teilkreisradius",
        description="Radius des Teilkreises",
        default=1.0,
        min=0.1,
        unit="LENGTH",
    )
    teeth: bpy.props.IntProperty(
        name="Zaehnezahl",
        description="Anzahl der Zaehne",
        default=24,
        min=6,
        max=200,
    )
    thickness: bpy.props.FloatProperty(
        name="Dicke",
        description="Dicke des Zahnrads",
        default=0.3,
        min=0.01,
        unit="LENGTH",
    )
    pressure_angle: bpy.props.FloatProperty(
        name="Eingriffswinkel",
        description="Druckwinkel in Grad (Standard 20)",
        default=20.0,
        min=10.0,
        max=30.0,
    )


# ================================================================
# OPERATOR
# ================================================================

class MESH_OT_create_gear(bpy.types.Operator):
    bl_idname = "mesh.create_gear"
    bl_label = "Zahnrad erstellen"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.gear_generator
        try:
            create_gear_mesh(
                radius=props.radius,
                teeth=props.teeth,
                thickness=props.thickness,
                pressure_angle_deg=props.pressure_angle,
            )
        except Exception as exc:
            self.report({"ERROR"}, f"Zahnrad konnte nicht erzeugt werden: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Evolventen-Zahnrad mit {props.teeth} Zaehnen erstellt.")
        return {"FINISHED"}


# ================================================================
# PANEL
# ================================================================

class VIEW3D_PT_gear_generator(bpy.types.Panel):
    bl_label = "Evolventen Zahnrad"
    bl_idname = "VIEW3D_PT_gear_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Erstellen"

    def draw(self, context):
        layout = self.layout
        props = context.scene.gear_generator
        layout.prop(props, "radius")
        layout.prop(props, "teeth")
        layout.prop(props, "thickness")
        layout.prop(props, "pressure_angle")
        layout.operator("mesh.create_gear", icon="MESH_CIRCLE")


# ================================================================
# REGISTRATION
# ================================================================

_classes = (
    GearGeneratorProperties,
    MESH_OT_create_gear,
    VIEW3D_PT_gear_generator,
)


def _safe_unregister():
    """Best-effort Cleanup: entfernt vorherige Registrierungen, ignoriert Fehler.
    Wichtig fuer wiederholtes Ausfuehren des Skripts im Blender-Texteditor, da
    eine bereits an Scene gebundene PropertyGroup als 'readonly' gilt und ein
    erneutes register_class() sonst mit RuntimeError abbricht."""
    if hasattr(bpy.types.Scene, "gear_generator"):
        try:
            del bpy.types.Scene.gear_generator
        except Exception:
            pass
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


def _do_register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.gear_generator = bpy.props.PointerProperty(type=GearGeneratorProperties)


def register():
    # Erst aufraeumen, damit Re-Runs aus dem Texteditor nicht am 'readonly'
    # Status der bereits gebundenen PropertyGroup scheitern.
    _safe_unregister()
    try:
        _do_register()
    except RuntimeError as exc:
        if "readonly" not in str(exc).lower():
            raise
        # Blender ist in einem restriktiven Kontext (z.B. File-Load, Render).
        # Registrierung per Timer verschieben, bis der Kontext wieder frei ist.
        def _deferred():
            try:
                _do_register()
            except RuntimeError as exc_inner:
                if "readonly" in str(exc_inner).lower():
                    return 0.5  # spaeter erneut versuchen
                raise
            return None  # einmalige Ausfuehrung, Timer beenden
        bpy.app.timers.register(_deferred, first_interval=0.5)


def unregister():
    _safe_unregister()


if __name__ == "__main__":
    register()
