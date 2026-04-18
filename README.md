# Uni-Gear – Parametric Gear Generator

*In anderer Sprache lesen: **Deutsch** · [English](README_EN.md)*

**Ein schlankes Blender-Add-on zur schnellen Erstellung parametrischer Zahnräder**

Erstelle realistische Zahnräder mit nur wenigen Klicks direkt im N-Panel.  
Ideal für Mechanik-Konstruktionen, 3D-Druck, Animationen, technische Visualisierungen und Game-Assets.

![Zahnrad Generator Screenshot](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/screenshot.png)

## ✨ Features

- ✅ Voll parametrisch: Zahnraddurchmesser, Zähnezahl, Dicke, Eingriffswinkel
- ✅ Echte Evolventenverzahnung nach DIN-867-Bezugsprofil (`h_aP* = 1.0`, `h_fP* = 1.25`)
- ✅ Korrekte Teilkreis-Zahndicke `π·m/2` per `inv(α) = tan(α) − α`
- ✅ Tangential geblendeter Kreisbogen-Fillet am Zahnfuß (trochoidale Näherung)
- ✅ Optionale Schrägverzahnung mit einstellbarem Schrägungswinkel
- ✅ Optionale Nabe (Hub) – ein- oder beidseitig
- ✅ Optionale zentrische Bohrung (durchgehend durch Nabe und Kegel)
- ✅ Optionale dezentrale Entlastungs-/Befestigungsbohrungen (Anzahl, Radius, Lochkreis)
- ✅ Stufenrad / Stacking: bis zu 3 Zahnradstufen auf einer Achse
- ✅ Kegelverzahnung (Bevel Gear) – gerad- und spiralverzahnt
- ✅ Innenverzahnung (Hohlrad / Ring Gear)
- ✅ DIN-3960-Modus: Normmodul (DIN 780), Profilverschiebung `x`, Unterschnitt-Warnung
- ✅ Zahnrad-Paarung: Gegenrad automatisch auf korrektem Achsabstand
- ✅ Eigene GUI im N-Panel (Tab „Uni-Gear") mit erhaltener Einstellung
- ✅ Ein-Klick-Erstellung mit Undo-Support
- ✅ Sauberer Blender-Python-Code (bmesh)
- ✅ MIT License – frei nutzbar und modifizierbar

## 📥 Installation

1. Lade die Datei [`gear_generator.py`](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/gear_generator.py) herunter  
2. In Blender: **Edit → Preferences → Add-ons → Install**  
3. Wähle die heruntergeladene `.py`-Datei aus  
4. Aktiviere das Add-on „Uni-Gear"  
5. Drücke `N` → Tab **Uni-Gear** → „Zahnrad erstellen"

## 🚀 Verwendung

1. Im 3D-Viewport die Sidebar mit `N` öffnen  
2. Zum Tab **Uni-Gear** wechseln  
3. Parameter anpassen (optionale Sektionen per Toggle aktivieren)  
4. Auf **„Zahnrad erstellen"** klicken  

Das Zahnrad wird direkt als neues Objekt in der Szene erstellt.

## Parameter

> Alle Längen werden als **Durchmesser** angegeben (nicht als Radius) – so wie
> Zahnräder in der Praxis bezeichnet werden (z. B. „20 mm Zahnrad"). Intern
> rechnet das Add-on weiterhin radienbasiert.

### Zahnrad

| Parameter              | Beschreibung                          | Standardwert |
|------------------------|---------------------------------------|--------------|
| Zahnraddurchmesser     | Teilkreisdurchmesser des Zahnrads     | 20 mm        |
| Zähnezahl              | Anzahl der Zähne                      | 24           |
| Dicke                  | Zahnbreite (axiale Dicke)             | 5 mm         |
| Eingriffswinkel        | Druckwinkel in Grad                   | 20°          |

### Schrägverzahnung (optional)

| Parameter          | Beschreibung                          | Standardwert |
|--------------------|---------------------------------------|--------------|
| Schrägungswinkel   | Helix-Winkel in Grad (−45…45)         | 15°          |

### Zentrische Bohrung (optional)

| Parameter              | Beschreibung                      | Standardwert |
|------------------------|-----------------------------------|--------------|
| Bohrungsdurchmesser    | Durchmesser der Mittelbohrung     | 6 mm         |

### Dezentrale Bohrungen (optional)

| Parameter              | Beschreibung                              | Standardwert |
|------------------------|-------------------------------------------|--------------|
| Anzahl                 | Anzahl gleichmäßig verteilter Löcher      | 3            |
| Durchmesser            | Durchmesser jedes Lochs                   | 3 mm         |
| Lochkreisdurchmesser   | Durchmesser, auf dem die Löcher liegen    | 10 mm        |

### Nabe (optional)

| Parameter          | Beschreibung                                              | Standardwert |
|--------------------|-----------------------------------------------------------|--------------|
| Nabendurchmesser   | Außendurchmesser der zylindrischen Nabe                   | 16 mm        |
| Nabenhöhe          | Überstand bzw. Tiefe der Nabe                             | 4 mm         |
| Seite              | Beidseitig / nur Rückseite / nur Vorderseite              | Beidseitig   |
| Negative Nabe      | Nabe als Vertiefung im Zahnradkörper statt als Überstand  | aus          |

### Stufenrad / Stacking (optional)

| Parameter          | Beschreibung                                            | Standardwert |
|--------------------|---------------------------------------------------------|--------------|
| Stufen gesamt      | Anzahl Zahnradstufen auf der gemeinsamen Achse          | 2            |
| Abstand            | Axialer Luftspalt zwischen zwei Stufen                  | 0 mm         |
| Stufe 2/3          | Eigener Teilkreisdurchmesser, Zähnezahl und Dicke       | —            |

### Kegelverzahnung (optional)

| Parameter          | Beschreibung                                              | Standardwert |
|--------------------|-----------------------------------------------------------|--------------|
| Teilkegelwinkel    | Halber Öffnungswinkel des Teilkegels δ (45° = Miter 1:1)  | 45°          |
| Zahnbreite         | Zahnlänge entlang der Kegelmantellinie                    | 8 mm         |
| Spiralverzahnung   | Gerad- oder spiralverzahntes Kegelrad                     | aus          |
| Spiralwinkel       | Mittlerer Spiralwinkel (bei Spiralverzahnung)             | 35°          |

> Hinweis: Im Kegelrad-Modus sind Schrägverzahnung, Nabe, dezentrale Bohrungen und
> Stacking deaktiviert. Eine zentrische Bohrung kann zusätzlich eingeschaltet werden.

### Innenverzahnung – Hohlrad (optional)

| Parameter              | Beschreibung                                                   | Standardwert |
|------------------------|----------------------------------------------------------------|--------------|
| Ring-Außendurchmesser  | Außendurchmesser des Hohlrad-Rings (> Zahnraddurchmesser)     | 30 mm        |

### DIN-3960-Modus (optional)

| Parameter            | Beschreibung                                                           | Standardwert |
|----------------------|------------------------------------------------------------------------|--------------|
| Modul (DIN 780)      | Normmodul m – bestimmt Zahnraddurchmesser: d = m · z                  | 1,0 mm       |
| Profilverschiebung x | Profilverschiebungsfaktor nach DIN 3960 (0 = Normverzahnung)          | 0,0          |

> Im DIN-Modus wird der Zahnraddurchmesser automatisch aus Modul und Zähnezahl berechnet.
> Das Panel zeigt eine Unterschnitt-Warnung, wenn x < x_min für die gewählte Zähnezahl.

### Zahnrad-Paarung (optional)

| Parameter            | Beschreibung                                                  | Standardwert |
|----------------------|---------------------------------------------------------------|--------------|
| Zähnezahl Gegenrad   | Zähnezahl des automatisch erzeugten Gegenrads                | 16           |
| Dicke Gegenrad       | Axiale Dicke des Gegenrads                                    | 5 mm         |
| Gegenrad als Hohlrad | Gegenrad als Innenverzahnung erzeugen                        | aus          |
| Bohrung im Gegenrad  | Zentrische Bohrung im Gegenrad (Durchmesser einstellbar)     | aus          |
| Nabe im Gegenrad     | Nabe im Gegenrad (Durchmesser, Höhe, Seite, negativ)         | aus          |

## Roadmap (nächste Versionen)

Erledigt:

- [x] Echte Evolventen-Zahnform
- [x] Schrägverzahnung (Helix)
- [x] Automatische Bohrung (zentrisch + dezentrale Entlastungslöcher)
- [x] Nabe (Hub) – ein- oder beidseitig, kombinierbar mit der Bohrung
- [x] Zahnradkombination / Stacking (mehrere Räder auf einer Achse, z. B. Stufenräder)
- [x] Kegelverzahnung (Bevel Gear, gerad- und spiralverzahnt)
- [x] Innenverzahnung (Hohlrad / Ring Gear)
- [x] DIN-3960-Modus: Normmodul (DIN 780), Profilverschiebung `x`, Unterschnitt-Warnung
- [x] Zahnrad-Paarung (Gegenrad auf korrektem Achsabstand, inkl. Bohrung/Nabe im Gegenrad)
- [x] Negative Nabe (Nabentasche im Zahnradkörper)

Offen:

- [ ] Flankenspiel (Backlash)
- [ ] Zahnstange (Rack)
- [ ] Automatisches Rigging (Rotation via Driver)
- [ ] Modul-Eingabe als Freitexteingabe (zusätzlich zum DIN-Dropdown)
- [ ] Vorschau-Modus (Modal Operator mit Live-Preview)
- [ ] Echte Trochoide am Zahnfuß (DIN 3960 vollständig)

## Mitwirken

Du hast Ideen für Verbesserungen?  
Einfach einen Issue oder Pull Request öffnen – ich freue mich über jeden Beitrag! ❤️

## Lizenz

[MIT License](LICENSE) – du darfst das Add-on frei verwenden, verändern und weiterverbreiten.

---

**Made with ❤️ für die Blender-Community**
