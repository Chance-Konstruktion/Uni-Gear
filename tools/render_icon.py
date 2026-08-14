"""Rendert das Projektbild aus dem Add-on selbst.

Der Punkt: hier wird kein Zahnrad nachgebaut, das aussieht wie eines aus
Uni-Gear. Es laeuft ``create_gear_mesh`` aus ``gear_generator.py`` --
dieselbe Funktion, die auch im N-Panel auf "Zahnrad erstellen" haengt.
Was auf dem Bild steht, kann das Add-on also nachweislich.

Das hat einen Nebennutzen: aendert jemand die Verzahnung so, dass sie
bricht, faellt der Bildjob aus, bevor jemand die Datei installiert.

Laeuft headless mit dem PyPI-Modul ``bpy``, ohne Blender-Oberflaeche:

    python tools/render_icon.py
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import sys

import bpy
import mathutils

WURZEL = pathlib.Path(__file__).resolve().parents[1]
AUSGABE = WURZEL / "icon.png"
KANTE = 1024  # gross gerendert, das Verkleinern macht GitLab sauberer als wir


def leere_szene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def lade_addon():
    """``gear_generator.py`` laden, ohne es zu installieren.

    Das Add-on ruft beim Import kein ``register()`` auf, deshalb genuegt
    ein gewoehnlicher Modul-Import -- und wir bekommen die Bau-Funktion
    direkt, ohne den Umweg ueber einen Operator, der einen UI-Kontext
    braeuchte.
    """
    pfad = WURZEL / "gear_generator.py"
    spec = importlib.util.spec_from_file_location("gear_generator", pfad)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["gear_generator"] = modul
    spec.loader.exec_module(modul)
    return modul


def baue_zahnrad(modul):
    """Ein Rad, das zeigt, was das Add-on kann, ohne unruhig zu werden.

    18 Zaehne, weil bei weniger die Evolvente am Fuss kaum sichtbar ist
    und bei mehr die einzelnen Zaehne im Icon zu Rauschen verschmelzen.
    Nabe, Bohrung und fuenf Entlastungsloecher sind da, damit das Bild
    nicht nur eine Scheibe mit Zacken ist, sondern ein Maschinenteil.
    """
    obj = modul.create_gear_mesh(
        pitch_radius=1.0,
        teeth=18,
        thickness=0.30,
        pressure_angle_deg=20.0,
        helix_angle_deg=0.0,
        bore_radius=0.17,
        hole_count=5,
        hole_radius=0.16,
        hole_pitch_radius=0.55,
        hub_radius=0.34,
        hub_height=0.16,
        hub_sides="BOTH",
        use_trochoidal=True,
    )
    return obj


def material(obj, farbe, rauheit=0.32):
    mat = bpy.data.materials.new("Metall")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = farbe
    bsdf.inputs["Metallic"].default_value = 1.0
    bsdf.inputs["Roughness"].default_value = rauheit
    obj.data.materials.append(mat)


def kanten_brechen(obj, breite) -> None:
    """Eine winzige Fase auf jede Kante.

    Ohne sie sieht poliertes Metall im Kleinen flach aus: eine perfekt
    scharfe Kante hat keine Breite und faengt deshalb kein Licht. Die
    Fase ist das, was ein Zahnrad im Bild als Metall lesbar macht.
    """
    bpy.context.view_layer.objects.active = obj
    fase = obj.modifiers.new("Fase", "BEVEL")
    fase.width = breite
    fase.segments = 2
    fase.limit_method = "ANGLE"
    fase.angle_limit = math.radians(30)
    glatt = obj.modifiers.new("Glaetten", "WEIGHTED_NORMAL")
    glatt.keep_sharp = True
    for flaeche in obj.data.polygons:
        flaeche.use_smooth = True


def ausdehnung(obj) -> float:
    weit = 0.0
    for ecke in obj.bound_box:
        punkt = obj.matrix_world @ mathutils.Vector(ecke)
        weit = max(weit, max(abs(punkt[i]) for i in range(3)))
    return weit or 1.0


def licht(name, richtung, staerke, groesse, weite):
    """Lampen mitwachsen lassen statt feste Zahlen zu setzen.

    Ort und Groesse haengen an der Ausdehnung des Teils, die Leistung an
    deren Quadrat -- damit bleibt die Ausleuchtung gleich, egal ob das
    Teil einen Meter misst oder vierzig Millimeter. Uni-Pulley baut in
    Millimetern, dieses Add-on in Metern; ohne das waere eines der
    beiden Bilder schwarz und das andere ausgebrannt.
    """
    daten = bpy.data.lights.new(name, type="AREA")
    daten.energy = staerke * weite * weite
    daten.size = groesse * weite
    lampe = bpy.data.objects.new(name, daten)
    bpy.context.collection.objects.link(lampe)
    lampe.location = tuple(k * weite for k in richtung)
    richte_auf(lampe, (0.0, 0.0, 0.0))
    return lampe


def richte_auf(objekt, ziel) -> None:
    richtung = mathutils.Vector(ziel) - objekt.location
    objekt.rotation_euler = richtung.to_track_quat("-Z", "Y").to_euler()


def kamera(weite):
    """Schraege Draufsicht, orthografisch.

    Perspektive kippt bei einem runden Teil die Zahnkraenze gegeneinander
    und laesst es schief wirken. Orthografisch bleibt der Kranz ein Kreis,
    und die Neigung zeigt trotzdem die Dicke -- das eine, was eine
    Draufsicht nicht zeigen kann.

    Der Ausschnitt wird eingepasst statt geraten: die groesste Ausdehnung
    mal 2,55 laesst genug Rand, dass der runde Zuschnitt eines Icons die
    Zaehne nicht anschneidet.
    """
    daten = bpy.data.cameras.new("Kamera")
    daten.type = "ORTHO"
    daten.ortho_scale = weite * 2.55
    kam = bpy.data.objects.new("Kamera", daten)
    bpy.context.collection.objects.link(kam)
    kam.location = (2.6 * weite, -2.6 * weite, 2.35 * weite)
    richte_auf(kam, (0.0, 0.0, 0.0))
    bpy.context.scene.camera = kam
    return kam


def welt(helligkeit=0.25) -> None:
    w = bpy.data.worlds.new("Welt")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (
        0.55, 0.6, 0.7, 1.0)
    w.node_tree.nodes["Background"].inputs[1].default_value = helligkeit
    bpy.context.scene.world = w


def rendere(ziel: pathlib.Path) -> None:
    szene = bpy.context.scene
    szene.render.engine = "CYCLES"
    szene.cycles.device = "CPU"
    szene.cycles.samples = 160
    szene.cycles.use_denoising = True
    # Transparenter Hintergrund: das Icon steht bei GitLab auf hellem wie
    # auf dunklem Grund, und ein eingebackenes Weiss faellt im dunklen
    # Modus als Kasten auf.
    szene.render.film_transparent = True
    szene.render.resolution_x = KANTE
    szene.render.resolution_y = KANTE
    szene.render.image_settings.file_format = "PNG"
    szene.render.image_settings.color_mode = "RGBA"
    szene.render.filepath = str(ziel)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    leere_szene()
    modul = lade_addon()
    rad = baue_zahnrad(modul)
    weite = ausdehnung(rad)
    kanten_brechen(rad, weite * 0.006)
    # Warmer Stahl mit einem Stich ins Messing -- unterscheidbar vom
    # kuehlen Aluminium, das Uni-Pulley bekommt. Die beiden Projekte
    # stehen in derselben Liste nebeneinander.
    material(rad, (0.62, 0.52, 0.34, 1.0))

    # Dieselben drei Lampen wie bei Uni-Pulley, an denselben Stellen.
    licht("Fuehrung", (1.3, -1.15, 1.6), 140.0, 2.7, weite)
    licht("Aufhellung", (-1.4, -0.6, 0.6), 40.0, 3.5, weite)
    licht("Kante", (-0.45, 1.4, 0.9), 65.0, 1.9, weite)
    welt()
    kamera(weite)
    rendere(AUSGABE)
    print("geschrieben: %s (Ausdehnung %.3f)" % (AUSGABE, weite))


if __name__ == "__main__":
    main()
