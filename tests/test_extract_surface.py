import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile
import zlib

from PIL import Image

from backend.extract_surface import extract_surface, region_chunks
from test_world_reader import packed


def string(value):
    raw = value.encode("utf-8")
    return struct.pack(">H", len(raw)) + raw


def compound(fields):
    return b"".join(bytes([tag]) + string(name) + payload for name, tag, payload in fields) + b"\0"


def long_array(values):
    return struct.pack(">i", len(values)) + b"".join(struct.pack(">q", value) for value in values)


def nbt_list(tag, items):
    return bytes([tag]) + struct.pack(">i", len(items)) + b"".join(items)


def chunk_nbt(cx=0, cz=0, top=63, material="minecraft:grass_block", legacy=False):
    """A one-block path and a small roof amid a flat material surface."""
    palette = [material, "minecraft:dirt_path", "minecraft:cobblestone", "minecraft:oak_stairs"]
    entries = []
    for i, name in enumerate(palette):
        # Mixed legacy/new states and wrapped compact strings occur in migrated chunks.
        key = "Name" if legacy else "id"
        if i == 1 and not legacy:
            key = ""
        fields = [(key, 8, string(name))]
        if i == 3:
            fields.append(("Properties" if legacy else "properties", 10,
                           compound([("facing", 8, string("east")), ("half", 8, string("top"))])))
        entries.append(compound(fields))
    indices = [0] * 4096
    for z in range(16):
        indices[(top & 15) * 256 + z * 16 + 3] = 1
        for x in range(10, 13):
            if 10 <= z <= 12:
                indices[(top & 15) * 256 + z * 16 + x] = 2 if x != 12 else 3
    states = compound([("palette", 9, nbt_list(10, entries)),
                       ("data", 12, long_array(packed(indices, 4)))])
    biomes = compound([("palette", 9, nbt_list(8, [string("minecraft:plains")]))])
    section = compound([("Y", 1, struct.pack(">b", top // 16)),
                        ("block_states", 10, states), ("biomes", 10, biomes)])
    heights = compound([("WORLD_SURFACE", 12, long_array(packed([top + 65] * 256, 9)))])
    root = compound([
        ("xPos", 3, struct.pack(">i", cx)), ("zPos", 3, struct.pack(">i", cz)),
        ("DataVersion", 3, struct.pack(">i", 4790 if legacy else 5023)),
        ("Status", 8, string("minecraft:full")), ("Heightmaps", 10, heights),
        ("sections", 9, nbt_list(10, [section])),
    ])
    return b"\x0a\0\0" + root


def write_region(world, cx=0, cz=0, top=63, material="minecraft:grass_block", legacy=False):
    payload = zlib.compress(chunk_nbt(cx, cz, top, material, legacy))
    chunk = struct.pack(">I", len(payload) + 1) + b"\x02" + payload
    sectors = (len(chunk) + 4095) // 4096
    header = bytearray(8192)
    slot = (cz % 32) * 32 + (cx % 32)
    struct.pack_into(">I", header, slot * 4, (2 << 8) | sectors)
    struct.pack_into(">I", header, 4096 + slot * 4, 1234567)
    path = world / "region" / f"r.{cx // 32}.{cz // 32}.mca"
    path.parent.mkdir(exist_ok=True)
    path.write_bytes(header + chunk.ljust(sectors * 4096, b"\0"))
    return path


class ExtractSurfaceTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.world = self.root / "world"
        self.world.mkdir()

    def test_path_roof_states_and_lossless_compact_archive(self):
        source = write_region(self.world)
        original = source.read_bytes()
        surface = extract_surface(self.world, 0, 0, size=16)
        self.assertEqual(sum(surface.valid), 256)
        self.assertEqual(set(surface.heights), {63})
        self.assertEqual(surface.palette[surface.states[4 * 16 + 3]][0], "minecraft:dirt_path")
        self.assertEqual(surface.palette[surface.states[10 * 16 + 10]][0], "minecraft:cobblestone")
        state = surface.palette[surface.states[10 * 16 + 12]]
        self.assertEqual(dict(state[1]), {"facing": "east", "half": "top"})
        output = self.root / "out"
        report = surface.save(output)
        self.assertEqual(report["array_bytes"], 16 * 16 * 5)
        self.assertEqual(report["unknown_material_columns"], {})
        with ZipFile(output / "surface.zip") as archive:
            metadata = json.loads(archive.read("metadata.json"))
            self.assertEqual(metadata["blocks_per_pixel"], 1)
            self.assertEqual(metadata["origin"], [0, 0])
            self.assertEqual(struct.unpack("<256h", archive.read("height.i16le")), (63,) * 256)
            self.assertEqual(struct.unpack("<256H", archive.read("state.u16le")), tuple(surface.states))
            self.assertEqual(archive.read("valid.u8"), bytes([1]) * 256)
            self.assertEqual(metadata["sources"][0]["timestamp"], 1234567)
        with Image.open(output / "surface.png") as preview:
            self.assertEqual(preview.size, (16, 16))
            self.assertNotEqual(preview.getpixel((3, 4)), preview.getpixel((4, 4)))
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((self.world / "chunk_cache.json").exists())

    def test_negative_origin_crosses_four_regions_without_mirroring(self):
        for cx, cz, top in ((-1, -1, -2), (0, -1, 0), (-1, 0, 30), (0, 0, 64)):
            write_region(self.world, cx, cz, top, legacy=cx < 0)
        surface = extract_surface(self.world, -1, -1, size=2)
        self.assertEqual(list(surface.heights), [-2, 0, 30, 64])
        self.assertEqual(list(surface.valid), [1, 1, 1, 1])
        self.assertEqual(dict(surface.versions), {4790: 2, 5023: 2})

    def test_missing_chunks_are_masked_not_fake_zero_height_terrain(self):
        write_region(self.world, top=0)
        surface = extract_surface(self.world, 15, 15, size=3)
        self.assertEqual(list(surface.valid), [1] + [0] * 8)
        self.assertEqual(list(surface.heights), [0] * 9)
        with self.assertRaisesRegex(ValueError, "No populated"):
            extract_surface(self.world, 512, 512, size=1)

    def test_second_extraction_reads_changed_blocks_without_stale_cache(self):
        write_region(self.world, top=63)
        old = extract_surface(self.world, 0, 0, size=1)
        write_region(self.world, top=80, material="minecraft:sand")
        new = extract_surface(self.world, 0, 0, size=1)
        self.assertEqual((old.heights[0], new.heights[0]), (63, 80))
        self.assertEqual(new.palette[new.states[0]][0], "minecraft:sand")
        self.assertNotEqual(old.sources[0]["sha256"], new.sources[0]["sha256"])

    def test_web_reader_keeps_existing_four_by_four_tile_contract(self):
        from backend.main import update_region_chunks
        for legacy in (False, True):
            with self.subTest(legacy=legacy):
                path = write_region(self.world, legacy=legacy)
                chunks, added = update_region_chunks(path, {})
                self.assertEqual(added, 1)
                tiles = chunks["0,0"]
                self.assertEqual(len(tiles), 16)
                self.assertEqual({(t["bx4"], t["bz4"]) for t in tiles},
                                 {(x, z) for x in range(4) for z in range(4)})
                self.assertEqual({t["ws"] for t in tiles}, {128})
                self.assertEqual({t["biome"] for t in tiles}, {"minecraft:plains"})
                self.assertTrue(all(t["top_block"].startswith("minecraft:") for t in tiles))

    def test_source_changes_and_truncation_are_rejected(self):
        path = write_region(self.world)
        chunks = region_chunks(path, [(0, 0)])
        next(chunks)
        path.write_bytes(path.read_bytes() + b"\0")
        with self.assertRaisesRegex(ValueError, "Region changed"):
            next(chunks)
        path.write_bytes(path.read_bytes()[:8195])
        with self.assertRaisesRegex(ValueError, "Truncated chunk"):
            extract_surface(self.world, 0, 0, size=1)


if __name__ == "__main__":
    unittest.main()
