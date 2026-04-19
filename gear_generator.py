import bpy
import bmesh
import math
import mathutils

bl_info = {
    "name": "Uni-Gear",
    "author": "Du + KI-Assistent",
    "version": (7, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Uni-Gear",
    "description": "Zahnradsimulation mit Innenverzahnung, Kegelverzahnung, DIN-3960 und Paarung.",
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


def _clean_profile(profile, pitch_radius):
    """Adjazente Punkte zusammenfuehren, die durch Sampling/Rundung nahezu zusammenfallen."""
    eps_sq = (1e-6 * pitch_radius) ** 2
    cleaned = [profile[0]]
    for x, y in profile[1:]:
        px, py = cleaned[-1]
        if (x - px) ** 2 + (y - py) ** 2 > eps_sq:
            cleaned.append((x, y))
    if (cleaned[0][0] - cleaned[-1][0]) ** 2 + (cleaned[0][1] - cleaned[-1][1]) ** 2 <= eps_sq:
        cleaned.pop()
    return cleaned


def build_trochoidal_fillet(pitch_radius, teeth, root_radius, flank_start_pt, fillet_samples=8):
    """Trochoidaler Zahnfuss-Verlauf (Naeherung des Werkzeug-Rack-Eingriffs)."""
    ix, iy = flank_start_pt
    inv_radius = math.hypot(ix, iy)
    inv_angle  = math.atan2(iy, ix)
    if inv_radius <= root_radius + 1e-9:
        return []
    module    = 2.0 * pitch_radius / teeth
    r_roll    = pitch_radius
    pts       = []
    foot_x    = root_radius * math.cos(inv_angle)
    foot_y    = root_radius * math.sin(inv_angle)
    for i in range(1, fillet_samples + 1):
        u            = i / (fillet_samples + 1)
        phi          = u * math.pi * 0.5
        s_radial     = math.sin(phi)
        s_tangential = 1.0 - math.cos(phi)
        r_current    = root_radius + (inv_radius - root_radius) * s_radial
        angle_shift  = s_tangential * (1.25 * module / r_roll) * 0.3
        ang          = inv_angle + angle_shift
        pts.append((r_current * math.cos(ang), r_current * math.sin(ang)))
    return pts


def build_gear_profile(
    pitch_radius,
    teeth,
    pressure_angle_deg,
    addendum_coeff=1.0,
    dedendum_coeff=1.25,
    profile_shift=0.0,
    use_trochoidal=False,
    flank_samples=20,
    fillet_samples=6,
    tip_samples=4,
    root_samples=4,
):
    """
    Erzeugt das geschlossene 2D-Profil eines Evolventen-Zahnrads.

    profile_shift:  Profilverschiebungsfaktor x (DIN 3960). 0 = Nullrad.
    use_trochoidal: Trochoidaler Zahnfuss statt einfachem Kreisbogen-Fillet.
    """
    if teeth < 4:
        raise ValueError("Zaehnezahl muss >= 4 sein.")

    pressure_angle = math.radians(pressure_angle_deg)
    module         = 2.0 * pitch_radius / teeth
    base_radius    = pitch_radius * math.cos(pressure_angle)

    x          = profile_shift
    tip_radius  = pitch_radius + (addendum_coeff + x) * module
    root_radius = max(pitch_radius - (dedendum_coeff - x) * module, 0.05 * pitch_radius)

    angular_pitch    = 2.0 * math.pi / teeth
    half_tooth_at_pitch = (math.pi / 2.0 + 2.0 * x * math.tan(pressure_angle)) / teeth
    flank_offset     = half_tooth_at_pitch + inv(pressure_angle)

    raw_flank  = build_tooth_flank(base_radius, root_radius, tip_radius, flank_samples)
    if use_trochoidal:
        raw_fillet = build_trochoidal_fillet(pitch_radius, teeth, root_radius, raw_flank[0], fillet_samples)
    else:
        raw_fillet = build_root_fillet(raw_flank[0], root_radius, fillet_samples)

    right_flank  = [rotate_xy(x, y, -flank_offset) for (x, y) in raw_flank]
    right_fillet = [rotate_xy(x, y, -flank_offset) for (x, y) in raw_fillet]
    left_flank   = [(x, -y) for (x, y) in right_flank]
    left_fillet  = [(x, -y) for (x, y) in right_fillet]

    right_root_pt    = right_fillet[-1] if right_fillet else right_flank[0]
    right_root_angle = math.atan2(right_root_pt[1], right_root_pt[0])
    left_root_angle  = -right_root_angle
    right_tip_angle  = math.atan2(right_flank[-1][1], right_flank[-1][0])
    left_tip_angle   = -right_tip_angle

    profile = []
    for i in range(teeth):
        center_angle = i * angular_pitch
        prev_left_root_world = (i - 1) * angular_pitch + left_root_angle
        curr_right_root_world = center_angle + right_root_angle
        for px, py in build_arc(root_radius, prev_left_root_world, curr_right_root_world, root_samples):
            profile.append((px, py))
        for px, py in right_fillet:
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        for px, py in right_flank:
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        tip_start = center_angle + right_tip_angle
        tip_end   = center_angle + left_tip_angle
        for px, py in build_arc(tip_radius, tip_start, tip_end, tip_samples):
            profile.append((px, py))
        for px, py in reversed(left_flank):
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        for px, py in reversed(left_fillet):
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))

    return _clean_profile(profile, pitch_radius), root_radius, tip_radius


