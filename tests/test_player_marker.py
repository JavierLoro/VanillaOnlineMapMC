import json
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from backend.export_posteffect_map import build, PACK_ROOT, world_shader


FUNCTIONS = PACK_ROOT / "datapack/data/vanilla_map_post/function"


def capture_heading(yaw):
    """Execute the score arithmetic from the actual capture function."""
    scores = {("@s", "vmp_yaw"): yaw}
    for line in (FUNCTIONS / "load.mcfunction").read_text().splitlines():
        match = re.fullmatch(r"scoreboard players set (#[\w_]+) (\w+) (-?\d+)", line)
        if match:
            holder, objective, value = match.groups()
            scores[holder, objective] = int(value)
    for line in (FUNCTIONS / "capture_heading.mcfunction").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("execute if score"):
            if scores["@s", "vmp_heading"] >= 0:
                continue
            line = line.split(" run ", 1)[1]
        parts = line.split()
        if parts[:3] == ["scoreboard", "players", "add"]:
            key = parts[3], parts[4]
            scores[key] = scores.get(key, 0) + int(parts[5])
        elif parts[:3] == ["scoreboard", "players", "operation"]:
            key, op, source = (parts[3], parts[4]), parts[5], (parts[6], parts[7])
            right = scores[source]
            left = scores.get(key, 0)
            scores[key] = {"=": lambda: right, "*=": lambda: left * right,
                           "/=": lambda: math.trunc(left / right),
                           "%=": lambda: left - math.trunc(left / right) * right}[op]()
        else:
            raise AssertionError(f"Unsupported capture instruction: {line}")
    return scores["@s", "vmp_heading"]


class PlayerMarkerTests(unittest.TestCase):
    def test_opening_yaw_wraps_and_rounds_to_correct_cardinal_and_diagonal_directions(self):
        cases = {0: 0, 9000: 16, 18000: 32, -9000: 48,
                 4500: 8, 13500: 24, 22500: 40, -4500: 56,
                 36000: 0, -36000: 0, 45000: 16, -81000: 48,
                 35999: 0, 281: 0, 282: 1, -281: 0, -282: 63}
        for yaw, expected in cases.items():
            with self.subTest(yaw=yaw):
                self.assertEqual(capture_heading(yaw), expected)
        for yaw in range(-72000, 72001, 37):
            heading = capture_heading(yaw)
            error = abs((heading * 36000 / 64 - yaw + 18000) % 36000 - 18000)
            self.assertLessEqual(error, 36000 / 128)

    def test_heading_is_captured_only_on_open_and_cleanup_uses_each_players_value(self):
        toggle = (FUNCTIONS / "toggle.mcfunction").read_text()
        self.assertLess(toggle.index("Rotation[0] 100"), toggle.index("function vanilla_map_post:capture_heading"))
        self.assertLess(toggle.index("function vanilla_map_post:capture_heading"), toggle.index("function vanilla_map_post:set_pan_effects"))
        for path in FUNCTIONS.glob("*.mcfunction"):
            if path.name != "toggle.mcfunction":
                self.assertNotIn("function vanilla_map_post:capture_heading", path.read_text())
        storage = (FUNCTIONS / "set_pan_effects.mcfunction").read_text()
        self.assertIn("heading int 1 run scoreboard players get @s vmp_heading", storage)
        effects = (FUNCTIONS / "pan_effects.mcfunction").read_text()
        self.assertIn("$posteffect $(operation) @s vanilla_map_post:heading/$(heading)", effects)
        self.assertIn('set_pan_effects {operation:"remove"}', (FUNCTIONS / "close.mcfunction").read_text())

    def test_export_contains_all_heading_signals_without_growing_history_or_sampler_count(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            from PIL import Image
            from unittest.mock import patch
            with patch("backend.export_posteffect_map.read_render", return_value=(
                    Image.new("RGBA", (1, 1), "green"), (0, 0, 0), (4, 4))):
                build(output, output, 1024)
            with ZipFile(output / "vanilla-map-post-resources.zip") as pack:
                for heading in range(64):
                    signal = json.loads(pack.read(f"assets/vanilla_map_post/post_effect/heading/{heading}.json"))
                    value = signal["passes"][0]["uniforms"]["PanSignal"][0]["value"]
                    self.assertEqual(value, [8, heading])
                effect = json.loads(pack.read("assets/vanilla_map_post/post_effect/map_near.json"))
                self.assertEqual(effect["targets"]["history"], {"width": 2, "height": 1, "persistent": True})
                self.assertEqual(effect["targets"]["next_state"], {"width": 2, "height": 1})
                for path in ("assets/vanilla_map_post/shaders/post/map.fsh",):
                    shader = pack.read(path).decode()
                    self.assertNotIn("// PLAYER_MARKER", shader)
                    self.assertIn("color = playerMarker", shader)
            shader = world_shader(15)
            self.assertEqual(shader.count("uniform sampler2D"), 16)
            self.assertNotIn("// PLAYER_MARKER", shader)


if __name__ == "__main__":
    unittest.main()
