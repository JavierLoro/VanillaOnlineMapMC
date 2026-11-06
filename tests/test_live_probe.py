import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from backend.export_posteffect_map import build, PACK_ROOT, world_shader
from backend import live_probe


class Sender:
    """Execute generated sender arithmetic and macros, including shared scratch storage."""
    def __init__(self, archive):
        self.files = {name: archive.read(name).decode() for name in archive.namelist() if name.endswith(".mcfunction")}
        self.scores = {}
        self.storage = {}
        self.effects = {"a": [], "b": []}
        self.player = "a"
        for key, value in {"#byte": 256, "#sum": 255, "#chunk": 16, "#two": 2,
                           "#one": 1, "#four": 4}.items():
            self.scores[key, "vmp_lword"] = value

    def key(self, holder, objective):
        return (self.player if holder == "@s" else holder, objective)

    def run(self, name, arguments=None):
        if name == "live/read_column":
            x, z = self.storage["context.x"], self.storage["context.z"]
            for c, value in zip("rgb", (x % 256, z % 256, (x + z) % 256)):
                self.scores[self.player, "vmp_l" + c] = value
            return
        text = self.files[f"data/vanilla_map_post/function/{name}.mcfunction"]
        for line in text.splitlines():
            if line.startswith("$"):
                line = re.sub(r"\$\((\w+)\)", lambda m: str(arguments[m[1]]), line[1:])
            self.line(line)

    def line(self, line):
        if not line or line.startswith("#"):
            return 0
        if line.startswith("execute if score "):
            condition, command = line[17:].split(" run ", 1)
            parts = condition.split()
            value = self.scores.get(self.key(parts[0], parts[1]))
            if value is None:
                return 0
            if parts[2] == "matches":
                bounds = parts[3].split("..")
                passed = value == int(bounds[0]) if len(bounds) == 1 else (
                    (not bounds[0] or value >= int(bounds[0])) and (not bounds[1] or value <= int(bounds[1])))
            else:
                raise AssertionError(condition)
            return self.line(command) if passed else 0
        if line.startswith("execute store result "):
            target, command = line[21:].split(" run ", 1)
            value = self.line(command)
            parts = target.split()
            if parts[0] == "score":
                self.scores[self.key(parts[1], parts[2])] = value
            else:
                self.storage[parts[2]] = value
            return value
        p = line.split()
        if p[:2] == ["scoreboard", "players"]:
            key = self.key(p[3], p[4])
            old = self.scores.get(key, 0)
            if p[2] == "get":
                return self.scores[key]
            if p[2] == "operation":
                value = self.scores[self.key(p[6], p[7])]
                self.scores[key] = {"=": lambda: value, "+=": lambda: old + value,
                                    "-=": lambda: old - value, "*=": lambda: old * value,
                                    "/=": lambda: old // value, "%=": lambda: old % value}[p[5]]()
            else:
                value = int(p[5])
                self.scores[key] = {"set": value, "add": old + value, "remove": old - value}[p[2]]
            return self.scores[key]
        if p[:3] == ["data", "get", "storage"]:
            return self.storage[p[4]]
        if p[:3] == ["data", "modify", "storage"]:
            prefix = p[4] + "."
            self.storage = {k: v for k, v in self.storage.items() if not k.startswith(prefix)}
            return 0
        if p[0] == "function":
            arguments = None
            if "with" in p:
                prefix = p[-1] + "."
                arguments = {k[len(prefix):]: v for k, v in self.storage.items() if k.startswith(prefix)}
            self.run(p[1].split(":", 1)[1], arguments)
            return 0
        if p[0] == "posteffect":
            effects = self.effects[self.player]
            if p[1] == "remove" and p[3] in effects:
                effects.remove(p[3])
            if p[1] == "add" and p[3] not in effects:
                effects.append(p[3])
            return 0
        if p[0] == "tag":
            return 0
        raise AssertionError(line)


class LiveProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = TemporaryDirectory()
        cls.output = Path(cls.temporary.name)
        with patch("backend.export_posteffect_map.read_render", return_value=(
                Image.new("RGBA", (1, 1), "green"), (0, 0, 0), (16, 16))):
            build(cls.output, cls.output, 1024, live_chunk_probe=True)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_actual_sender_matches_reference_for_all_pixels_negative_chunks_and_two_players(self):
        with ZipFile(self.output / "vanilla-map-post-datapack.zip") as archive:
            sender = Sender(archive)
        for player, cx, cz in (("a", -2, -1), ("b", 32767, -32768)):
            for objective, value in {"vmp_lcx": cx, "vmp_lcz": cz, "vmp_lgen": 255,
                                     "vmp_lindex": 0, "vmp_lbank": 0, "vmp_lsent": 0,
                                     "vmp_lmode": 1, "vmp_zoom": 2}.items():
                sender.scores[player, objective] = value
            sender.effects[player] = ["vanilla_map_post:live/bank0", "vanilla_map_post:live/bank1"]
        for group in range(65):
            for player in ("a", "b"):
                sender.player = player
                cx, cz = (sender.scores[player, o] for o in ("vmp_lcx", "vmp_lcz"))
                sender.run("live/next")
                index = group % 64
                colors = []
                for i in range(4):
                    x, z = cx * 16 + (index * 4 + i) % 16, cz * 16 + index // 4
                    colors.append((x % 256, z % 256, (x + z) % 256))
                expected = live_probe.encode_packet(cx, cz, index, colors, 255)
                self.assertEqual([sender.scores[player, f"vmp_lold{i}"] for i in range(20)], expected)
                effects = sender.effects[player]
                self.assertEqual(len(effects), 23)
                self.assertEqual(effects[0], f"vanilla_map_post:live/bank{1 - group % 2}")
                self.assertEqual(effects[-2], f"vanilla_map_post:live/bank{group % 2}")
                self.assertEqual(effects[-1], "vanilla_map_post:map_near")
                self.assertEqual(len([v for v in effects if ":live/byte/" in v]), 20)
        sender.run("live/stop")
        self.assertEqual(sender.effects["b"], ["vanilla_map_post:map_near"])
        self.assertEqual(len(sender.effects["a"]), 23)

    def test_generated_palette_decision_tree_maps_every_known_block_to_shared_material_color(self):
        with ZipFile(self.output / "vanilla-map-post-datapack.zip") as archive:
            prefix = "data/vanilla_map_post/"
            def blocks(tag):
                return {v["id"] for v in json.loads(archive.read(prefix + "tags/block/" + tag + ".json"))["values"]}
            for block in blocks("live/known"):
                node = "root"
                depth = 0
                while True:
                    text = archive.read(prefix + "function/live/palette/" + node + ".mcfunction").decode()
                    if text.startswith("scoreboard"):
                        rgb = tuple(int(line.split()[-1]) for line in text.splitlines())
                        self.assertEqual(rgb, tuple(bytes.fromhex(live_probe.material_color(block)[1:])))
                        break
                    node += "0" if block in blocks("live/" + node + "0") else "1"
                    depth += 1
                    self.assertLessEqual(depth, 9)

    def test_opt_in_pack_has_bounded_histories_signals_cleanup_and_extra_sampler(self):
        with ZipFile(self.output / "vanilla-map-post-resources.zip") as archive:
            self.assertEqual(len([n for n in archive.namelist() if "/live/byte/" in n]), 5120)
            for slot, value in ((0, 0), (19, 255), (7, 128)):
                effect = json.loads(archive.read(f"assets/vanilla_map_post/post_effect/live/byte/{slot}_{value}.json"))
                self.assertEqual(effect["passes"][0]["uniforms"]["PanSignal"][0]["value"], [10 + slot, value])
            for bank in range(2):
                effect = json.loads(archive.read(f"assets/vanilla_map_post/post_effect/live/bank{bank}.json"))
                self.assertEqual(effect["targets"]["history"], {"width": 16, "height": 17, "persistent": True})
            for name in ("map", "map_far", "map_near", "map_close"):
                effect = json.loads(archive.read(f"assets/vanilla_map_post/post_effect/{name}.json"))
                self.assertEqual(effect["passes"][1]["inputs"][1], {"sampler_name": "Live", "target": "minecraft:main"})
            self.assertIn("liveOverlay", archive.read("assets/vanilla_map_post/shaders/post/map.fsh").decode())
        with ZipFile(self.output / "vanilla-map-post-datapack.zip") as archive:
            close = archive.read("data/vanilla_map_post/function/close.mcfunction").decode()
            self.assertIn("live/stop", close)
        self.assertEqual(live_probe.shader(world_shader(14), PACK_ROOT).count("uniform sampler2D"), 16)
        with patch("backend.export_posteffect_map.read_world_tiles", return_value={"tiles": [None] * 15}):
            with self.assertRaisesRegex(ValueError, "fourteen"):
                build(self.output, self.output, 1024, world_tiles=self.output, live_chunk_probe=True)

    def test_encoder_rejects_out_of_range_payloads(self):
        for args in ((32768, 0, 0, [(0, 0, 0)] * 4, 0),
                     (0, 0, 64, [(0, 0, 0)] * 4, 0),
                     (0, 0, 0, [(256, 0, 0)] * 4, 0)):
            with self.assertRaises(ValueError):
                live_probe.encode_packet(*args)


if __name__ == "__main__":
    unittest.main()
