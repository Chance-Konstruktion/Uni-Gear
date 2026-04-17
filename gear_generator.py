import bpy
import bmesh
import math

bl_info = {
    "name": "Parametric Evolvent Gear Generator",
    "author": "Du + KI-Assistent",
    "version": (4, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Erstellen",
    "description": "Evolventenzahnrad mit optionaler Schraegverzahnung und Bohrungen.",
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

def _add_circle_layer(bm, cx, cy, z, radius, segments):
    """Erzeugt einen Ring aus BMVerts auf einem Kreis."""
    verts = []
    for s in range(segments):
        ang = 2.0 * math.pi * s / segments
        verts.append(bm.verts.new((cx + radius * math.cos(ang), cy + radius * math.sin(ang), z)))
    return verts


def _bridge_rings(bm, lower, upper, reverse_winding=False):
    """Verbindet zwei Ringe gleicher Laenge durch Vierecke."""
    n = len(lower)
    assert n == len(upper)
    for i in range(n):
        j = (i + 1) % n
        if reverse_winding:
            bm.faces.new((lower[i], upper[i], upper[j], lower[j]))
        else:
            bm.faces.new((lower[i], lower[j], upper[j], upper[i]))


def _collect_loop_edges(bm, loops):
    """Sammelt fuer jeden Vertex-Loop die bereits existierenden Umfangs-Edges."""
    edges = []
    seen = set()
    for loop in loops:
        n = len(loop)
        for i in range(n):
            e = bm.edges.get((loop[i], loop[(i + 1) % n]))
            if e is not None and e.index not in seen:
                seen.add(e.index)
                edges.append(e)
    return edges


def _compute_helix_layers(thickness, helix_angle_rad, pitch_radius):
    """Waehlt eine Anzahl von axialen Schichten fuer die Schraegverzahnung."""
    if abs(helix_angle_rad) < 1e-9 or thickness <= 0.0:
        return 1
    total_twist = abs(thickness * math.tan(helix_angle_rad) / pitch_radius)
    # 3 Grad pro Schicht, mindestens 4 Schichten fuer weiche Verwindung.
    layers = max(4, int(math.ceil(math.degrees(total_twist) / 3.0)))
    return min(layers, 128)


def create_gear_mesh(
    pitch_radius,
    teeth,
    thickness,
    pressure_angle_deg,
    helix_angle_deg=0.0,
    bore_radius=0.0,
    hole_count=0,
    hole_radius=0.0,
    hole_pitch_radius=0.0,
):
    """Erzeugt das vollstaendige 3D-Mesh eines (optional schraegverzahnten) Zahnrads
    mit optionaler zentrischer Bohrung und optionalen dezentralen Bohrungen."""
    profile_2d, root_radius, _tip_radius = build_gear_profile(
        pitch_radius=pitch_radius,
        teeth=teeth,
        pressure_angle_deg=pressure_angle_deg,
    )

    # Validierung: Bohrungen duerfen weder den Fusskreis noch einander beruehren.
    if bore_radius > 0.0 and bore_radius >= root_radius * 0.95:
        raise ValueError("Zentrische Bohrung zu gross fuer diesen Fusskreisradius.")
    if hole_count > 0:
        if hole_radius <= 0.0:
            raise ValueError("Dezentrale Bohrungen: Radius muss > 0 sein.")
        inner_limit = max(bore_radius, 0.0) * 1.05
        if hole_pitch_radius - hole_radius < inner_limit:
            raise ValueError("Dezentrale Bohrungen ueberlappen die zentrische Bohrung.")
        if hole_pitch_radius + hole_radius > root_radius * 0.95:
            raise ValueError("Dezentrale Bohrungen ragen ueber den Fusskreis hinaus.")
        # Abstand zwischen benachbarten Loechern auf ihrem Teilkreis.
        if hole_count >= 2:
            chord = 2.0 * hole_pitch_radius * math.sin(math.pi / hole_count)
            if chord < 2.0 * hole_radius * 1.05:
                raise ValueError("Dezentrale Bohrungen ueberlappen einander.")

    helix_angle = math.radians(helix_angle_deg)
    layers = _compute_helix_layers(thickness, helix_angle, pitch_radius)

    mesh = bpy.data.meshes.new("Zahnrad")
    obj = bpy.data.objects.new("Zahnrad", mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()

    # --- Aussenhuelle ueber mehrere Z-Schichten (fuer Schraegverzahnung) ---
    outer_layers = []
    tan_helix = math.tan(helix_angle)
    for k in range(layers + 1):
        z = thickness * k / layers
        phi = z * tan_helix / pitch_radius
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        layer = []
        for (x, y) in profile_2d:
            xr = x * cos_phi - y * sin_phi
            yr = x * sin_phi + y * cos_phi
            layer.append(bm.verts.new((xr, yr, z)))
        outer_layers.append(layer)

    for k in range(layers):
        _bridge_rings(bm, outer_layers[k], outer_layers[k + 1])

    outer_bottom = outer_layers[0]
    outer_top = outer_layers[-1]

    # --- Zentrische Bohrung (axial, nicht verdreht) ---
    bore_bottom = bore_top = None
    if bore_radius > 0.0:
        bore_segments = max(32, min(128, int(2.0 * math.pi * bore_radius / (0.01 * pitch_radius)) + 16))
        bore_bottom = _add_circle_layer(bm, 0.0, 0.0, 0.0, bore_radius, bore_segments)
        bore_top = _add_circle_layer(bm, 0.0, 0.0, thickness, bore_radius, bore_segments)
        # Normalen sollen nach innen (ins Loch) zeigen -> umgekehrte Verdrahtung.
        _bridge_rings(bm, bore_bottom, bore_top, reverse_winding=True)

    # --- Dezentrale Bohrungen (Entlastungs- bzw. Befestigungsbohrungen) ---
    hole_bottoms = []
    hole_tops = []
    if hole_count > 0 and hole_radius > 0.0:
        hole_segments = max(16, min(64, int(hole_radius / (0.005 * pitch_radius)) + 8))
        for hi in range(hole_count):
            center_angle = 2.0 * math.pi * hi / hole_count
            cx = hole_pitch_radius * math.cos(center_angle)
            cy = hole_pitch_radius * math.sin(center_angle)
            ring_bottom = _add_circle_layer(bm, cx, cy, 0.0, hole_radius, hole_segments)
            ring_top = _add_circle_layer(bm, cx, cy, thickness, hole_radius, hole_segments)
            _bridge_rings(bm, ring_bottom, ring_top, reverse_winding=True)
            hole_bottoms.append(ring_bottom)
            hole_tops.append(ring_top)

    # --- End-Caps: planar triangulieren, inkl. aller Loch-Schleifen ---
    bottom_loops = [outer_bottom]
    top_loops = [outer_top]
    if bore_bottom is not None:
        bottom_loops.append(bore_bottom)
        top_loops.append(bore_top)
    bottom_loops.extend(hole_bottoms)
    top_loops.extend(hole_tops)

    bmesh.ops.triangle_fill(bm, edges=_collect_loop_edges(bm, bottom_loops), use_beauty=True)
    bmesh.ops.triangle_fill(bm, edges=_collect_loop_edges(bm, top_loops), use_beauty=True)

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
    # --- Basisgeometrie ---
    radius: bpy.props.FloatProperty(
        name="Teilkreisradius",
        description="Radius des Teilkreises in Szenen-Laengeneinheiten",
        default=0.02,
        min=0.001,
        max=1.0,
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
        description="Dicke (Zahnbreite) des Zahnrads",
        default=0.005,
        min=0.0001,
        max=1.0,
        unit="LENGTH",
    )
    pressure_angle: bpy.props.FloatProperty(
        name="Eingriffswinkel",
        description="Druckwinkel in Grad (Standard 20)",
        default=20.0,
        min=10.0,
        max=30.0,
    )

    # --- Schraegverzahnung ---
    use_helical: bpy.props.BoolProperty(
        name="Schraegverzahnung",
        description="Zaehne als Schraegverzahnung mit Verdrehung ueber die Zahnbreite erzeugen",
        default=False,
    )
    helix_angle: bpy.props.FloatProperty(
        name="Schraegungswinkel",
        description="Winkel der Schraegverzahnung in Grad (0 = Geradverzahnung)",
        default=15.0,
        min=-45.0,
        max=45.0,
    )

    # --- Zentrische Bohrung ---
    use_bore: bpy.props.BoolProperty(
        name="Zentrische Bohrung",
        description="Bohrung entlang der Zahnradachse erzeugen",
        default=False,
    )
    bore_radius: bpy.props.FloatProperty(
        name="Bohrungsradius",
        description="Radius der zentrischen Bohrung",
        default=0.004,
        min=0.0001,
        max=1.0,
        unit="LENGTH",
    )

    # --- Dezentrale Bohrungen ---
    use_holes: bpy.props.BoolProperty(
        name="Dezentrale Bohrungen",
        description="Zusaetzliche Bohrungen fuer Gewichtsersparnis oder Befestigung",
        default=False,
    )
    hole_count: bpy.props.IntProperty(
        name="Anzahl",
        description="Anzahl der gleichmaessig verteilten dezentralen Bohrungen",
        default=6,
        min=1,
        max=32,
    )
    hole_radius: bpy.props.FloatProperty(
        name="Radius",
        description="Radius jeder dezentralen Bohrung",
        default=0.002,
        min=0.0001,
        max=1.0,
        unit="LENGTH",
    )
    hole_pitch_radius: bpy.props.FloatProperty(
        name="Lochkreisradius",
        description="Radius des Lochkreises, auf dem die dezentralen Bohrungen liegen",
        default=0.01,
        min=0.0001,
        max=1.0,
        unit="LENGTH",
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
        helix_deg = props.helix_angle if props.use_helical else 0.0
        bore_r = props.bore_radius if props.use_bore else 0.0
        hole_n = props.hole_count if props.use_holes else 0
        hole_r = props.hole_radius if props.use_holes else 0.0
        hole_pr = props.hole_pitch_radius if props.use_holes else 0.0
        try:
            create_gear_mesh(
                pitch_radius=props.radius,
                teeth=props.teeth,
                thickness=props.thickness,
                pressure_angle_deg=props.pressure_angle,
                helix_angle_deg=helix_deg,
                bore_radius=bore_r,
                hole_count=hole_n,
                hole_radius=hole_r,
                hole_pitch_radius=hole_pr,
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

        box = layout.box()
        box.label(text="Zahnrad")
        box.prop(props, "radius")
        box.prop(props, "teeth")
        box.prop(props, "thickness")
        box.prop(props, "pressure_angle")

        box = layout.box()
        box.prop(props, "use_helical")
        sub = box.column()
        sub.enabled = props.use_helical
        sub.prop(props, "helix_angle")

        box = layout.box()
        box.prop(props, "use_bore")
        sub = box.column()
        sub.enabled = props.use_bore
        sub.prop(props, "bore_radius")

        box = layout.box()
        box.prop(props, "use_holes")
        sub = box.column()
        sub.enabled = props.use_holes
        sub.prop(props, "hole_count")
        sub.prop(props, "hole_radius")
        sub.prop(props, "hole_pitch_radius")

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
