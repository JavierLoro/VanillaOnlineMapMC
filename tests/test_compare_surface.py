import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from backend.compare_surface import (compare, detail_box, hillshade, load_surface,
                                     path_metrics, render, sample_surface)
from backend.extract_surface import Surface


def flat_surface(size=16):
    surface = Surface(-16, 0, size, -64)
    surface.palette = [("minecraft:air", ()), ("minecraft:grass_block", ()),
                       ("minecraft:dirt_path", ())]
    for i in range(size * size):
        surface.valid[i] = 1
        surface.states[i] = 1
        surface.heights[i] = 64
    return surface


class CompareSurfaceTests(unittest.TestCase):
    def test_height_average_and_material_sample_preserve_world_grid(self):
        surface = flat_surface()
        for z in range(16):
            for x in range(16):
                surface.heights[z * 16 + x] = x + 2 * z
        surface.states[1 * 16 + 1] = 2
        coarse = sample_surface(surface, 4)
        self.assertEqual((coarse.size, coarse.spacing), (4, 4))
        self.assertEqual(coarse.heights[0], 4.5)
        self.assertEqual(coarse.heights[1], 8.5)
        self.assertEqual(coarse.states[0], 2)
        self.assertEqual(coarse.states[1], 1)
        surface.origin_x = -15
        with self.assertRaisesRegex(ValueError, "align"):
            sample_surface(surface, 4)

    def test_same_physical_plane_gets_same_light_at_both_resolutions(self):
        surface = flat_surface()
        for z in range(16):
            for x in range(16):
                surface.heights[z * 16 + x] = 64 - x
        fine, coarse = sample_surface(surface, 1), sample_surface(surface, 4)
        self.assertAlmostEqual(hillshade(fine, 5, 5), hillshade(coarse, 1, 1), places=7)
        fine_flat, coarse_flat = sample_surface(flat_surface(), 1), sample_surface(flat_surface(), 4)
        _, fine_image = render(fine_flat)
        _, coarse_image = render(coarse_flat)
        self.assertEqual(fine_image.getpixel((5, 5)), coarse_image.getpixel((1, 1)))

    def test_missing_columns_do_not_create_false_cliffs_or_opaque_cells(self):
        surface = flat_surface()
        surface.heights[5 * 16 + 5] = -64
        surface.valid[5 * 16 + 5] = 0
        fine, coarse = sample_surface(surface, 1), sample_surface(surface, 4)
        self.assertEqual(coarse.valid[1 * 4 + 1], 0)
        _, image = render(coarse)
        self.assertEqual(image.getpixel((1, 1))[3], 0)
        self.assertAlmostEqual(hillshade(fine, 4, 5), hillshade(fine, 2, 2))

    def test_narrow_path_metrics_distinguish_missing_from_thickened_paths(self):
        for column, recall, precision in ((1, 1.0, 0.25), (3, 0.0, None)):
            with self.subTest(column=column):
                surface = flat_surface()
                for z in range(16):
                    surface.states[z * 16 + column] = 2
                metrics = path_metrics(surface, sample_surface(surface, 4))
                self.assertEqual(metrics["actual_path_blocks"], 16)
                self.assertEqual(metrics["recall"], recall)
                self.assertEqual(metrics["precision"], precision)

    def test_archive_roundtrip_and_comparison_outputs_are_reproducible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            surface = flat_surface()
            surface.heights[0] = -2
            surface.valid[1] = 0
            surface.save(root)
            source = root / "surface.zip"
            original = source.read_bytes()
            loaded = load_surface(source)
            self.assertEqual(loaded.heights, surface.heights)
            self.assertEqual(loaded.states, surface.states)
            self.assertEqual(loaded.valid, surface.valid)
            self.assertEqual(loaded.palette, surface.palette)
            first = compare(source, root / "first")
            second = compare(source, root / "second")
            self.assertEqual(first["source_sha256"], second["source_sha256"])
            self.assertEqual(first["path_overlap"], second["path_overlap"])
            for name in ("hillshade-1x1.png", "hillshade-4x4.png", "comparison.png", "detail.png"):
                self.assertEqual((root / "first" / name).read_bytes(), (root / "second" / name).read_bytes())
            with Image.open(root / "first" / "hillshade-4x4.png") as image:
                self.assertEqual(image.size, (4, 4))
            with Image.open(root / "first" / "hillshade-1x1.png") as image:
                self.assertEqual(image.size, (16, 16))
            self.assertEqual(source.read_bytes(), original)

    def test_bad_archive_version_and_truncated_array_are_rejected(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            flat_surface().save(root)
            with ZipFile(root / "surface.zip") as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            for defect in ("version", "height"):
                changed = dict(entries)
                if defect == "version":
                    metadata = json.loads(changed["metadata.json"])
                    metadata["version"] = 2
                    changed["metadata.json"] = json.dumps(metadata).encode()
                else:
                    changed["height.i16le"] = b"\0\0"
                path = root / f"{defect}.zip"
                with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                    for name, payload in changed.items():
                        archive.writestr(name, payload)
                with self.assertRaises(ValueError):
                    load_surface(path)

    def test_detail_selection_uses_path_coverage_and_stays_inside_crop(self):
        surface = flat_surface(size=256)
        for z in range(160, 220):
            surface.states[z * 256 + 200] = 2
        box = detail_box(surface)
        self.assertEqual((box[2] - box[0], box[3] - box[1]), (128, 128))
        self.assertTrue(box[0] <= 200 < box[2])
        self.assertTrue(box[1] <= 160 and box[3] > 219)
        self.assertTrue(all(0 <= edge <= 256 for edge in box))


if __name__ == "__main__":
    unittest.main()
