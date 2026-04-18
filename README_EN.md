# Uni-Gear – Parametric Gear Generator

*Read this in another language: [Deutsch](README.md) · **English***

**A lightweight Blender add-on for quickly creating parametric gears**

Build realistic gears with just a few clicks right from the N-panel.
Ideal for mechanical design, 3D printing, animation, technical visualization and game assets.

![Gear Generator Screenshot](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/screenshot.png)

## ✨ Features

- ✅ Fully parametric: gear diameter, tooth count, thickness, pressure angle
- ✅ True involute teeth per DIN-867 reference profile (`h_aP* = 1.0`, `h_fP* = 1.25`)
- ✅ Correct pitch-circle tooth thickness `π·m/2` via `inv(α) = tan(α) − α`
- ✅ Tangentially blended trochoidal fillet at the tooth root
- ✅ Optional helical teeth with adjustable helix angle
- ✅ Optional hub – on one or both faces
- ✅ Optional central bore (passes through hub and cone)
- ✅ Optional decentral relief / mounting holes (count, diameter, hole circle)
- ✅ Stepped gear / stacking: up to 3 gear stages on a shared axis
- ✅ Bevel gears – straight- and spiral-toothed
- ✅ Internal gears (ring gears / Hohlrad)
- ✅ DIN-3960 mode: standard module (DIN 780), profile shift `x`, undercut warning
- ✅ Gear pairing: counter-gear automatically placed at correct center distance
- ✅ Dedicated N-panel GUI (tab "Uni-Gear") with persistent settings
- ✅ One-click creation with full undo support
- ✅ Clean Blender Python code (bmesh)
- ✅ MIT License – free to use and modify

## 📥 Installation

1. Download [`gear_generator.py`](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/gear_generator.py)
2. In Blender: **Edit → Preferences → Add-ons → Install**
3. Select the downloaded `.py` file
4. Enable the add-on "Uni-Gear"
5. Press `N` → tab **Uni-Gear** → "Zahnrad erstellen" ("Create gear")

## 🚀 Usage

1. Open the sidebar in the 3D viewport with `N`
2. Switch to the tab **Uni-Gear**
3. Adjust parameters (enable optional sections via their toggles)
4. Click **"Zahnrad erstellen"** ("Create gear")

The gear is created directly as a new object in the scene.

## Parameters

> All lengths are given as **diameters** (not radii) — the way gears are
> referred to in practice (e.g. "20 mm gear"). Internally the add-on still
> works with radii.

### Gear

| Parameter        | Description                    | Default |
|------------------|--------------------------------|---------|
| Gear diameter    | Pitch-circle diameter          | 20 mm   |
| Tooth count      | Number of teeth                | 24      |
| Thickness        | Axial face width               | 5 mm    |
| Pressure angle   | Pressure angle in degrees      | 20°     |

### Helical teeth (optional)

| Parameter    | Description                    | Default |
|--------------|--------------------------------|---------|
| Helix angle  | Helix angle in degrees (−45…45)| 15°     |

### Central bore (optional)

| Parameter     | Description                        | Default |
|---------------|------------------------------------|---------|
| Bore diameter | Diameter of the central bore       | 6 mm    |

### Decentral holes (optional)

| Parameter           | Description                                 | Default |
|---------------------|---------------------------------------------|---------|
| Count               | Number of evenly distributed holes          | 3       |
| Diameter            | Diameter of each hole                       | 3 mm    |
| Hole circle dia.    | Diameter of the circle the holes lie on     | 10 mm   |

### Hub (optional)

| Parameter     | Description                                               | Default    |
|---------------|-----------------------------------------------------------|------------|
| Hub diameter  | Outer diameter of the cylindrical hub                     | 16 mm      |
| Hub height    | Protrusion or pocket depth of the hub                     | 4 mm       |
| Side          | Both sides / back only / front only                       | Both sides |
| Negative hub  | Hub as a pocket carved into the gear body (not protrusion)| off        |

### Stepped gear / stacking (optional)

| Parameter       | Description                                              | Default |
|-----------------|----------------------------------------------------------|---------|
| Stage count     | Total number of stages on the shared shaft               | 2       |
| Spacing         | Axial gap between two stages                             | 0 mm    |
| Stage 2/3       | Own pitch diameter, tooth count and thickness per stage  | —       |

### Bevel gear (optional)

| Parameter        | Description                                                    | Default |
|------------------|----------------------------------------------------------------|---------|
| Pitch cone angle | Half-angle of the pitch cone δ (45° = 1:1 miter pair)          | 45°     |
| Face width       | Tooth length along the cone slant                              | 8 mm    |
| Spiral teeth     | Straight- vs. spiral-toothed bevel gear                        | off     |
| Spiral angle     | Mean spiral angle (when spiral teeth are enabled)              | 35°     |

> Note: In bevel mode, helical teeth, hub, decentral holes and stacking are
> disabled. A central bore can still be enabled.

### Internal gear – ring gear (optional)

| Parameter             | Description                                                        | Default |
|-----------------------|--------------------------------------------------------------------|---------|
| Ring outer diameter   | Outer diameter of the ring body (must be > gear diameter)         | 30 mm   |

### DIN-3960 mode (optional)

| Parameter       | Description                                                            | Default |
|-----------------|------------------------------------------------------------------------|---------|
| Module (DIN 780)| Standard module m – sets gear diameter: d = m · z                     | 1.0 mm  |
| Profile shift x | Profile shift coefficient per DIN 3960 (0 = standard tooth)           | 0.0     |

> In DIN mode the gear diameter is computed automatically from module and tooth count.
> The panel shows an undercut warning when x < x_min for the selected tooth count.

### Gear pairing (optional)

| Parameter                 | Description                                                | Default |
|---------------------------|------------------------------------------------------------|---------|
| Counter-gear teeth        | Tooth count of the automatically generated counter-gear   | 16      |
| Counter-gear thickness    | Axial thickness of the counter-gear                        | 5 mm    |
| Counter-gear as ring gear | Generate counter-gear as internal gear                     | off     |
| Bore on counter-gear      | Central bore on the counter-gear (configurable diameter)   | off     |
| Hub on counter-gear       | Hub on the counter-gear (diameter, height, side, negative) | off     |

## Roadmap

Done:

- [x] True involute tooth shape
- [x] Helical teeth
- [x] Automatic bores (central + decentral relief holes)
- [x] Hub – one- or two-sided, combinable with the bore
- [x] Gear stacking (several gears on one shaft, e.g. stepped gears)
- [x] Bevel gears (straight- and spiral-toothed)
- [x] Internal gears (ring gears)
- [x] DIN-3960 mode: standard module (DIN 780), profile shift `x`, undercut warning
- [x] Gear pairing (counter-gear at correct center distance, incl. bore/hub on counter-gear)
- [x] Negative hub (hub pocket inside the gear body)

Open:

- [ ] Backlash (Flankenspiel)
- [ ] Rack gear (Zahnstange)
- [ ] Automatic rigging (rotation via driver)
- [ ] Free-text module input (in addition to DIN dropdown)
- [ ] Preview mode (Modal Operator with live preview)
- [ ] True trochoidal root fillet (full DIN 3960)

## Contributing

Got ideas for improvements?
Just open an issue or a pull request — every contribution is welcome! ❤️

## License

[MIT License](LICENSE) – you may use, modify and redistribute the add-on freely.

---

**Made with ❤️ for the Blender community**
