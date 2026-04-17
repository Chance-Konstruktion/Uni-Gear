import bpy
import bmesh
import math

bl_info = {
    "name": "Parametric Evolvent Gear Generator",
    "author": "Du + KI-Assistent",
    "version": (5, 0, 0),
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
    hub_radius=0.0,
    hub_height=0.0,
    hub_sides="BOTH",
    z_offset=0.0,
):
    """Erstellt ein vollstaendiges 3D-Mesh eines Evolventen-Zahnrads.

    Optional: Schraegverzahnung, zentrische Bohrung, dezentrale Bohrungen,
    und eine Nabe (Hub) auf einer oder beiden Stirnseiten.
    z_offset verschiebt das fertige Objekt entlang Z (fuer Stacking).
    """
    profile_2d, root_radius, _tip_radius = build_gear_profile(
        pitch_radius=pitch_radius,
        teeth=teeth,
        pressure_angle_deg=pressure_angle_deg,
    )

    has_hub_back  = hub_radius > 0.0 and hub_height > 0.0 and hub_sides in ("BOTH", "BACK")
    has_hub_front = hub_radius > 0.0 and hub_height > 0.0 and hub_sides in ("BOTH", "FRONT")
    has_hub       = has_hub_back or has_hub_front
    has_bore      = bore_radius > 0.0
    has_holes     = hole_count > 0 and hole_radius > 0.0

    # --- Validierung ---
    if has_bore and bore_radius >= root_radius * 0.95:
        raise ValueError("Zentrische Bohrung zu gross fuer diesen Fusskreisradius.")
    if has_hub:
        if hub_radius >= root_radius * 0.95:
            raise ValueError("Nabenradius zu gross fuer diesen Fusskreisradius.")
        if has_bore and bore_radius >= hub_radius:
            raise ValueError("Bohrungsradius muss kleiner als Nabenradius sein.")
    if has_holes:
        inner_clear = max(hub_radius if has_hub else 0.0, bore_radius if has_bore else 0.0)
        if hole_pitch_radius - hole_radius < inner_clear * 1.05:
            raise ValueError("Dezentrale Bohrungen ueberlappen Nabe oder Bohrung.")
        if hole_pitch_radius + hole_radius > root_radius * 0.95:
            raise ValueError("Dezentrale Bohrungen ragen ueber den Fusskreis hinaus.")
        if hole_count >= 2:
            chord = 2.0 * hole_pitch_radius * math.sin(math.pi / hole_count)
            if chord < 2.0 * hole_radius * 1.05:
                raise ValueError("Dezentrale Bohrungen ueberlappen einander.")

    helix_angle = math.radians(helix_angle_deg)
    layers = _compute_helix_layers(thickness, helix_angle, pitch_radius)

    def _segs_for_r(r):
        return max(32, min(128, int(2.0 * math.pi * r / (0.005 * pitch_radius)) + 16))

    mesh = bpy.data.meshes.new("Zahnrad")
    obj  = bpy.data.objects.new("Zahnrad", mesh)
    bpy.context.collection.objects.link(obj)
    bm   = bmesh.new()

    # --- Aussenhuelle (helical) ---
    tan_helix   = math.tan(helix_angle)
    outer_layers = []
    for k in range(layers + 1):
        z       = thickness * k / layers
        phi     = z * tan_helix / pitch_radius
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        outer_layers.append([
            bm.verts.new((x * cos_phi - y * sin_phi, x * sin_phi + y * cos_phi, z))
            for (x, y) in profile_2d
        ])
    for k in range(layers):
        _bridge_rings(bm, outer_layers[k], outer_layers[k + 1])
    outer_bottom = outer_layers[0]
    outer_top    = outer_layers[-1]

    # --- Naben-Aussenzylinder ---
    # hub_back:  z = -hub_height  ..  0          (Rueckseite)
    # hub_front: z = thickness    ..  thickness + hub_height  (Vorderseite)
    hub_back_bot = hub_back_top = hub_front_bot = hub_front_top = None
    if has_hub_back:
        hub_segs      = _segs_for_r(hub_radius)
        hub_back_bot  = _add_circle_layer(bm, 0.0, 0.0, -hub_height, hub_radius, hub_segs)
        hub_back_top  = _add_circle_layer(bm, 0.0, 0.0,  0.0,        hub_radius, hub_segs)
        _bridge_rings(bm, hub_back_bot, hub_back_top)           # Normalen nach aussen
    if has_hub_front:
        hub_segs      = _segs_for_r(hub_radius)
        hub_front_bot = _add_circle_layer(bm, 0.0, 0.0, thickness,              hub_radius, hub_segs)
        hub_front_top = _add_circle_layer(bm, 0.0, 0.0, thickness + hub_height, hub_radius, hub_segs)
        _bridge_rings(bm, hub_front_bot, hub_front_top)

    # --- Bohrung (erstreckt sich durch Nabe falls vorhanden) ---
    # Wir benoetigen Bohrungsringe bei allen Stirnflaechen-Z-Werten fuer triangle_fill.
    bore_z_start = -hub_height  if has_hub_back  else 0.0
    bore_z_end   =  thickness + hub_height if has_hub_front else thickness
    bore_rings   = {}  # {z_value: [BMVerts]}
    if has_bore:
        bore_segs    = _segs_for_r(bore_radius)
        bore_z_set   = {bore_z_start, 0.0, thickness, bore_z_end}
        bore_z_levels = sorted(bore_z_set)
        for z in bore_z_levels:
            bore_rings[z] = _add_circle_layer(bm, 0.0, 0.0, z, bore_radius, bore_segs)
        for i in range(len(bore_z_levels) - 1):
            _bridge_rings(bm, bore_rings[bore_z_levels[i]], bore_rings[bore_z_levels[i + 1]],
                          reverse_winding=True)

    # --- Dezentrale Bohrungen ---
    hole_bottoms = []
    hole_tops    = []
    if has_holes:
        hole_segs = _segs_for_r(hole_radius)
        for hi in range(hole_count):
            ang = 2.0 * math.pi * hi / hole_count
            cx  = hole_pitch_radius * math.cos(ang)
            cy  = hole_pitch_radius * math.sin(ang)
            rb  = _add_circle_layer(bm, cx, cy, 0.0,       hole_radius, hole_segs)
            rt  = _add_circle_layer(bm, cx, cy, thickness, hole_radius, hole_segs)
            _bridge_rings(bm, rb, rt, reverse_winding=True)
            hole_bottoms.append(rb)
            hole_tops.append(rt)

    # --- Stirnflaechen (triangle_fill) ---
    # Die innere Grenze der Zahnrad-Stirnflaeche ist die Nabe (falls vorhanden)
    # oder die Bohrung; nicht beides gleichzeitig (Nabe umschliesst die Bohrung).
    def _fill_cap(outer_loop, inner_ring, extra_holes):
        loops = [outer_loop]
        if inner_ring is not None:
            loops.append(inner_ring)
        loops.extend(extra_holes)
        bmesh.ops.triangle_fill(bm, edges=_collect_loop_edges(bm, loops), use_beauty=True)

    # Zahnrad-Rueckseite (z=0)
    inner_back = hub_back_top if has_hub_back else bore_rings.get(0.0)
    _fill_cap(outer_bottom, inner_back, hole_bottoms)

    # Zahnrad-Vorderseite (z=thickness)
    inner_front = hub_front_bot if has_hub_front else bore_rings.get(thickness)
    _fill_cap(outer_top, inner_front, hole_tops)

    # Naben-Rueckseite (z=-hub_height) — Kreisring oder Vollkreis
    if has_hub_back:
        _fill_cap(hub_back_bot, bore_rings.get(bore_z_start), [])

    # Naben-Vorderseite (z=thickness+hub_height)
    if has_hub_front:
        _fill_cap(hub_front_top, bore_rings.get(bore_z_end), [])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])

    if z_offset != 0.0:
        bmesh.ops.translate(bm, vec=(0.0, 0.0, z_offset), verts=bm.verts[:])

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
        description="Radius des Teilkreises",
        default=0.02, min=0.001, max=1.0, unit="LENGTH",
    )
    teeth: bpy.props.IntProperty(
        name="Zaehnezahl", default=24, min=6, max=200,
    )
    thickness: bpy.props.FloatProperty(
        name="Dicke", description="Zahnbreite (axiale Dicke)",
        default=0.005, min=0.0001, max=1.0, unit="LENGTH",
    )
    pressure_angle: bpy.props.FloatProperty(
        name="Eingriffswinkel", description="Druckwinkel in Grad (Standard 20)",
        default=20.0, min=10.0, max=30.0,
    )

    # --- Schraegverzahnung ---
    use_helical: bpy.props.BoolProperty(name="Schraegverzahnung", default=False)
    helix_angle: bpy.props.FloatProperty(
        name="Schraegungswinkel", description="Helix-Winkel in Grad",
        default=15.0, min=-45.0, max=45.0,
    )

    # --- Nabe (Hub) ---
    use_hub: bpy.props.BoolProperty(
        name="Nabe", description="Zylindrische Nabe auf einer oder beiden Stirnseiten", default=False,
    )
    hub_radius: bpy.props.FloatProperty(
        name="Nabenradius", description="Aussenradius der Nabe",
        default=0.008, min=0.0001, max=1.0, unit="LENGTH",
    )
    hub_height: bpy.props.FloatProperty(
        name="Nabenhoehe", description="Wie weit die Nabe ueber die Stirnflaeche hinausragt",
        default=0.004, min=0.0001, max=1.0, unit="LENGTH",
    )
    hub_sides: bpy.props.EnumProperty(
        name="Seite",
        items=[
            ("BOTH",  "Beidseitig",  "Nabe auf Vorder- und Rueckseite"),
            ("BACK",  "Rueckseite",  "Nabe nur auf der Rueckseite (z=0)"),
            ("FRONT", "Vorderseite", "Nabe nur auf der Vorderseite (z=Dicke)"),
        ],
        default="BOTH",
    )

    # --- Zentrische Bohrung ---
    use_bore: bpy.props.BoolProperty(
        name="Zentrische Bohrung", description="Bohrung entlang der Achse (durch Nabe falls vorhanden)",
        default=False,
    )
    bore_radius: bpy.props.FloatProperty(
        name="Bohrungsradius",
        default=0.004, min=0.0001, max=1.0, unit="LENGTH",
    )

    # --- Dezentrale Bohrungen ---
    use_holes: bpy.props.BoolProperty(
        name="Dezentrale Bohrungen", description="Gewichtserleichterungs- oder Befestigungsbohrungen",
        default=False,
    )
    hole_count: bpy.props.IntProperty(name="Anzahl", default=6, min=1, max=32)
    hole_radius: bpy.props.FloatProperty(
        name="Radius", default=0.002, min=0.0001, max=1.0, unit="LENGTH",
    )
    hole_pitch_radius: bpy.props.FloatProperty(
        name="Lochkreisradius", description="Radius des Lochkreises",
        default=0.01, min=0.0001, max=1.0, unit="LENGTH",
    )

    # --- Stacking (Stufenrad) ---
    use_stack: bpy.props.BoolProperty(
        name="Stufenrad (Stacking)",
        description="Mehrere Zahnradstufen auf derselben Achse erzeugen",
        default=False,
    )
    stack_count: bpy.props.IntProperty(
        name="Stufen gesamt", description="Gesamtzahl der Stufen (inkl. Hauptzahnrad)",
        default=2, min=2, max=3,
    )
    stack_z_gap: bpy.props.FloatProperty(
        name="Abstand", description="Axialer Abstand zwischen den Stufen",
        default=0.0, min=0.0, max=0.1, unit="LENGTH",
    )
    # Stufe 2
    stack2_radius: bpy.props.FloatProperty(
        name="Teilkreisradius", default=0.015, min=0.001, max=1.0, unit="LENGTH",
    )
    stack2_teeth: bpy.props.IntProperty(name="Zaehnezahl", default=16, min=6, max=200)
    stack2_thickness: bpy.props.FloatProperty(
        name="Dicke", default=0.005, min=0.0001, max=1.0, unit="LENGTH",
    )
    # Stufe 3
    stack3_radius: bpy.props.FloatProperty(
        name="Teilkreisradius", default=0.01, min=0.001, max=1.0, unit="LENGTH",
    )
    stack3_teeth: bpy.props.IntProperty(name="Zaehnezahl", default=10, min=6, max=200)
    stack3_thickness: bpy.props.FloatProperty(
        name="Dicke", default=0.005, min=0.0001, max=1.0, unit="LENGTH",
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
        bore_r    = props.bore_radius if props.use_bore  else 0.0
        hole_n    = props.hole_count  if props.use_holes else 0
        hole_r    = props.hole_radius       if props.use_holes else 0.0
        hole_pr   = props.hole_pitch_radius if props.use_holes else 0.0
        hub_r     = props.hub_radius  if props.use_hub else 0.0
        hub_h     = props.hub_height  if props.use_hub else 0.0
        hub_s     = props.hub_sides   if props.use_hub else "BOTH"

        # Stufenparameter sammeln (immer Stufe 1 = Hauptrad)
        stages = [
            {"pitch_radius": props.radius,        "teeth": props.teeth,
             "thickness": props.thickness,         "pressure_angle": props.pressure_angle},
        ]
        if props.use_stack:
            stages.append({
                "pitch_radius": props.stack2_radius, "teeth": props.stack2_teeth,
                "thickness": props.stack2_thickness, "pressure_angle": props.pressure_angle,
            })
            if props.stack_count >= 3:
                stages.append({
                    "pitch_radius": props.stack3_radius, "teeth": props.stack3_teeth,
                    "thickness": props.stack3_thickness, "pressure_angle": props.pressure_angle,
                })

        z = 0.0
        created = 0
        for i, stage in enumerate(stages):
            # Nabe nur auf Aussenstirnflaechen: Stufe 1 Rueckseite, letzte Stufe Vorderseite.
            if len(stages) == 1:
                h_sides = hub_s
            elif i == 0:
                h_sides = "BACK"
            elif i == len(stages) - 1:
                h_sides = "FRONT"
            else:
                h_sides = "NONE"  # Mittelstufen: keine Nabe

            if h_sides == "NONE":
                eff_hub_r = 0.0
                eff_hub_h = 0.0
            else:
                eff_hub_r = hub_r
                eff_hub_h = hub_h

            try:
                create_gear_mesh(
                    pitch_radius=stage["pitch_radius"],
                    teeth=stage["teeth"],
                    thickness=stage["thickness"],
                    pressure_angle_deg=stage["pressure_angle"],
                    helix_angle_deg=helix_deg,
                    bore_radius=bore_r,
                    hole_count=hole_n,
                    hole_radius=hole_r,
                    hole_pitch_radius=hole_pr,
                    hub_radius=eff_hub_r,
                    hub_height=eff_hub_h,
                    hub_sides=h_sides,
                    z_offset=z,
                )
            except Exception as exc:
                self.report({"ERROR"}, f"Stufe {i + 1}: {exc}")
                return {"CANCELLED"}

            z += stage["thickness"] + (props.stack_z_gap if props.use_stack else 0.0)
            created += 1

        label = f"Stufenrad ({created} Stufen)" if created > 1 else f"Zahnrad {props.teeth}Z"
        self.report({"INFO"}, f"{label} erstellt.")
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
        props  = context.scene.gear_generator

        # Zahnrad
        box = layout.box()
        box.label(text="Zahnrad", icon="MESH_CIRCLE")
        box.prop(props, "radius")
        box.prop(props, "teeth")
        box.prop(props, "thickness")
        box.prop(props, "pressure_angle")

        # Schraegverzahnung
        box = layout.box()
        box.prop(props, "use_helical", icon="MOD_SCREW")
        col = box.column()
        col.enabled = props.use_helical
        col.prop(props, "helix_angle")

        # Nabe
        box = layout.box()
        box.prop(props, "use_hub", icon="MESH_CYLINDER")
        col = box.column()
        col.enabled = props.use_hub
        col.prop(props, "hub_radius")
        col.prop(props, "hub_height")
        col.prop(props, "hub_sides")

        # Zentrische Bohrung
        box = layout.box()
        box.prop(props, "use_bore", icon="HANDLE_ALIGN")
        col = box.column()
        col.enabled = props.use_bore
        col.prop(props, "bore_radius")

        # Dezentrale Bohrungen
        box = layout.box()
        box.prop(props, "use_holes", icon="EMPTY_AXIS")
        col = box.column()
        col.enabled = props.use_holes
        col.prop(props, "hole_count")
        col.prop(props, "hole_radius")
        col.prop(props, "hole_pitch_radius")

        # Stacking
        box = layout.box()
        box.prop(props, "use_stack", icon="DUPLICATE")
        col = box.column()
        col.enabled = props.use_stack
        col.prop(props, "stack_count")
        col.prop(props, "stack_z_gap")
        # Stufe 2
        sub2 = col.box()
        sub2.enabled = props.use_stack
        sub2.label(text="Stufe 2")
        sub2.prop(props, "stack2_radius")
        sub2.prop(props, "stack2_teeth")
        sub2.prop(props, "stack2_thickness")
        # Stufe 3
        if props.stack_count >= 3:
            sub3 = col.box()
            sub3.label(text="Stufe 3")
            sub3.prop(props, "stack3_radius")
            sub3.prop(props, "stack3_teeth")
            sub3.prop(props, "stack3_thickness")

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
