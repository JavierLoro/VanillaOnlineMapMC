import gzip
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from PIL import Image

from backend import export_posteffect_map as EXPORT
from backend.extract_surface import Surface
from backend.compare_surface import render, sample_surface


ROOT = Path(__file__).resolve().parents[1]


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
        (self.render / "map_hillshade.png").unlink()
        with self.assertRaisesRegex(ValueError, "--style biomes"):
            EXPORT.read_render(self.render)
        plain, _, _ = EXPORT.read_render(self.render, "biomes")
        self.assertEqual(plain.getpixel((0, 0)), (120, 180, 90, 255))

    def test_rejects_misaligned_or_stale_layers(self):
        path = self.render / "map_hillshade.png"
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

    def test_full_hillshade_uses_unblurred_pixels_without_topography(self):
        (self.render / "map_shade.png").unlink()
        texture, _, _ = EXPORT.read_render(self.render)
        self.assertEqual(texture.getpixel((0, 0)), (37, 56, 28, 255))
        self.assertEqual(texture.getpixel((1, 0)), (120, 180, 90, 255))

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

    def test_detail_preserves_one_block_pixels_world_alignment_and_controls(self):
        surface = Surface(-4, 12, 4, -64)
        surface.palette.append(("minecraft:dirt_path", ()))
        for i in range(16):
            surface.states[i] = 1
            surface.heights[i] = 64
            surface.valid[i] = i != 5
        source = self.render / "surface"
        surface.save(source)
        plain_dir, detail_dir = self.render / "overview", self.render / "detail"
        plain_dir.mkdir()
        detail_dir.mkdir()
        EXPORT.build(self.render, plain_dir, 1024)
        EXPORT.build(self.render, detail_dir, 1024, surface_path=source / "surface.zip")
        with ZipFile(plain_dir / "vanilla-map-post-datapack.zip") as old, ZipFile(
                detail_dir / "vanilla-map-post-datapack.zip") as new:
            self.assertEqual({n: old.read(n) for n in old.namelist()},
                             {n: new.read(n) for n in new.namelist()})
        with ZipFile(detail_dir / "vanilla-map-post-resources.zip") as pack:
            from io import BytesIO
            with Image.open(BytesIO(pack.read("assets/vanilla_map_post/textures/effect/detail.png"))) as image:
                expected = render(sample_surface(surface, 1))[1]
                self.assertEqual(image.size, (4, 4))
                self.assertEqual(image.tobytes(), expected.tobytes())
                self.assertEqual(image.getpixel((1, 1))[3], 0)
            for effect, span in (("map_near", 1024), ("map", 2048), ("map_far", 4096)):
                effect = json.loads(pack.read(f"assets/vanilla_map_post/post_effect/{effect}.json"))
                map_pass = next(p for p in effect["passes"] if "MapConfig" in p.get("uniforms", {}))
                config = {v["name"]: v["value"] for v in map_pass["uniforms"]["MapConfig"]}
                self.assertEqual(config["MapOrigin"], [-8, 0, 12])
                self.assertEqual(config["MapWorldSize"], [12, 4])
                self.assertEqual(config["DetailOffset"], [4, 0])
                self.assertEqual(config["DetailWorldSize"], [4, 4])
                self.assertEqual(config["ViewHeight"], span)
                detail = next(i for i in map_pass["inputs"] if i["sampler_name"] == "Detail")
                self.assertEqual((detail["width"], detail["height"]), (4, 4))
                # A marker at this world column reaches the identical detail texel.
                player_x, player_z = -2.5, 14.5
                texel = (int(player_x - config["MapOrigin"][0] - config["DetailOffset"][0]),
                         int(player_z - config["MapOrigin"][2] - config["DetailOffset"][1]))
                self.assertEqual(texel, (1, 2))

    def test_detail_rejects_outside_bounds_and_disabled_detail_is_transparent(self):
        surface = Surface(-20, 12, 4, -64)
        source = self.render / "outside"
        surface.save(source)
        with self.assertRaisesRegex(ValueError, "inside the full map"):
            EXPORT.read_detail(source / "surface.zip", (-8, 0, 12), (12, 4))
        image, offset, size = EXPORT.read_detail(None, (-8, 0, 12), (12, 4))
        self.assertEqual((offset, size), ((0, 0), (0, 0)))
        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_unhandled_material_uses_overview_instead_of_diagnostic_magenta(self):
        surface = Surface(-4, 12, 4, -64)
        surface.palette.append(("custom:unhandled_block", ()))
        surface.valid[0] = 1
        surface.states[0] = 1
        source = self.render / "unhandled"
        surface.save(source)
        texture, _, _ = EXPORT.read_detail(source / "surface.zip", (-8, 0, 12), (12, 4))
        self.assertEqual(texture.getpixel((0, 0)), (0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