def build_internal_gear_profile(
    pitch_radius,
    teeth,
    pressure_angle_deg,
    addendum_coeff=1.0,
    dedendum_coeff=1.25,
    profile_shift=0.0,
    flank_samples=20,
    fillet_samples=6,
    tip_samples=4,
    root_samples=4,
):
    """
    Erzeugt das Innenprofil eines Hohlrads (Internal Gear / Ring Gear).
    Zaehne zeigen nach innen: Kopfkreis < Teilkreis < Fusskreis.
    """
    if teeth < 4:
        raise ValueError("Zaehnezahl muss >= 4 sein.")
    pressure_angle = math.radians(pressure_angle_deg)
    module      = 2.0 * pitch_radius / teeth
    base_radius = pitch_radius * math.cos(pressure_angle)
    x           = profile_shift
    tip_radius  = pitch_radius - (addendum_coeff + x) * module
    root_radius = pitch_radius + (dedendum_coeff - x) * module
    if tip_radius <= 0.0:
        raise ValueError("Innenverzahnung: Teilkreisradius zu klein fuer diese Zaehnezahl.")

    angular_pitch      = 2.0 * math.pi / teeth
    half_space_at_pitch = (math.pi / 2.0 - 2.0 * x * math.tan(pressure_angle)) / teeth
    flank_offset       = half_space_at_pitch + inv(pressure_angle)

    raw_flank  = build_tooth_flank(base_radius, tip_radius, root_radius, flank_samples)
    raw_fillet = build_root_fillet(raw_flank[0], tip_radius, fillet_samples)

    right_flank  = [rotate_xy(px, py, flank_offset)  for (px, py) in raw_flank]
    right_fillet = [rotate_xy(px, py, flank_offset)  for (px, py) in raw_fillet]
    left_flank   = [(px, -py) for (px, py) in right_flank]
    left_fillet  = [(px, -py) for (px, py) in right_fillet]

    right_root_angle = math.atan2(right_flank[-1][1], right_flank[-1][0])
    left_root_angle  = -right_root_angle
    right_tip_pt     = right_fillet[-1] if right_fillet else right_flank[0]
    right_tip_angle  = math.atan2(right_tip_pt[1], right_tip_pt[0])
    left_tip_angle   = -right_tip_angle

    profile = []
    for i in range(teeth):
        center_angle = i * angular_pitch
        prev_left_root_world  = (i - 1) * angular_pitch + left_root_angle
        curr_right_root_world = center_angle + right_root_angle
        for px, py in build_arc(root_radius, prev_left_root_world, curr_right_root_world, root_samples):
            profile.append((px, py))
        for px, py in reversed(right_flank):
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        for px, py in reversed(right_fillet):
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        tip_start = center_angle + right_tip_angle
        tip_end   = center_angle + left_tip_angle
        for px, py in build_arc(tip_radius, tip_start, tip_end, tip_samples):
            profile.append((px, py))
        for px, py in left_fillet:
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))
        for px, py in left_flank:
            xr, yr = rotate_xy(px, py, center_angle)
            profile.append((xr, yr))

    return _clean_profile(profile, pitch_radius), root_radius, tip_radius


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


