# Uni-Gear – Parametric Gear Generator

*Read this in another language: [Deutsch](README.md) · **English***

**A lightweight Blender add-on for quickly creating parametric gears**

Build realistic gears with just a few clicks right from the N-panel.
Ideal for mechanical design, 3D printing, animation, technical visualization and game assets.

![Gear Generator Screenshot](https://github.com/Chance-Konstruktion/Uni-Gear/blob/main/screenshot.png)
*(Screenshot will be added later – just take a picture of the sidebar and upload it.)*

## ✨ Features

- ✅ Fully parametric: pitch diameter, tooth count, thickness, pressure angle
- ✅ True involute teeth per DIN-867 reference profile (`h_aP* = 1.0`, `h_fP* = 1.25`)
- ✅ Correct pitch-circle tooth thickness `π·m/2` via `inv(α) = tan(α) − α`
- ✅ Tangentially blended circular-arc fillet at the tooth root
- ✅ Optional helical teeth with adjustable helix angle
- ✅ Optional hub – on one or both faces
- ✅ Optional central bore (passes through hub and cone)
- ✅ Optional decentral relief / mounting holes (count, diameter, hole circle)
- ✅ Stepped gear / stacking: up to 3 gear stages on a shared axis
- ✅ Bevel gears – straight- and spiral-toothed
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
| Pitch diameter   | Pitch-circle diameter          | 20 mm   |
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

| Parameter     | Description                                       | Default    |
|---------------|---------------------------------------------------|------------|
| Hub diameter  | Outer diameter of the cylindrical hub             | 16 mm      |
| Hub height    | How far the hub protrudes past the face           | 4 mm       |
| Side          | Both sides / back only / front only               | Both sides |

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

## Roadmap

Done:

- [x] True involute tooth shape
- [x] Helical teeth
- [x] Automatic bores (central + decentral relief holes)
- [x] Hub – one- or two-sided, combinable with the bore
- [x] Gear stacking (several gears on one shaft, e.g. stepped gears)
- [x] Bevel gears (straight- and spiral-toothed)

Open:

- [ ] Internal gears (ring gears)
- [ ] Gear pairing (two gears matched to each other, incl. center distance)
- [ ] DIN-3960 mode: module dropdown (DIN 780), profile shift `x`, true trochoidal root, undercut warning

## Contributing

Got ideas for improvements?
Just open an issue or a pull request — every contribution is welcome! ❤️

## License

[MIT License](LICENSE) – you may use, modify and redistribute the add-on freely.

---

**Made with ❤️ for the Blender community**
