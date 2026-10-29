"""Host-free regression tests for Uni-Gear's involute geometry."""

import importlib.util
import math
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _install_blender_stubs():
    if "bpy" in sys.modules:
        return

    class _PropertyFactory:
        def __getattr__(self, name):
            def make_property(**kwargs):
                return {"property_type": name, **kwargs}
            return make_property

    bpy = types.ModuleType("bpy")
    bpy.props = _PropertyFactory()
    bpy.types = types.SimpleNamespace(
        PropertyGroup=type("PropertyGroup", (), {}),
        Operator=type("Operator", (), {}),
        Panel=type("Panel", (), {}),
        Scene=type("Scene", (), {}),
    )
    sys.modules["bpy"] = bpy
    sys.modules["bmesh"] = types.ModuleType("bmesh")
    sys.modules["mathutils"] = types.ModuleType("mathutils")


# Load the production math source directly by path. This bypasses package
# initialization so the calculation tests do not import bpy.
math_spec = importlib.util.spec_from_file_location(
    "uni_gear_pure_math", ROOT / "uni_gear" / "gear_math.py"
)
gear_math = importlib.util.module_from_spec(math_spec)
math_spec.loader.exec_module(gear_math)

_install_blender_stubs()
sys.path.insert(0, str(ROOT))
import uni_gear as gear  # noqa: E402


class TestGearProfileNormReferences(unittest.TestCase):
    def test_standard_straight_gear_radii_follow_din_867_basic_profile(self):
        # DIN 867 basic rack: haP*=1.0 and hfP*=1.25, module m=2*r/z.
        profile, root_radius, tip_radius = gear_math.build_gear_profile(
            pitch_radius=10.0,
            teeth=20,
            pressure_angle_deg=20.0,
        )
        self.assertGreaterEqual(len(profile), 20)
        self.assertAlmostEqual(tip_radius, 11.0, places=8)
        self.assertAlmostEqual(root_radius, 8.75, places=8)

    def test_module_pitch_circle_and_20_degree_involute_reference(self):
        pitch_radius = 10.0
        teeth = 20
        module = 2.0 * pitch_radius / teeth
        _profile, root_radius, tip_radius = gear_math.build_gear_profile(
            pitch_radius=pitch_radius,
            teeth=teeth,
            pressure_angle_deg=20.0,
        )
        # DIN 867 basic rack, zero profile shift: haP*=1.0, hfP*=1.25.
        self.assertAlmostEqual(module, 1.0, places=8)
        self.assertAlmostEqual(tip_radius - pitch_radius, module, places=8)
        self.assertAlmostEqual(pitch_radius - root_radius, 1.25 * module, places=8)

        alpha = math.radians(20.0)
        base_radius = pitch_radius * math.cos(alpha)
        self.assertAlmostEqual(base_radius, 9.396926207859085, places=8)
        self.assertAlmostEqual(gear_math.inv(alpha), math.tan(alpha) - alpha, places=12)
        self.assertAlmostEqual(
            gear_math.involute_t_at_radius(base_radius, pitch_radius),
            math.tan(alpha),
            places=8,
        )
    def test_invalid_profile_values_are_rejected(self):
        invalid_cases = (
            {"pitch_radius": 0.0, "teeth": 20, "pressure_angle_deg": 20.0},
            {"pitch_radius": -1.0, "teeth": 20, "pressure_angle_deg": 20.0},
            {"pitch_radius": 10.0, "teeth": 0, "pressure_angle_deg": 20.0},
            {"pitch_radius": 10.0, "teeth": 20, "pressure_angle_deg": 90.0},
            {"pitch_radius": float("nan"), "teeth": 20, "pressure_angle_deg": 20.0},
            {"pitch_radius": 10.0, "teeth": 20, "pressure_angle_deg": float("inf")},
        )
        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    gear.build_gear_profile(**kwargs)

    def test_mesh_entry_rejects_non_positive_thickness_before_blender_ops(self):
        with self.assertRaisesRegex(ValueError, "Dicke muss > 0"):
            gear.create_gear_mesh(
                pitch_radius=10.0,
                teeth=20,
                thickness=0.0,
                pressure_angle_deg=20.0,
            )

    def test_internal_gear_radii_follow_din_867_basic_profile(self):
        _profile, root_radius, tip_radius = gear_math.build_internal_gear_profile(
            pitch_radius=10.0,
            teeth=20,
            pressure_angle_deg=20.0,
        )
        self.assertAlmostEqual(root_radius, 11.25, places=8)
        self.assertAlmostEqual(tip_radius, 9.0, places=8)

    def test_internal_gear_uses_inverted_cutter_coefficients(self):
        cutter = gear._internal_gear_cutter_profile_parameters(profile_shift=0.2)
        self.assertEqual(cutter["addendum_coeff"], 1.25)
        self.assertEqual(cutter["dedendum_coeff"], 1.0)
        self.assertEqual(cutter["profile_shift"], -0.2)

    def test_din_780_module_dropdown_includes_09(self):
        module_property = gear.GearGeneratorProperties.__annotations__["din_module"]
        values = {entry[0] for entry in module_property["items"]}
        self.assertIn("0.9", values)
        self.assertIn("1.25", values)

    def test_addon_version_is_updated(self):
        self.assertEqual(gear.bl_info["version"], (1, 0, 4))
        self.assertEqual(gear.bl_info["blender"], (3, 0, 0))


if __name__ == "__main__":
    unittest.main()
