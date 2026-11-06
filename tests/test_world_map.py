import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from backend.compare_surface import Raster, render
from backend.export_posteffect_map import build, read_world_tiles, world_shader
from backend.extract_surface import extract_window
from backend.render_world_map import discover_world, render_world, validate_sources
from test_extract_surface import write_region


class WorldMapTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.world = self.root / "source"
        self.world.mkdir()

    def test_tiled_render_matches_single_image_across_negative_origin_and_seams(self):
        write_region(self.world, -1, 0, top=63, legacy=True)
        write_region(self.world, 0, 0, top=70)
        # Empty MCA files are valid artifacts of region creation.
        (self.world / "region" / "r.9.9.mca").touch()
        output = self.root / "tiles"
        with patch("builtins.print"):
            manifest = render_world(self.world, output, tile_size=10)
        self.assertEqual(manifest["origin"], [-16, 0])
        self.assertEqual(manifest["world_size"], [32, 16])
        self.assertEqual(manifest["grid"], [4, 2])
        self.assertEqual(manifest["valid_columns"], 512)
        surface = extract_window(self.world, -17, -1, 34)
        raster = Raster(surface.size, 1, surface.heights, surface.states, surface.valid, surface.palette)
        _, reference = render(raster, unknown_color="#6a6a6a", include_base=False)
        expected = reference.crop((1, 1, 33, 17))
        stitched = Image.new("RGBA", (32, 16))
        for tile in manifest["tiles"]:
            with Image.open(output / tile["file"]) as texture:
                self.assertEqual(texture.size, tuple(tile["size"]))
                stitched.paste(texture, (tile["cell"][0] * 10, tile["cell"][1] * 10))
        self.assertEqual(stitched.tobytes(), expected.tobytes())
        self.assertEqual(manifest["tiles"][-1]["size"], [2, 6])
        self.assertEqual(read_world_tiles(output)["blocks_per_pixel"], 1)

    def test_missing_chunks_stay_transparent_without_coarse_fallback(self):
        write_region(self.world, -1, -1, top=0)
        write_region(self.world, 0, 0, top=90)
        output = self.root / "holes"
        with patch("builtins.print"):
            manifest = render_world(self.world, output, tile_size=16)
        self.assertEqual(manifest["valid_columns"], 512)
        for tile in manifest["tiles"]:
            with Image.open(output / tile["file"]) as image:
                if tile["cell"] in ([1, 0], [0, 1]):
                    self.assertEqual(image.getchannel("A").getextrema(), (0, 0))
                else:
                    self.assertEqual(image.getchannel("A").getextrema(), (255, 255))

    def test_world_pack_preserves_pixels_bounds_four_zooms_and_sampler_budget(self):
        write_region(self.world, -1, 0, top=63)
        write_region(self.world, 0, 0, top=70)
        tiles = self.root / "tiles"
        with patch("builtins.print"):
            manifest = render_world(self.world, tiles, tile_size=10)
        output = self.root / "packs"
        output.mkdir()
        build(self.root / "no-web-render", output, 1024, world_tiles=tiles)
        with ZipFile(output / "vanilla-map-post-resources.zip") as pack:
            self.assertNotIn("assets/vanilla_map_post/textures/effect/map.png", pack.namelist())
            for i, tile in enumerate(manifest["tiles"]):
                payload = pack.read(f"assets/vanilla_map_post/textures/effect/world/{i}.png")
                self.assertEqual(hashlib.sha256(payload).hexdigest(), tile["sha256"])
            for effect, span in (("map_close", 512), ("map_near", 1024), ("map", 2048), ("map_far", 4096)):
                effect = json.loads(pack.read(f"assets/vanilla_map_post/post_effect/{effect}.json"))
                map_pass = next(p for p in effect["passes"] if "MapConfig" in p.get("uniforms", {}))
                values = {v["name"]: v["value"] for v in map_pass["uniforms"]["MapConfig"]}
                self.assertEqual(values["MapOrigin"], [-16, 0, 0])
                self.assertEqual(values["MapWorldSize"], [32, 16])
                self.assertEqual(values["ViewHeight"], span)
                self.assertEqual((values["TileSize"], values["TilesX"]), (10, 4))
                self.assertEqual(len(map_pass["inputs"]), 9)
                self.assertLessEqual(len(map_pass["inputs"]), 16)
                self.assertEqual(map_pass["fragment_shader"], "vanilla_map_post:post/world_map")
                for i, tile in enumerate(manifest["tiles"]):
                    self.assertEqual((map_pass["inputs"][i+1]["width"], map_pass["inputs"][i+1]["height"]),
                                     tuple(tile["size"]))
        with ZipFile(output / "vanilla-map-post-datapack.zip") as pack:
            limits = pack.read("data/vanilla_map_post/function/limit_pan.mcfunction").decode()
            self.assertIn("scoreboard players add @s vmp_word 256", limits)

    def test_corrupt_tiles_and_invalid_grid_are_rejected(self):
        write_region(self.world)
        output = self.root / "tiles"
        with patch("builtins.print"):
            manifest = render_world(self.world, output, tile_size=16)
        path = output / manifest["tiles"][0]["file"]
        original = path.read_bytes()
        path.write_bytes(original + b"corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            read_world_tiles(output)
        path.write_bytes(original)
        manifest["tiles"][0]["size"] = [8, 8]
        (output / "world-map.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "dimensions"):
            read_world_tiles(output)

    def test_changed_source_and_excessive_grid_fail_without_completed_manifest(self):
        path = write_region(self.world)
        _, _, sources = discover_world(self.world)
        path.write_bytes(path.read_bytes() + b"\0")
        with self.assertRaisesRegex(ValueError, "World changed"):
            validate_sources(self.world, sources)
        output = self.root / "interrupted"
        with patch("backend.render_world_map.validate_sources", side_effect=ValueError("Changed source")), patch("builtins.print"):
            with self.assertRaisesRegex(ValueError, "Changed source"):
                render_world(self.world, output, tile_size=16)
        self.assertFalse((output / "world-map.json").exists())
        write_region(self.world, cx=4096)
        with self.assertRaisesRegex(ValueError, "supported maximum"):
            render_world(self.world, self.root / "too-large", tile_size=1024)

    def test_shader_has_fixed_sampler_leaves_with_balanced_dispatch(self):
        for count in (1, 6, 15):
            source = world_shader(count)
            self.assertNotIn("// TILE_", source)
            self.assertNotIn("for (", source)
            self.assertEqual(source.count("uniform sampler2D"), count + 1)
            for i in range(count):
                self.assertEqual(source.count(f"return texelFetch(Tile{i}Sampler, pixel, 0)"), 1)
        with self.assertRaises(ValueError):
            world_shader(16)


if __name__ == "__main__":
    unittest.main()
