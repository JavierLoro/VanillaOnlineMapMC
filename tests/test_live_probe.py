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
        self.loaded = True
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
            return 0
        if name == "live/cache/check_loaded":
            return int(self.loaded)
        text = self.files[f"data/vanilla_map_post/function/{name}.mcfunction"]
        try:
            for line in text.splitlines():
                if line.startswith("$"):
                    line = re.sub(r"\$\((\w+)\)", lambda m: str(arguments[m[1]]), line[1:])
                self.line(line)
        except ReturnValue as result:
            return result.value
        return 0

    def line(self, line):
        if not line or line.startswith("#"):
            return 0
        match = re.match(r"execute (if|unless) score (\S+) (\S+) matches (\S+) (.*)", line)
        if match:
            kind, holder, objective, interval, command = match.groups()
            value = self.scores.get(self.key(holder, objective))
            bounds = interval.split("..")
            passed = value is not None and (value == int(bounds[0]) if len(bounds) == 1 else (
                (not bounds[0] or value >= int(bounds[0])) and (not bounds[1] or value <= int(bounds[1]))))
            if kind == "unless":
                passed = not passed
            command = command[4:] if command.startswith("run ") else "execute " + command
            return self.line(command) if passed else 0
        match = re.match(r"execute (if|unless) data storage \S+ (\S+) run (.*)", line)
        if match:
            kind, path, command = match.groups()
            if "{" in path:
                path, version = path.split("{", 1)
                passed = self.storage.get(path + ".version") == int(version.split(":")[1][:-1])
            else:
                passed = path in self.storage or any(k.startswith(path + ".") for k in self.storage)
            return self.line(command) if passed == (kind == "if") else 0
        if line.startswith("execute store result "):
            target, command = line[21:].split(" run ", 1)
            value = self.line(command)
            parts = target.split()
            if parts[0] == "score":
                self.scores[self.key(parts[1], parts[2])] = value
            else:
                self.storage[parts[2]] = value
            return value
        if line.startswith("return "):
            value = self.line(line[11:]) if line.startswith("return run ") else int(line[7:])
            raise ReturnValue(value)
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
            target = p[4]
            if p[6] == "value":
                value = json.loads(re.sub(r"(\w+):", r'"\1":', " ".join(p[7:])))
                def flatten(value, key):
                    result = {}
                    for k, v in value.items():
                        result.update(flatten(v, key + "." + k) if isinstance(v, dict) else {key + "." + k: v})
                    return result
                updates = flatten(value, target)
            else:
                source = p[9]
                updates = {target + k[len(source):]: v for k, v in self.storage.items()
                           if k == source or k.startswith(source + ".")}
            self.storage = {k: v for k, v in self.storage.items() if k != target and not k.startswith(target + ".")}
            self.storage.update(updates)
            return 1
        if p[0] == "function":
            arguments = None
            if "with" in p:
                prefix = p[-1] + "."
                arguments = {k[len(prefix):]: v for k, v in self.storage.items() if k.startswith(prefix)}
            return self.run(p[1].split(":", 1)[1], arguments)
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


class ReturnValue(Exception):
    def __init__(self, value):
        self.value = value


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
                                     "vmp_lmode": 1, "vmp_zoom": 2, "vmp_lid": 1 if player == "a" else 2}.items():
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

    def test_complete_chunk_cache_survives_sender_restart_and_replays_without_loaded_world(self):
        with ZipFile(self.output / "vanilla-map-post-datapack.zip") as archive:
            sender = Sender(archive)
            restored = Sender(archive)
        for objective, value in {"vmp_lid": 1, "vmp_lcx": -2, "vmp_lcz": -1,
                                 "vmp_lgen": 5, "vmp_lmode": 1, "vmp_lindex": 0,
                                 "vmp_lbank": 0, "vmp_lsent": 0, "vmp_zoom": 2}.items():
            sender.scores["a", objective] = value
        sender.run("live/cache/context")
        sender.run("live/cache/create", {"id": 1, "cx": -2, "cz": -1, "mode": 1, "revision": 5})
        sender.run("live/start")
        for _ in range(63):
            sender.run("live/next")
        sender.run("live/stop")
        restored.storage = json.loads(json.dumps(sender.storage))
        restored.scores = sender.scores.copy()
        restored.loaded = False
        restored.scores["a", "vmp_lcx"] = 100
        restored.run("live/resume")
        self.assertEqual(restored.scores["a", "vmp_lcx"], -2)
        for group in range(64):
            if group:
                restored.run("live/next")
            colors = []
            for pixel in range(4):
                x, z = -32 + (group * 4 + pixel) % 16, -16 + group // 4
                colors.append((x % 256, z % 256, (x + z) % 256))
            self.assertEqual([restored.scores["a", f"vmp_lold{i}"] for i in range(20)],
                             live_probe.encode_packet(-2, -1, group, colors, 5))
        restored.run("live/disable")
        self.assertEqual(restored.scores["a", "vmp_lresume"], 0)
        self.assertFalse(any(":live/" in e for e in restored.effects["a"]))

    def test_unloaded_missing_group_cannot_replay_another_players_data(self):
        with ZipFile(self.output / "vanilla-map-post-datapack.zip") as archive:
            sender = Sender(archive)
        sender.loaded = False
        for objective, value in {"vmp_lid": 2, "vmp_lcx": 0, "vmp_lcz": 0,
                                 "vmp_lgen": 1, "vmp_lmode": 1, "vmp_lindex": 0,
                                 "vmp_lbank": 0, "vmp_lsent": 0, "vmp_zoom": 2}.items():
            sender.scores["a", objective] = value
        for i, value in enumerate(live_probe.encode_packet(0, 0, 0, [(255, 0, 0)] * 4, 1)):
            sender.storage[f"players.p1.packets.g0.b{i}"] = value
        sender.run("live/next")
        self.assertEqual(sender.effects["a"], [])
        self.assertEqual(sender.scores["a", "vmp_lsent"], 0)


if __name__ == "__main__":
    unittest.main()
