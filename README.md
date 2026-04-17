# Uni-Gear – Parametric Gear Generator

**Ein schlankes Blender-Add-on zur schnellen Erstellung parametrischer Zahnräder**

Erstelle realistische Zahnräder mit nur wenigen Klicks direkt im N-Panel.  
Ideal für Mechanik-Konstruktionen, 3D-Druck, Animationen, technische Visualisierungen und Game-Assets.

![Zahnrad Generator Screenshot](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/screenshot.png)  
*(Screenshot wird später eingefügt – einfach ein Bild von der Sidebar machen und hochladen)*

## ✨ Features

- ✅ Voll parametrisch: Teilkreisradius, Zähnezahl, Dicke, Eingriffswinkel
- ✅ Echte Evolventenverzahnung nach DIN-867-Bezugsprofil (`h_aP* = 1.0`, `h_fP* = 1.25`)
- ✅ Korrekte Teilkreis-Zahndicke `π·m/2` per `inv(α) = tan(α) − α`
- ✅ Tangential geblendeter Kreisbogen-Fillet am Zahnfuß
- ✅ Optionale Schrägverzahnung mit einstellbarem Schrägungswinkel
- ✅ Optionale zentrische Bohrung
- ✅ Optionale dezentrale Entlastungs-/Befestigungsbohrungen (Anzahl, Radius, Lochkreis)
- ✅ Eigene GUI im N-Panel (Tab „Erstellen") mit erhaltener Einstellung
- ✅ Ein-Klick-Erstellung mit Undo-Support
- ✅ Sauberer Blender-Python-Code (bmesh)
- ✅ MIT License – frei nutzbar und modifizierbar

## 📥 Installation

1. Lade die Datei [`gear_generator.py`](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/gear_generator.py) herunter  
2. In Blender: **Edit → Preferences → Add-ons → Install**  
3. Wähle die heruntergeladene `.py`-Datei aus  
4. Aktiviere das Add-on „Parametric Gear Generator"  
5. Drücke `N` → Tab **Erstellen** → „Evolventen Zahnrad"

## 🚀 Verwendung

1. Im 3D-Viewport die Sidebar mit `N` öffnen  
2. Zum Tab **Erstellen** wechseln  
3. Parameter anpassen (optionale Sektionen per Toggle aktivieren)  
4. Auf **„Zahnrad erstellen"** klicken  

Das Zahnrad wird direkt als neues Objekt in der Szene erstellt.

## Parameter

### Zahnrad

| Parameter          | Beschreibung                          | Standardwert |
|--------------------|---------------------------------------|--------------|
| Teilkreisradius    | Radius des Teilkreises                | 20 mm        |
| Zähnezahl          | Anzahl der Zähne                      | 24           |
| Dicke              | Zahnbreite (axiale Dicke)             | 5 mm         |
| Eingriffswinkel    | Druckwinkel in Grad                   | 20°          |

### Schrägverzahnung (optional)

| Parameter          | Beschreibung                          | Standardwert |
|--------------------|---------------------------------------|--------------|
| Schrägungswinkel   | Helix-Winkel in Grad (−45…45)         | 15°          |

### Zentrische Bohrung (optional)

| Parameter          | Beschreibung                          | Standardwert |
|--------------------|---------------------------------------|--------------|
| Bohrungsradius     | Radius der Mittelbohrung              | 4 mm         |

### Dezentrale Bohrungen (optional)

| Parameter          | Beschreibung                          | Standardwert |
|--------------------|---------------------------------------|--------------|
| Anzahl             | Anzahl gleichmäßig verteilter Löcher  | 6            |
| Radius             | Radius jedes Lochs                    | 2 mm         |
| Lochkreisradius    | Radius, auf dem die Löcher liegen     | 10 mm        |

## Roadmap (nächste Versionen)

Erledigt:

- [x] Echte Evolventen-Zahnform
- [x] Schrägverzahnung (Helix)
- [x] Automatische Bohrung (zentrisch + dezentrale Entlastungslöcher)

Offen:

- [ ] Innenverzahnung (Internal Gear / Hohlrad)
- [ ] Zahnrad-Paarung (zwei Räder passend zueinander, inkl. Achsabstand)
- [ ] Zahnradkombination / Stacking (mehrere Räder auf einer Achse, z. B. Stufenräder)
- [ ] Kegelverzahnung (Bevel Gear, gerad- und spiralverzahnt)
- [ ] Nabe (Hub) – als Alternative oder in Kombination mit der Bohrung
- [ ] DIN-3960-Modus: Modul-Dropdown (DIN 780), Profilverschiebung `x`, echte Trochoide am Zahnfuß, Unterschnitt-Warnung

## Mitwirken

Du hast Ideen für Verbesserungen?  
Einfach einen Issue oder Pull Request öffnen – ich freue mich über jeden Beitrag! ❤️

## Lizenz

[MIT License](LICENSE) – du darfst das Add-on frei verwenden, verändern und weiterverbreiten.

---

**Made with ❤️ für die Blender-Community**
