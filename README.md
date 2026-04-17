# Uni-Gear – Parametric Gear Generator

**Ein schlankes Blender-Add-on zur schnellen Erstellung parametrischer Zahnräder**

Erstelle realistische Zahnräder mit nur wenigen Klicks direkt im N-Panel.  
Ideal für Mechanik-Konstruktionen, 3D-Druck, Animationen, technische Visualisierungen und Game-Assets.

![Zahnrad Generator Screenshot](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/screenshot.png)  
*(Screenshot wird später eingefügt – einfach ein Bild von der Sidebar machen und hochladen)*

## ✨ Features

- ✅ Voll parametrisch: Teilkreisradius, Zähnezahl, Dicke, Zahntiefe  
- ✅ Trapez-Zahnform (realistisch wirkend)  
- ✅ Eigene GUI im N-Panel (Tab „Erstellen“)  
- ✅ Einstellungen bleiben erhalten  
- ✅ Ein-Klick-Erstellung mit Undo-Support  
- ✅ Sauberer Blender-Python-Code (bmesh)  
- ✅ MIT License – frei nutzbar und modifizierbar  

## 📥 Installation

1. Lade die Datei [`gear_generator.py`](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/gear_generator.py) herunter  
2. In Blender: **Edit → Preferences → Add-ons → Install**  
3. Wähle die heruntergeladene `.py`-Datei aus  
4. Aktiviere das Add-on „Parametric Gear Generator“  
5. Drücke `N` → Tab **Erstellen** → „Zahnrad Generator“

## 🚀 Verwendung

1. Im 3D-Viewport die Sidebar mit `N` öffnen  
2. Zum Tab **Erstellen** wechseln  
3. Parameter anpassen  
4. Auf **„Zahnrad erstellen“** klicken  

Das Zahnrad wird direkt als neues Objekt in der Szene erstellt.

## Parameter

| Parameter          | Beschreibung                     | Standardwert |
|--------------------|----------------------------------|--------------|
| Radius (Teilkreis) | Teilkreisradius                  | 1.0 m        |
| Anzahl Zähne       | Zähnezahl                        | 24           |
| Dicke              | Materialdicke                    | 0.3 m        |
| Zahntiefe          | Höhe eines Zahns                 | 0.25 m       |

## Roadmap (nächste Versionen)

- [ ] Innenverzahnung (Internal Gear)  
- [ ] Schrägverzahnung (Helix)  
- [ ] Echte Evolventen-Zahnform  
- [ ] Automatische Bohrung / Nabe  
- [ ] Zahnrad-Paarung (zwei Räder passend zueinander)  

## Mitwirken

Du hast Ideen für Verbesserungen?  
Einfach einen Issue oder Pull Request öffnen – ich freue mich über jeden Beitrag! ❤️

## Lizenz

[MIT License](LICENSE) – du darfst das Add-on frei verwenden, verändern und weiterverbreiten.

---

**Made with ❤️ für die Blender-Community**
