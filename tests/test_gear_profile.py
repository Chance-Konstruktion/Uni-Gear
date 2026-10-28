"""Host-free regression tests for Uni-Gear's involute geometry."""

import importlib.util
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


_install_blender_stubs()
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("uni_gear_test_module", ROOT / "gear_generator.py")
gear = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gear)


class TestGearProfileNormReferences(unittest.TestCase):
    def test_standard_straight_gear_radii_follow_din_867_basic_profile(self):
        # DIN 867 basic rack: haP*=1.0 and hfP*=1.25, module m=2*r/z.
        profile, root_radius, tip_radius = gear.build_gear_profile(
            pitch_radius=10.0,
            teeth=20,
            pressure_angle_deg=20.0,
        )
        self.assertGreaterEqual(len(profile), 20)
        self.assertAlmostEqual(tip_radius, 11.0, places=8)
        self.assertAlmostEqual(root_radius, 8.75, places=8)

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

    def test_din_780_module_dropdown_includes_09(self):
        module_property = gear.GearGeneratorProperties.__annotations__["din_module"]
        values = {entry[0] for entry in module_property["items"]}
        self.assertIn("0.9", values)
        self.assertIn("1.25", values)

    def test_addon_version_is_updated(self):
        self.assertEqual(gear.bl_info["version"], (1, 0, 3))


if __name__ == "__main__":
    unittest.main()
