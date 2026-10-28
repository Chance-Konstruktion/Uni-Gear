"""Pure gear mathematics and involute-profile generation; no Blender dependencies."""

import math

def inv(alpha):
    """Klassische Evolventenfunktion inv(alpha) = tan(alpha) - alpha."""
    return math.tan(alpha) - alpha


def _validate_gear_profile_inputs(
    pitch_radius,
    teeth,
    pressure_angle_deg,
    addendum_coeff,
    dedendum_coeff,
    profile_shift,
    flank_samples,
    fillet_samples,
    tip_samples,
    root_samples,
):
    """Reject invalid inputs before trigonometry or mesh construction."""
    numeric_fields = {
        "Teilkreisradius": pitch_radius,
        "Eingriffswinkel": pressure_angle_deg,
        "Kopfhoehenfaktor": addendum_coeff,
        "Fusshoehenfaktor": dedendum_coeff,
        "Profilverschiebung": profile_shift,
    }
    for label, value in numeric_fields.items():
        try:
            finite_value = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{label} muss eine endliche Zahl sein.") from exc
        if not math.isfinite(finite_value):
            raise ValueError(f"{label} muss eine endliche Zahl sein.")

    if pitch_radius <= 0.0:
        raise ValueError("Teilkreisradius muss > 0 sein.")
    if not isinstance(teeth, int) or isinstance(teeth, bool) or teeth < 4:
        raise ValueError("Zaehnezahl muss eine ganze Zahl >= 4 sein.")
    if not 0.0 < pressure_angle_deg < 90.0:
        raise ValueError("Eingriffswinkel muss zwischen 0 und 90 Grad liegen.")
    if addendum_coeff <= 0.0 or dedendum_coeff <= 0.0:
        raise ValueError("Kopf- und Fusshoehenfaktor muessen > 0 sein.")

    sample_counts = {
        "Flankensampling": (flank_samples, 1),
        "Fillet-Sampling": (fillet_samples, 0),
        "Kopfkreis-Sampling": (tip_samples, 0),
        "Fusskreis-Sampling": (root_samples, 0),
    }
    for label, (count, minimum) in sample_counts.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < minimum:
            raise ValueError(f"{label} muss eine ganze Zahl >= {minimum} sein.")


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
    flank_samples=10,
    fillet_samples=3,
    tip_samples=2,
    root_samples=2,
):
    """
    Erzeugt das geschlossene 2D-Profil eines Evolventen-Zahnrads.

    profile_shift:  Profilverschiebungsfaktor x (DIN 3960). 0 = Nullrad.
    use_trochoidal: Trochoidaler Zahnfuss statt einfachem Kreisbogen-Fillet.
    """
    _validate_gear_profile_inputs(
        pitch_radius, teeth, pressure_angle_deg, addendum_coeff, dedendum_coeff,
        profile_shift, flank_samples, fillet_samples, tip_samples, root_samples,
    )
    pressure_angle = math.radians(pressure_angle_deg)
    module         = 2.0 * pitch_radius / teeth
    base_radius    = pitch_radius * math.cos(pressure_angle)

    x          = profile_shift
    tip_radius  = pitch_radius + (addendum_coeff + x) * module
    root_radius = max(pitch_radius - (dedendum_coeff - x) * module, 0.05 * pitch_radius)
    if tip_radius <= base_radius or root_radius <= 0.0:
        raise ValueError("Zahnprofil ist mit diesen Parametern nicht geometrisch gueltig.")

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
    flank_samples=10,
    fillet_samples=3,
    tip_samples=2,
    root_samples=2,
):
    """
    Erzeugt das Innenprofil eines Hohlrads (Internal Gear / Ring Gear).
    Zaehne zeigen nach innen: Kopfkreis < Teilkreis < Fusskreis.
    """
    _validate_gear_profile_inputs(
        pitch_radius, teeth, pressure_angle_deg, addendum_coeff, dedendum_coeff,
        profile_shift, flank_samples, fillet_samples, tip_samples, root_samples,
    )
    pressure_angle = math.radians(pressure_angle_deg)
    module      = 2.0 * pitch_radius / teeth
    base_radius = pitch_radius * math.cos(pressure_angle)
    x           = profile_shift
    tip_radius  = pitch_radius - (addendum_coeff + x) * module
    root_radius = pitch_radius + (dedendum_coeff - x) * module
    if tip_radius <= 0.0 or root_radius <= tip_radius:
        raise ValueError("Innenverzahnung: Teilkreisradius/Profilverschiebung ergibt kein gueltiges Profil.")

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