def _tess_fill_cap(bm, outer_loop, hole_loops, normal_z_sign):
    """Fuellt eine planare Cap aus mehreren Vertex-Loops (1 Aussenloop + N Loecher)
    robust mit mathutils.geometry.tessellate_polygon.

    Vorteil gegenueber bmesh.ops.triangle_fill: tessellate_polygon erwartet eine
    klare Hierarchie (aussen + Loecher), funktioniert auf 2D-Polygonen mit beliebig
    vielen Loechern und kann den stark nicht-konvexen Evolventen-Profilumriss
    zuverlaessig triangulieren, ohne Ueberlappungen oder fehlende Flaechen.

    normal_z_sign: +1 erwartet Normalen in +Z, -1 in -Z. Jede Dreiecks-Wicklung
    wird anhand ihrer tatsaechlichen z-Normal auf das gewuenschte Vorzeichen
    gebracht.
    """
    from mathutils.geometry import tessellate_polygon

    loops = [outer_loop]
    if hole_loops:
        loops.extend(hole_loops)

    # 2D-Koordinaten fuer die Triangulation. z wird ignoriert, da die Cap planar ist.
    coord_lists = [[v.co.xy.to_3d() for v in loop] for loop in loops]
    flat_verts  = [v for loop in loops for v in loop]

    triangles = tessellate_polygon(coord_lists)

    for tri in triangles:
        i, j, k = tri
        v0, v1, v2 = flat_verts[i], flat_verts[j], flat_verts[k]
        # 2D-Signed-Area-Test -> z-Komponente der Normalen.
        ax, ay = v0.co.x, v0.co.y
        bx, by = v1.co.x, v1.co.y
        cx, cy = v2.co.x, v2.co.y
        cross_z = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
        if normal_z_sign * cross_z < 0.0:
            v1, v2 = v2, v1
        try:
            bm.faces.new((v0, v1, v2))
        except ValueError:
            # Degenerierte Dreiecke oder bereits existierende Flaeche -> ueberspringen.
            pass


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
    hub_negative=False,
    z_offset=0.0,
    profile_shift=0.0,
    use_trochoidal=False,
    x_offset=0.0,
    phase_offset=0.0,
):
    """Erstellt ein vollstaendiges 3D-Mesh eines Evolventen-Zahnrads.

    profile_shift:  Profilverschiebungsfaktor x (DIN 3960).
    use_trochoidal: Trochoidaler Zahnfuss (DIN 3960).
    z_offset:       Verschiebung entlang Z (fuer Stacking).
    """
    profile_2d, root_radius, _tip_radius = build_gear_profile(
        pitch_radius=pitch_radius,
        teeth=teeth,
        pressure_angle_deg=pressure_angle_deg,
        profile_shift=profile_shift,
        use_trochoidal=use_trochoidal,
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
        if hub_negative:
            # Tasche darf nicht tiefer sein als der Zahnradkoerper (ggf. pro Seite).
            max_depth_per_side = 0.9 * thickness if hub_sides == "BOTH" else 0.95 * thickness
            if hub_sides == "BOTH":
                # Beidseitige Taschen duerfen sich nicht durchstossen.
                if 2.0 * hub_height >= 0.95 * thickness:
                    raise ValueError(
                        "Beidseitige negative Nabentaschen wuerden sich durchstossen. "
                        "Nabenhoehe reduzieren oder nur einseitig einstellen.")
            if hub_height >= max_depth_per_side:
                raise ValueError(
                    "Negative Nabentasche zu tief fuer die Zahnraddicke.")
    if has_holes:
        inner_clear = max(hub_radius if has_hub else 0.0, bore_radius if has_bore else 0.0)
        # Verfuegbarer Ringraum zwischen innerer Sperre (Bohrung/Nabe) und Fusskreis.
        # Ohne diese Groesse laufen die weiteren Prueflogiken leer, wenn z.B. der
        # Fusskreis kleiner als die Bohrung ist -> vermeidet Absturz durch negative
        # Abstaende in den folgenden Vergleichen.
        r_available = root_radius - inner_clear
        if r_available <= 2.0 * hole_radius:
            raise ValueError(
                "Kein Platz fuer dezentrale Bohrungen zwischen Bohrung/Nabe und Fusskreis.")
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
    # Positive Nabe: Material ragt aus dem Zahnrad heraus.
    #   hub_back:  z = -hub_height .. 0
    #   hub_front: z = thickness .. thickness + hub_height
    # Negative Nabe: Material wird aus dem Zahnrad ausgespart (Nabentasche).
    #   hub_back:  Tasche von z = 0 bis z = +hub_height (Boden innen im Zahnrad)
    #   hub_front: Tasche von z = thickness-hub_height bis z = thickness
    hub_back_bot = hub_back_top = hub_front_bot = hub_front_top = None
    if has_hub_back:
        hub_segs     = _segs_for_r(hub_radius)
        z_outer_back = +hub_height if hub_negative else -hub_height
        hub_back_bot = _add_circle_layer(bm, 0.0, 0.0, z_outer_back, hub_radius, hub_segs)
        hub_back_top = _add_circle_layer(bm, 0.0, 0.0, 0.0,          hub_radius, hub_segs)
        # Bei negativer Nabe zeigt die Zylinderwand nach INNEN (zur Achse) ->
        # reverse_winding=True. Ansonsten zeigt sie nach aussen.
        _bridge_rings(bm, hub_back_bot, hub_back_top, reverse_winding=hub_negative)
    if has_hub_front:
        hub_segs      = _segs_for_r(hub_radius)
        z_outer_front = (thickness - hub_height) if hub_negative else (thickness + hub_height)
        hub_front_bot = _add_circle_layer(bm, 0.0, 0.0, thickness,     hub_radius, hub_segs)
        hub_front_top = _add_circle_layer(bm, 0.0, 0.0, z_outer_front, hub_radius, hub_segs)
        _bridge_rings(bm, hub_front_bot, hub_front_top, reverse_winding=hub_negative)

    # --- Bohrung (erstreckt sich durch Nabe falls positiv; bei negativer Nabe
    # geht die Bohrung nur durch den Zahnradkoerper) ---
    # Wir benoetigen Bohrungsringe bei allen Stirnflaechen-Z-Werten fuer triangle_fill.
    if hub_negative:
        bore_z_start = 0.0
        bore_z_end   = thickness
    else:
        bore_z_start = -hub_height  if has_hub_back  else 0.0
        bore_z_end   =  thickness + hub_height if has_hub_front else thickness
    bore_rings   = {}  # {z_value: [BMVerts]}
    if has_bore:
        bore_segs    = _segs_for_r(bore_radius)
        bore_z_set   = {bore_z_start, 0.0, thickness, bore_z_end}
        if hub_negative:
            # Bei negativer Nabe braucht der Boden der Nabentasche einen
            # Bohrungsring auf seinem Z-Level (fuer den Ringschnitt beim Cap).
            if has_hub_back:
                bore_z_set.add(+hub_height)
            if has_hub_front:
                bore_z_set.add(thickness - hub_height)
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

    # --- Stirnflaechen (robuste Tessellation mit Loch-Unterstuetzung) ---
    def _holes(inner_ring, extras):
        hs = []
        if inner_ring is not None:
            hs.append(inner_ring)
        hs.extend(extras)
        return hs

    # Zahnrad-Rueckseite (z=0): Normalen zeigen in -Z
    inner_back = hub_back_top if has_hub_back else bore_rings.get(0.0)
    _tess_fill_cap(bm, outer_bottom, _holes(inner_back, hole_bottoms), normal_z_sign=-1)

    # Zahnrad-Vorderseite (z=thickness): Normalen zeigen in +Z
    inner_front = hub_front_bot if has_hub_front else bore_rings.get(thickness)
    _tess_fill_cap(bm, outer_top, _holes(inner_front, hole_tops), normal_z_sign=+1)

    # Naben-Rueckseite: Normalen zeigen in -Z (Aussenstirn der Nabe ODER Boden der Tasche).
    # Positiv: hub_back_bot bei z=-hub_height, bore_ring bei z=bore_z_start.
    # Negativ: hub_back_bot bei z=+hub_height, bore_ring ebenfalls dort.
    if has_hub_back:
        z_cap_back = (+hub_height) if hub_negative else bore_z_start
        _tess_fill_cap(bm, hub_back_bot, _holes(bore_rings.get(z_cap_back), []), normal_z_sign=-1)

    # Naben-Vorderseite: Normalen zeigen in +Z.
    # Positiv: hub_front_top bei z=thickness+hub_height.
    # Negativ: hub_front_top bei z=thickness-hub_height.
    if has_hub_front:
        z_cap_front = (thickness - hub_height) if hub_negative else bore_z_end
        _tess_fill_cap(bm, hub_front_top, _holes(bore_rings.get(z_cap_front), []), normal_z_sign=+1)

    # Absichtlich KEIN recalc_face_normals mehr: die expliziten normal_z_sign-Checks
    # in _fill_cap liefern korrekte Stirnflaechen-Normalen. recalc wuerde bei nicht
    # perfekt manifolder Topologie (Evolventen-Profil + Helix + Bohrungen) gelegentlich
    # Caps wieder kippen und damit den "unten offen"-Eindruck erzeugen.

    if phase_offset != 0.0:
        bmesh.ops.rotate(bm, verts=bm.verts[:],
                         cent=(0, 0, 0),
                         matrix=mathutils.Matrix.Rotation(phase_offset, 3, "Z"))
    if x_offset != 0.0 or z_offset != 0.0:
        bmesh.ops.translate(bm, vec=(x_offset, 0.0, z_offset), verts=bm.verts[:])

    bm.to_mesh(mesh)
    bm.free()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


# ================================================================
# HOHLRAD (Internal Gear / Ring Gear)
# ================================================================

def create_internal_gear_mesh(
    pitch_radius,
    teeth,
    thickness,
    pressure_angle_deg,
    ring_outer_radius,
    helix_angle_deg=0.0,
    z_offset=0.0,
    profile_shift=0.0,
    x_offset=0.0,
):
    """Erstellt ein Hohlrad (Ring Gear) mit nach innen zeigenden Zaehnen.

    ring_outer_radius: Aussenradius des Ringkoerpers (muss > Fusskreis).
    """
    profile_2d, root_radius_int, _tip_radius_int = build_internal_gear_profile(
        pitch_radius=pitch_radius,
        teeth=teeth,
        pressure_angle_deg=pressure_angle_deg,
        profile_shift=profile_shift,
    )

    if ring_outer_radius <= root_radius_int * 1.02:
        raise ValueError(
            f"Ring-Aussenradius ({ring_outer_radius*1000:.1f} mm) muss groesser als "
            f"Fusskreis der Innenverzahnung ({root_radius_int*1000:.1f} mm) sein.")

    helix_angle = math.radians(helix_angle_deg)
    layers      = _compute_helix_layers(thickness, helix_angle, pitch_radius)

    def _segs_for_r(r):
        return max(32, min(128, int(2.0 * math.pi * r / (0.005 * pitch_radius)) + 16))

    mesh = bpy.data.meshes.new("Hohlrad")
    obj  = bpy.data.objects.new("Hohlrad", mesh)
    bpy.context.collection.objects.link(obj)
    bm   = bmesh.new()

    tan_helix = math.tan(helix_angle)

    inner_layers = []
    for k in range(layers + 1):
        z       = thickness * k / layers
        phi     = z * tan_helix / pitch_radius
        cos_phi = math.cos(phi)
        sin_phi = math.sin(phi)
        inner_layers.append([
            bm.verts.new((x * cos_phi - y * sin_phi, x * sin_phi + y * cos_phi, z))
            for (x, y) in profile_2d
        ])
    for k in range(layers):
        _bridge_rings(bm, inner_layers[k], inner_layers[k + 1], reverse_winding=True)
    inner_bottom = inner_layers[0]
    inner_top    = inner_layers[-1]

    ring_segs   = _segs_for_r(ring_outer_radius)
    ring_bottom = _add_circle_layer(bm, 0.0, 0.0, 0.0,       ring_outer_radius, ring_segs)
    ring_top    = _add_circle_layer(bm, 0.0, 0.0, thickness,  ring_outer_radius, ring_segs)
    _bridge_rings(bm, ring_bottom, ring_top)

    # Ring-Caps: Aussenring = ring_{bottom,top} (grosser Kreis),
    # Inneres "Loch" = inner_{bottom,top} (Zahnprofil). tessellate_polygon fuellt
    # zuverlaessig das Annular-Gebiet zwischen Aussenkreis und gezahntem Innenrand.
    _tess_fill_cap(bm, ring_bottom, [inner_bottom], normal_z_sign=-1)
    _tess_fill_cap(bm, ring_top,    [inner_top],    normal_z_sign=+1)

    if x_offset != 0.0 or z_offset != 0.0:
        bmesh.ops.translate(bm, vec=(x_offset, 0.0, z_offset), verts=bm.verts[:])

    bm.to_mesh(mesh)
    bm.free()
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


# ================================================================
# KEGELRAD (Bevel Gear) — gerad- und spiralverzahnt
# ================================================================
#
# Geometrie-Grundlagen (Tredgold-Naeherung):
#   - Teilkegelwinkel  delta  (halber Oeffnungswinkel des Teilkegels)
#   - Aussenteilkreisradius R_o  (am "Rueckkegel", also am grossen Ende)
#   - Kegellaenge A_o = R_o / sin(delta)
#   - Zahnbreite  F  liegt entlang der Mantellinie
#   - An Mantelposition s in [0, F]:
#         Skalierung = 1 - s / A_o
#         Teilkreisradius lokal = R_o * Skalierung
#         axiale Hoehe z(s)  = -s * cos(delta)  (Richtung Kegelspitze)
#
# Das 2D-Evolventenprofil wird einmal am grossen Ende berechnet und pro
# Schicht linear auf die lokale Groesse skaliert — das entspricht der
# klassischen Tredgold-Approximation und ist optisch/funktional ausreichend.
#
# Fuer Spiralverzahnung wird jede Schicht zusaetzlich um einen Winkel phi(s)
# tangential verdreht: phi(s) = s * tan(beta) / r_mean, wobei beta der
# mittlere Spiralwinkel und r_mean der Teilkreisradius auf halber Zahnbreite
# ist. Das erzeugt einen gleichmaessigen, leicht konischen Schraubverlauf.


def _compute_bevel_layers(face_width, spiral_angle_rad):
    """Anzahl axialer Schichten fuer die Kegelradmantelung."""
    if face_width <= 0.0:
        return 1
    base = 16
    if abs(spiral_angle_rad) > 1e-9:
        base = max(base, int(math.degrees(abs(spiral_angle_rad)) / 2.0) + 16)
    return min(base, 128)


def create_bevel_gear_mesh(
    pitch_radius,
    teeth,
    face_width,
    pressure_angle_deg,
    cone_angle_deg,
    spiral_angle_deg=0.0,
    bore_radius=0.0,
    z_offset=0.0,
):
    """Erstellt ein Kegelrad (Bevel Gear) — gerad- oder spiralverzahnt.

    pitch_radius:        Teilkreisradius am grossen Ende (Rueckkegel).
    teeth:               Zaehnezahl.
    face_width:          Zahnbreite entlang der Mantellinie.
    pressure_angle_deg:  Eingriffswinkel (Druckwinkel).
    cone_angle_deg:      Teilkegelwinkel delta in Grad (45 = Miter-Paar 1:1).
    spiral_angle_deg:    Mittlerer Spiralwinkel. 0 = Geradverzahnung.
    bore_radius:         Optionale zentrale Bohrung durch den gesamten Kegel.
    z_offset:            Verschiebung entlang Z (z.B. fuer Kombinationen).
    """
    if teeth < 4:
        raise ValueError("Zaehnezahl muss >= 4 sein.")
    if face_width <= 0.0:
        raise ValueError("Zahnbreite muss > 0 sein.")

    cone_angle   = math.radians(cone_angle_deg)
    spiral_angle = math.radians(spiral_angle_deg)
    sin_d        = math.sin(cone_angle)
    cos_d        = math.cos(cone_angle)
    if sin_d < 1e-4:
        raise ValueError("Teilkegelwinkel zu klein.")

    cone_apex_dist = pitch_radius / sin_d
    if face_width >= cone_apex_dist * 0.95:
        raise ValueError("Zahnbreite zu gross fuer diesen Teilkegelwinkel.")

    profile_2d, root_radius, _tip_radius = build_gear_profile(
        pitch_radius=pitch_radius, teeth=teeth, pressure_angle_deg=pressure_angle_deg,
    )

    has_bore = bore_radius > 0.0
    if has_bore:
        inner_scale = 1.0 - face_width / cone_apex_dist
        if bore_radius >= root_radius * inner_scale * 0.95:
            raise ValueError("Bohrungsradius zu gross fuer das apex-nahe Ende des Kegelrads.")

    layers = _compute_bevel_layers(face_width, spiral_angle)

    r_back  = pitch_radius
    r_front = pitch_radius * (1.0 - face_width / cone_apex_dist)
    r_mean  = 0.5 * (r_back + r_front)
    tan_sp  = math.tan(spiral_angle)

    mesh = bpy.data.meshes.new("Kegelrad")
    obj  = bpy.data.objects.new("Kegelrad", mesh)
    bpy.context.collection.objects.link(obj)
    bm   = bmesh.new()

    slices = []
    for k in range(layers + 1):
        s     = face_width * k / layers
        scale = 1.0 - s / cone_apex_dist
        z     = -s * cos_d
        phi   = s * tan_sp / r_mean
        cos_p = math.cos(phi)
        sin_p = math.sin(phi)
        slices.append([
            bm.verts.new((
                (x * scale) * cos_p - (y * scale) * sin_p,
                (x * scale) * sin_p + (y * scale) * cos_p,
                z,
            ))
            for (x, y) in profile_2d
        ])

    for k in range(layers):
        _bridge_rings(bm, slices[k], slices[k + 1])

    # Zentrische Bohrung durch den gesamten Kegel (zylindrisch).
    bore_back = bore_front = None
    if has_bore:
        bore_segs  = max(32, int(2.0 * math.pi * bore_radius / (0.005 * pitch_radius)) + 16)
        z_back     = 0.0
        z_front    = -face_width * cos_d
        bore_back  = _add_circle_layer(bm, 0.0, 0.0, z_back,  bore_radius, bore_segs)
        bore_front = _add_circle_layer(bm, 0.0, 0.0, z_front, bore_radius, bore_segs)
        # Umgekehrte Wicklung, damit Normalen nach innen zeigen (Bohrungsinnenwand).
        _bridge_rings(bm, bore_front, bore_back, reverse_winding=True)

    def _fill_cap(outer_loop, inner_ring):
        loops = [outer_loop]
        if inner_ring is not None:
            loops.append(inner_ring)
        bmesh.ops.triangle_fill(bm, edges=_collect_loop_edges(bm, loops), use_beauty=True)

    _fill_cap(slices[0],  bore_back)    # Grosses Ende (z = 0)
    _fill_cap(slices[-1], bore_front)   # Apex-Ende    (z < 0)

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
    # UI arbeitet mit Durchmessern; die interne Berechnung nutzt weiterhin Radien.
    pitch_diameter: bpy.props.FloatProperty(
        name="Zahnraddurchmesser",
        description="Aussendurchmesser des Zahnrads (Teilkreis). Im DIN-Modus automatisch berechnet.",
        default=0.020, min=0.002, max=2.0, unit="LENGTH",
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
    hub_diameter: bpy.props.FloatProperty(
        name="Nabendurchmesser", description="Aussendurchmesser der Nabe",
        default=0.016, min=0.0002, max=2.0, unit="LENGTH",
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
    hub_negative: bpy.props.BoolProperty(
        name="Negative Nabe (Tasche)",
        description="Nabe als Vertiefung im Zahnradkoerper erzeugen (statt als Ueberstand)",
        default=False,
    )

    # --- Zentrische Bohrung ---
    use_bore: bpy.props.BoolProperty(
        name="Zentrische Bohrung", description="Bohrung entlang der Achse (durch Nabe falls vorhanden)",
        default=False,
    )
    bore_diameter: bpy.props.FloatProperty(
        name="Bohrungsdurchmesser",
        default=0.006, min=0.0002, max=2.0, unit="LENGTH",
    )

    # --- Dezentrale Bohrungen ---
    use_holes: bpy.props.BoolProperty(
        name="Dezentrale Bohrungen", description="Gewichtserleichterungs- oder Befestigungsbohrungen",
        default=False,
    )
    hole_count: bpy.props.IntProperty(name="Anzahl", default=3, min=1, max=32)
    hole_diameter: bpy.props.FloatProperty(
        name="Durchmesser", default=0.003, min=0.0002, max=2.0, unit="LENGTH",
    )
    hole_pitch_diameter: bpy.props.FloatProperty(
        name="Lochkreisdurchmesser", description="Durchmesser des Lochkreises",
        default=0.010, min=0.0002, max=2.0, unit="LENGTH",
    )

    # --- Kegelverzahnung (Bevel Gear) ---
    use_bevel: bpy.props.BoolProperty(
        name="Kegelverzahnung",
        description="Kegelrad statt Stirnrad erzeugen (deaktiviert Schraegverzahnung, Nabe, "
                    "dezentrale Bohrungen und Stacking)",
        default=False,
    )
    bevel_cone_angle: bpy.props.FloatProperty(
        name="Teilkegelwinkel",
        description="Halber Oeffnungswinkel des Teilkegels (delta). 45 = Miter-Paar 1:1",
        default=45.0, min=5.0, max=85.0,
    )
    bevel_face_width: bpy.props.FloatProperty(
        name="Zahnbreite",
        description="Laenge des Zahnes entlang der Kegelmantellinie",
        default=0.008, min=0.0001, max=1.0, unit="LENGTH",
    )
    use_spiral_bevel: bpy.props.BoolProperty(
        name="Spiralverzahnung",
        description="Spiralverzahnter Kegelrad (Spiral Bevel) statt Geradverzahnung",
        default=False,
    )
    spiral_angle: bpy.props.FloatProperty(
        name="Spiralwinkel",
        description="Mittlerer Spiralwinkel in Grad (typ. 20-45)",
        default=35.0, min=-60.0, max=60.0,
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
    stack2_pitch_diameter: bpy.props.FloatProperty(
        name="Zahnraddurchmesser", default=0.015, min=0.002, max=2.0, unit="LENGTH",
    )
    stack2_teeth: bpy.props.IntProperty(name="Zaehnezahl", default=16, min=6, max=200)
    stack2_thickness: bpy.props.FloatProperty(
        name="Dicke", default=0.005, min=0.0001, max=1.0, unit="LENGTH",
    )
    # Stufe 3
    stack3_pitch_diameter: bpy.props.FloatProperty(
        name="Zahnraddurchmesser", default=0.010, min=0.002, max=2.0, unit="LENGTH",
    )
    stack3_teeth: bpy.props.IntProperty(name="Zaehnezahl", default=10, min=6, max=200)
    stack3_thickness: bpy.props.FloatProperty(
        name="Dicke", default=0.005, min=0.0001, max=1.0, unit="LENGTH",
    )

    # --- Innenverzahnung (Hohlrad) ---
    use_internal: bpy.props.BoolProperty(
        name="Innenverzahnung (Hohlrad)",
        description="Erzeugt ein Hohlrad (Innenverzahnung) statt eines Aussen-Stirnrads",
        default=False,
    )
    internal_ring_diameter: bpy.props.FloatProperty(
        name="Ring-Aussendurchmesser",
        description="Aussendurchmesser des Hohlrad-Rings (muss groesser als Zahnraddurchmesser sein)",
        default=0.030, min=0.004, max=2.0, unit="LENGTH",
    )

    # --- DIN-3960-Modus ---
    use_din3960: bpy.props.BoolProperty(
        name="DIN-3960-Modus",
        description="Genormtes Modul (DIN 780) und Profilverschiebung x aktivieren",
        default=False,
    )
    din_module: bpy.props.EnumProperty(
        name="Modul (DIN 780)",
        description="Normmodul nach DIN 780 – bestimmt Zahngroesse und Teilkreisdurchmesser",
        items=[
            ("0.5",  "m = 0,5",  ""), ("0.6",  "m = 0,6",  ""), ("0.7",  "m = 0,7",  ""),
            ("0.8",  "m = 0,8",  ""), ("1.0",  "m = 1,0",  ""), ("1.25", "m = 1,25", ""),
            ("1.5",  "m = 1,5",  ""), ("2.0",  "m = 2,0",  ""), ("2.5",  "m = 2,5",  ""),
            ("3.0",  "m = 3,0",  ""), ("4.0",  "m = 4,0",  ""), ("5.0",  "m = 5,0",  ""),
            ("6.0",  "m = 6,0",  ""), ("8.0",  "m = 8,0",  ""), ("10.0", "m = 10,0", ""),
        ],
        default="1.0",
    )
    din_profile_shift: bpy.props.FloatProperty(
        name="Profilverschiebung x",
        description="Profilverschiebungsfaktor (DIN 3960). 0 = Normverzahnung",
        default=0.0, min=-0.8, max=0.8, step=5,
    )

    # --- Zahnrad-Paarung ---
    use_pairing: bpy.props.BoolProperty(
        name="Zahnrad-Paarung",
        description="Ein passendes Gegenrad auf dem korrekten Achsabstand erzeugen",
        default=False,
    )
    pair_teeth: bpy.props.IntProperty(
        name="Zaehnezahl Gegenrad", default=16, min=6, max=200,
    )
    pair_thickness: bpy.props.FloatProperty(
        name="Dicke Gegenrad", default=0.005, min=0.0001, max=1.0, unit="LENGTH",
    )
    pair_internal: bpy.props.BoolProperty(
        name="Gegenrad als Hohlrad",
        description="Gegenrad als Innenverzahnung (Hauptrad wird dann als Ritzel im Hohlrad platziert)",
        default=False,
    )
    # Gegenrad-Bohrung
    pair_use_bore: bpy.props.BoolProperty(
        name="Bohrung im Gegenrad", default=False,
    )
    pair_bore_diameter: bpy.props.FloatProperty(
        name="Bohrungsdurchmesser",
        default=0.004, min=0.0002, max=2.0, unit="LENGTH",
    )
    # Gegenrad-Nabe
    pair_use_hub: bpy.props.BoolProperty(
        name="Nabe im Gegenrad", default=False,
    )
    pair_hub_diameter: bpy.props.FloatProperty(
        name="Nabendurchmesser",
        default=0.010, min=0.0002, max=2.0, unit="LENGTH",
    )
    pair_hub_height: bpy.props.FloatProperty(
        name="Nabenhoehe",
        default=0.003, min=0.0001, max=1.0, unit="LENGTH",
    )
    pair_hub_sides: bpy.props.EnumProperty(
        name="Seite",
        items=[
            ("BOTH",  "Beidseitig",  ""),
            ("BACK",  "Rueckseite",  ""),
            ("FRONT", "Vorderseite", ""),
        ],
        default="BOTH",
    )
    pair_hub_negative: bpy.props.BoolProperty(
        name="Negative Nabe (Tasche)", default=False,
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

        # UI-Werte sind Durchmesser; interne Berechnung erwartet Radien -> halbieren.
        pitch_r = props.pitch_diameter * 0.5

        # DIN-3960: Modul bestimmt Teilkreis; pitch_diameter wird ueberschrieben.
        profile_shift = 0.0
        if props.use_din3960:
            m_mm = float(props.din_module)
            m = m_mm * 0.001  # Blender-Einheit = 1 m
            pitch_r = m * props.teeth / 2.0
            profile_shift = props.din_profile_shift

        if props.use_bevel:
            spiral_deg = props.spiral_angle if props.use_spiral_bevel else 0.0
            bore_r_b   = (props.bore_diameter * 0.5) if props.use_bore else 0.0
            try:
                create_bevel_gear_mesh(
                    pitch_radius=pitch_r,
                    teeth=props.teeth,
                    face_width=props.bevel_face_width,
                    pressure_angle_deg=props.pressure_angle,
                    cone_angle_deg=props.bevel_cone_angle,
                    spiral_angle_deg=spiral_deg,
                    bore_radius=bore_r_b,
                )
            except Exception as exc:
                self.report({"ERROR"}, f"Kegelrad: {exc}")
                return {"CANCELLED"}
            kind = "Spiralkegelrad" if props.use_spiral_bevel else "Kegelrad"
            self.report({"INFO"}, f"{kind} {props.teeth}Z erstellt.")
            return {"FINISHED"}

        # --- Innenverzahnung (Hohlrad) ---
        if props.use_internal:
            ring_outer_r = props.internal_ring_diameter * 0.5
            bore_r_int   = (props.bore_diameter * 0.5) if props.use_bore else 0.0
            helix_int    = props.helix_angle if props.use_helical else 0.0
            try:
                create_internal_gear_mesh(
                    pitch_radius=pitch_r,
                    teeth=props.teeth,
                    thickness=props.thickness,
                    pressure_angle_deg=props.pressure_angle,
                    ring_outer_radius=ring_outer_r,
                    helix_angle_deg=helix_int,
                    profile_shift=profile_shift,
                )
            except Exception as exc:
                self.report({"ERROR"}, f"Hohlrad: {exc}")
                return {"CANCELLED"}

            # --- optional: passendes Ritzel dazu erzeugen ---
            if props.use_pairing:
                if props.pair_teeth >= props.teeth:
                    self.report({"ERROR"},
                        "Ritzel als Gegenrad benoetigt weniger Zaehne als das Hohlrad.")
                    return {"CANCELLED"}
                pair_r      = pitch_r * props.pair_teeth / props.teeth
                center_dist = pitch_r - pair_r  # Inneneingriff: a = r_ring - r_ritzel
                helix_pair  = props.helix_angle if props.use_helical else 0.0
                p_bore_r = (props.pair_bore_diameter * 0.5) if props.pair_use_bore else 0.0
                p_hub_r  = (props.pair_hub_diameter  * 0.5) if props.pair_use_hub  else 0.0
                p_hub_h  =  props.pair_hub_height           if props.pair_use_hub  else 0.0
                p_hub_s  =  props.pair_hub_sides            if props.pair_use_hub  else "BOTH"
                p_hub_n  =  props.pair_hub_negative         if props.pair_use_hub  else False
                try:
                    create_gear_mesh(
                        pitch_radius=pair_r,
                        teeth=props.pair_teeth,
                        thickness=props.pair_thickness,
                        pressure_angle_deg=props.pressure_angle,
                        helix_angle_deg=helix_pair,
                        bore_radius=p_bore_r,
                        hub_radius=p_hub_r,
                        hub_height=p_hub_h,
                        hub_sides=p_hub_s,
                        hub_negative=p_hub_n,
                        x_offset=center_dist,
                    )
                except Exception as exc:
                    self.report({"ERROR"}, f"Paarung-Ritzel: {exc}")
                    return {"CANCELLED"}

            self.report({"INFO"}, f"Hohlrad {props.teeth}Z erstellt.")
            return {"FINISHED"}

        helix_deg = props.helix_angle if props.use_helical else 0.0
        bore_r    = (props.bore_diameter * 0.5)        if props.use_bore  else 0.0
        hole_n    =  props.hole_count                  if props.use_holes else 0
        hole_r    = (props.hole_diameter * 0.5)        if props.use_holes else 0.0
        hole_pr   = (props.hole_pitch_diameter * 0.5)  if props.use_holes else 0.0
        hub_r     = (props.hub_diameter * 0.5)         if props.use_hub   else 0.0
        hub_h     =  props.hub_height                  if props.use_hub   else 0.0
        hub_s     =  props.hub_sides                   if props.use_hub   else "BOTH"
        hub_neg   =  props.hub_negative                if props.use_hub   else False

        # Stufenparameter sammeln (immer Stufe 1 = Hauptrad)
        stages = [
            {"pitch_radius": pitch_r, "teeth": props.teeth,
             "thickness": props.thickness, "pressure_angle": props.pressure_angle},
        ]
        if props.use_stack:
            stages.append({
                "pitch_radius": props.stack2_pitch_diameter * 0.5,
                "teeth": props.stack2_teeth,
                "thickness": props.stack2_thickness,
                "pressure_angle": props.pressure_angle,
            })
            if props.stack_count >= 3:
                stages.append({
                    "pitch_radius": props.stack3_pitch_diameter * 0.5,
                    "teeth": props.stack3_teeth,
                    "thickness": props.stack3_thickness,
                    "pressure_angle": props.pressure_angle,
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
                    hub_negative=hub_neg,
                    z_offset=z,
                    profile_shift=profile_shift,
                )
            except Exception as exc:
                self.report({"ERROR"}, f"Stufe {i + 1}: {exc}")
                return {"CANCELLED"}

            z += stage["thickness"] + (props.stack_z_gap if props.use_stack else 0.0)
            created += 1

        # --- Zahnrad-Paarung: Gegenrad neben dem Hauptrad erzeugen ---
        if props.use_pairing and not props.use_stack:
            # Gegenrad-Teilradius aus gleichem Modul: r2 = r1 * z2/z1
            pair_r = pitch_r * props.pair_teeth / props.teeth
            # Gegenrad-Bohrung / Nabe (optional)
            p_bore_r = (props.pair_bore_diameter * 0.5) if props.pair_use_bore else 0.0
            p_hub_r  = (props.pair_hub_diameter  * 0.5) if props.pair_use_hub  else 0.0
            p_hub_h  =  props.pair_hub_height           if props.pair_use_hub  else 0.0
            p_hub_s  =  props.pair_hub_sides            if props.pair_use_hub  else "BOTH"
            p_hub_n  =  props.pair_hub_negative         if props.pair_use_hub  else False

            if props.pair_internal:
                # Hauptrad ist Ritzel, Gegenrad ist Hohlrad. Beide haben gleiches Modul.
                # Achsabstand bei Inneneingriff: a = r_ring - r_ritzel.
                if props.pair_teeth <= props.teeth:
                    self.report({"ERROR"},
                        "Hohlrad als Gegenrad benoetigt mehr Zaehne als das Ritzel.")
                    return {"CANCELLED"}
                module_main  = 2.0 * pitch_r / props.teeth
                ring_outer_r = pair_r + module_main * 3.0  # Fusskreis + Wandstaerke
                try:
                    create_internal_gear_mesh(
                        pitch_radius=pair_r,              # RING teilkreis (nicht pitch_r!)
                        teeth=props.pair_teeth,
                        thickness=props.pair_thickness,
                        pressure_angle_deg=props.pressure_angle,
                        ring_outer_radius=ring_outer_r,
                        helix_angle_deg=helix_deg,
                        profile_shift=0.0,
                        x_offset=(pair_r - pitch_r),       # a = r_ring - r_ritzel
                    )
                except Exception as exc:
                    self.report({"ERROR"}, f"Paarung-Hohlrad: {exc}")
                    return {"CANCELLED"}
            else:
                center_dist = pitch_r + pair_r
                try:
                    create_gear_mesh(
                        pitch_radius=pair_r,
                        teeth=props.pair_teeth,
                        thickness=props.pair_thickness,
                        pressure_angle_deg=props.pressure_angle,
                        helix_angle_deg=helix_deg,
                        bore_radius=p_bore_r,
                        hub_radius=p_hub_r,
                        hub_height=p_hub_h,
                        hub_sides=p_hub_s,
                        hub_negative=p_hub_n,
                        x_offset=center_dist,
                        phase_offset=math.pi / props.pair_teeth,
                    )
                except Exception as exc:
                    self.report({"ERROR"}, f"Paarung: {exc}")
                    return {"CANCELLED"}

        label = f"Stufenrad ({created} Stufen)" if created > 1 else f"Zahnrad {props.teeth}Z"
        self.report({"INFO"}, f"{label} erstellt.")
        return {"FINISHED"}


# ================================================================
# PANEL  (einklappbare Sub-Panels fuer einen schlanken Workflow)
# ================================================================

def _panel_gear_props(context):
    return context.scene.gear_generator


class VIEW3D_PT_gear_generator(bpy.types.Panel):
    bl_label = "Uni-Gear"
    bl_idname = "VIEW3D_PT_gear_generator"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uni-Gear"

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)

        box = layout.box()
        box.label(text="Zahnrad", icon="MESH_CIRCLE")

        # Im DIN-Modus: Durchmesser ist read-only (aus Modul berechnet).
        if props.use_din3960:
            m_mm = float(props.din_module)
            d_mm = m_mm * props.teeth
            row = box.row()
            row.enabled = False
            row.label(text=f"Zahnraddurchmesser: {d_mm:.2f} mm")
        else:
            box.prop(props, "pitch_diameter")

        box.prop(props, "teeth")
        box.prop(props, "thickness")
        box.prop(props, "pressure_angle")


class _GearSubPanel(bpy.types.Panel):
    """Gemeinsame Basis fuer einklappbare Sub-Panels unter dem Hauptpanel."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Uni-Gear"
    bl_parent_id = "VIEW3D_PT_gear_generator"
    bl_options   = {"DEFAULT_CLOSED"}

    # Unterklassen setzen diese Felder:
    toggle_prop    = ""   # Name der BoolProperty, die die Sektion aktiviert (optional).
    requires_cyl   = False  # True: Sektion ist im Kegelrad-Modus deaktiviert.

    def draw_header(self, context):
        props = _panel_gear_props(context)
        if self.toggle_prop:
            row = self.layout.row(align=True)
            if self.requires_cyl:
                row.enabled = not props.use_bevel
            row.prop(props, self.toggle_prop, text="")


class VIEW3D_PT_gear_helical(_GearSubPanel):
    bl_label    = "Schraegverzahnung"
    bl_idname   = "VIEW3D_PT_gear_helical"
    toggle_prop = "use_helical"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_helical and not props.use_bevel
        col.prop(props, "helix_angle")


class VIEW3D_PT_gear_bevel(_GearSubPanel):
    bl_label    = "Kegelverzahnung"
    bl_idname   = "VIEW3D_PT_gear_bevel"
    toggle_prop = "use_bevel"

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_bevel
        col.prop(props, "bevel_cone_angle")
        col.prop(props, "bevel_face_width")
        col.prop(props, "use_spiral_bevel", icon="FORCE_MAGNETIC")
        sub = col.column()
        sub.enabled = props.use_bevel and props.use_spiral_bevel
        sub.prop(props, "spiral_angle")


class VIEW3D_PT_gear_hub(_GearSubPanel):
    bl_label    = "Nabe (Hub)"
    bl_idname   = "VIEW3D_PT_gear_hub"
    toggle_prop = "use_hub"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_hub and not props.use_bevel
        col.prop(props, "hub_diameter")
        col.prop(props, "hub_height")
        col.prop(props, "hub_sides")
        col.prop(props, "hub_negative")


class VIEW3D_PT_gear_bore(_GearSubPanel):
    bl_label    = "Zentrische Bohrung"
    bl_idname   = "VIEW3D_PT_gear_bore"
    toggle_prop = "use_bore"
    # Kegelrad unterstuetzt zentrische Bohrung ebenfalls -> requires_cyl bleibt False.

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_bore
        col.prop(props, "bore_diameter")


class VIEW3D_PT_gear_holes(_GearSubPanel):
    bl_label    = "Dezentrale Bohrungen"
    bl_idname   = "VIEW3D_PT_gear_holes"
    toggle_prop = "use_holes"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_holes and not props.use_bevel
        col.prop(props, "hole_count")
        col.prop(props, "hole_diameter")
        col.prop(props, "hole_pitch_diameter")


class VIEW3D_PT_gear_stack(_GearSubPanel):
    bl_label    = "Stufenrad (Stacking)"
    bl_idname   = "VIEW3D_PT_gear_stack"
    toggle_prop = "use_stack"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_stack and not props.use_bevel
        col.prop(props, "stack_count")
        col.prop(props, "stack_z_gap")
        sub2 = col.box()
        sub2.label(text="Stufe 2")
        sub2.prop(props, "stack2_pitch_diameter")
        sub2.prop(props, "stack2_teeth")
        sub2.prop(props, "stack2_thickness")
        if props.stack_count >= 3:
            sub3 = col.box()
            sub3.label(text="Stufe 3")
            sub3.prop(props, "stack3_pitch_diameter")
            sub3.prop(props, "stack3_teeth")
            sub3.prop(props, "stack3_thickness")


class VIEW3D_PT_gear_din3960(_GearSubPanel):
    bl_label    = "DIN-3960-Modus"
    bl_idname   = "VIEW3D_PT_gear_din3960"
    toggle_prop = "use_din3960"

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_din3960
        col.prop(props, "din_module")
        col.prop(props, "din_profile_shift")

        # Berechneter Durchmesser als Info-Label
        if props.use_din3960:
            m_mm = float(props.din_module)
            d_mm = m_mm * props.teeth
            col.label(text=f"→ Zahnraddurchmesser: {d_mm:.2f} mm", icon="INFO")
            # Unterschnitt-Warnung
            alpha = math.radians(props.pressure_angle)
            z_min = 2.0 / math.sin(alpha) ** 2
            x_min = (z_min - props.teeth) / z_min
            if props.teeth < z_min and props.din_profile_shift < x_min:
                col.label(text=f"⚠ Unterschnitt! x_min ≈ {x_min:.2f}", icon="ERROR")


class VIEW3D_PT_gear_internal(_GearSubPanel):
    bl_label    = "Innenverzahnung (Hohlrad)"
    bl_idname   = "VIEW3D_PT_gear_internal"
    toggle_prop = "use_internal"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_internal and not props.use_bevel
        col.prop(props, "internal_ring_diameter")


class VIEW3D_PT_gear_pairing(_GearSubPanel):
    bl_label    = "Zahnrad-Paarung"
    bl_idname   = "VIEW3D_PT_gear_pairing"
    toggle_prop = "use_pairing"
    requires_cyl = True

    def draw(self, context):
        layout = self.layout
        props  = _panel_gear_props(context)
        col = layout.column()
        col.enabled = props.use_pairing and not props.use_bevel
        col.prop(props, "pair_teeth")
        col.prop(props, "pair_thickness")
        col.prop(props, "pair_internal")

        # Gegenrad-Bohrung
        box_b = col.box()
        box_b.prop(props, "pair_use_bore")
        sub_b = box_b.column()
        sub_b.enabled = props.pair_use_bore
        sub_b.prop(props, "pair_bore_diameter")

        # Gegenrad-Nabe
        box_h = col.box()
        box_h.prop(props, "pair_use_hub")
        sub_h = box_h.column()
        sub_h.enabled = props.pair_use_hub
        sub_h.prop(props, "pair_hub_diameter")
        sub_h.prop(props, "pair_hub_height")
        sub_h.prop(props, "pair_hub_sides")
        sub_h.prop(props, "pair_hub_negative")

        # Achsabstand als Info
        if props.use_pairing and not props.use_bevel:
            if props.use_din3960:
                m_mm = float(props.din_module)
                m = m_mm * 0.001
                r1 = m * props.teeth / 2.0
            else:
                r1 = props.pitch_diameter * 0.5
            r2 = r1 * props.pair_teeth / props.teeth
            if props.pair_internal:
                a_mm = abs(r1 - r2) * 1000.0
                col.label(text=f"→ Achsabstand: {a_mm:.2f} mm (Inneneingriff)", icon="INFO")
            else:
                a_mm = (r1 + r2) * 1000.0
                col.label(text=f"→ Achsabstand: {a_mm:.2f} mm", icon="INFO")


class VIEW3D_PT_gear_footer(bpy.types.Panel):
    """Footer-Panel: Erstellen-Button immer am Ende aller Sub-Panels sichtbar."""
    bl_label    = ""
    bl_idname   = "VIEW3D_PT_gear_footer"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "Uni-Gear"
    bl_parent_id   = "VIEW3D_PT_gear_generator"
    bl_options     = {"HIDE_HEADER"}
    bl_order       = 999  # ganz nach unten sortiert

    def draw(self, context):
        row = self.layout.row()
        row.scale_y = 1.6
        row.operator("mesh.create_gear", icon="MESH_CIRCLE", text="Zahnrad erstellen")


# ================================================================
# REGISTRATION
# ================================================================

_classes = (
    GearGeneratorProperties,
    MESH_OT_create_gear,
    VIEW3D_PT_gear_generator,
    VIEW3D_PT_gear_helical,
    VIEW3D_PT_gear_bevel,
    VIEW3D_PT_gear_hub,
    VIEW3D_PT_gear_bore,
    VIEW3D_PT_gear_holes,
    VIEW3D_PT_gear_stack,
    VIEW3D_PT_gear_din3960,
    VIEW3D_PT_gear_internal,
    VIEW3D_PT_gear_pairing,
    VIEW3D_PT_gear_footer,
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
