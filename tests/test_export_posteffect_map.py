import gzip
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("map_export", ROOT / "backend/export_posteffect_map.py")
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


class ExportReliefTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.render = Path(self.temporary.name)
        base = Image.new("RGBA", (3, 1), (120, 180, 90, 255))
        base.putpixel((2, 0), (120, 180, 90, 0))
        base.save(self.render / "map_base.png")
        Image.new("RGBA", base.size, "white").save(self.render / "map_shade.png")
        hills = Image.new("RGBA", base.size, (80, 80, 80, 255))
        hills.putpixel((1, 0), (0, 0, 0, 0))
        hills.save(self.render / "map_hillshade.png")
        with gzip.open(self.render / "tile_index.json.gz", "wt", encoding="utf-8") as stream:
            json.dump({"bounds": {"bx4_min": -2, "bz4_min": 3,
                                  "bx4_max": 0, "bz4_max": 3}}, stream)
        # Explicit generation times keep the checks independent of filesystem precision.
        for offset, name in enumerate(("map_base.png", "map_shade.png",
                                       "map_hillshade.png", "tile_index.json.gz")):
            os.utime(self.render / name, (1_700_000_000 + offset,) * 2)

    def test_relief_preserves_alignment_transparency_and_biome_color(self):
        plain, origin, size = EXPORT.read_render(self.render, "biomes")
        relief, relief_origin, relief_size = EXPORT.read_render(self.render)
        self.assertEqual((relief_origin, relief_size), (origin, size))
        self.assertEqual((origin, size), ((-8, 0, 12), (12, 4)))
        self.assertEqual(relief.size, plain.size)
        self.assertEqual(relief.getchannel("A").tobytes(), plain.getchannel("A").tobytes())
        shadow, original = relief.getpixel((0, 0)), plain.getpixel((0, 0))
        self.assertTrue(all(0 < new < old for new, old in zip(shadow[:3], original[:3])))
        self.assertGreater(shadow[1], shadow[0])
        self.assertGreater(shadow[0], shadow[2])
        self.assertEqual(relief.getpixel((1, 0)), plain.getpixel((1, 0)))

    def test_missing_relief_can_be_exported_explicitly_as_biomes(self):
        (self.render / "map_shade.png").unlink()
        with self.assertRaisesRegex(ValueError, "--style biomes"):
            EXPORT.read_render(self.render)
        plain, _, _ = EXPORT.read_render(self.render, "biomes")
        self.assertEqual(plain.getpixel((0, 0)), (120, 180, 90, 255))

    def test_rejects_misaligned_or_stale_layers(self):
        path = self.render / "map_shade.png"
        Image.new("RGBA", (1, 1), "white").save(path)
        os.utime(path, (1_700_000_001,) * 2)
        with self.assertRaisesRegex(ValueError, "dimensions"):
            EXPORT.read_render(self.render)
        Image.new("RGBA", (3, 1), "white").save(path)
        os.utime(path, (1_699_999_999,) * 2)
        with self.assertRaisesRegex(ValueError, "same completed render"):
            EXPORT.read_render(self.render)
        os.utime(path, (1_700_000_004,) * 2)
        with self.assertRaisesRegex(ValueError, "same completed render"):
            EXPORT.read_render(self.render)

    def test_style_changes_only_the_texture_and_keeps_zoom_and_controls(self):
        plain_dir, relief_dir = self.render / "plain", self.render / "relief"
        plain_dir.mkdir()
        relief_dir.mkdir()
        EXPORT.build(self.render, plain_dir, 1024, "biomes")
        EXPORT.build(self.render, relief_dir, 1024)
        for name in ("vanilla-map-post-datapack.zip", "vanilla-map-post-resources.zip"):
            with ZipFile(plain_dir / name) as plain, ZipFile(relief_dir / name) as relief:
                self.assertEqual(plain.namelist(), relief.namelist())
                different = [entry for entry in plain.namelist()
                             if plain.read(entry) != relief.read(entry)]
                self.assertEqual(different, ["assets/vanilla_map_post/textures/effect/map.png"]
                                 if "resources" in name else [])
                if "resources" in name:
                    spans = []
                    for effect in ("map_near", "map", "map_far"):
                        payload = json.loads(relief.read(
                            f"assets/vanilla_map_post/post_effect/{effect}.json"))
                        config = next(p["uniforms"]["MapConfig"] for p in payload["passes"]
                                      if "MapConfig" in p.get("uniforms", {}))
                        spans.append(next(v["value"] for v in config if v["name"] == "ViewHeight"))
                    self.assertEqual(spans, [1024, 2048, 4096])


if __name__ == "__main__":
    unittest.main()
