"""Extract a bounded, one-block surface without touching the live map cache."""

import argparse
from array import array
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import struct
import sys
import time
from zipfile import ZIP_DEFLATED, ZipFile
import zlib

from PIL import Image

if __package__:
    from .map_colors import BLOCK_COLORS
    from .world_reader import (AIR, AIR_IDS, BlockStateReader, _rv, _rs,
                               _T_COMP, _unpack_heightmap, surface_y)
else:
    from map_colors import BLOCK_COLORS
    from world_reader import (AIR, AIR_IDS, BlockStateReader, _rv, _rs,
                              _T_COMP, _unpack_heightmap, surface_y)


# Material colors are a diagnostic surface palette, not vanilla model textures.
SURFACE_COLORS = {
    "grass_block": "#7ca650", "dirt_path": "#aa8955", "farmland": "#735035",
    "dirt": "#866043", "coarse_dirt": "#77553b", "rooted_dirt": "#866043",
    "podzol": "#715030", "mycelium": "#8b7890", "mud": "#51463e",
    "sand": "#d8cd91", "red_sand": "#bd733a", "gravel": "#8b8580",
    "stone": "#888888", "deepslate": "#505055", "andesite": "#878781",
    "diorite": "#c3c3bb", "granite": "#a07766", "tuff": "#74796b",
    "calcite": "#dfdfd0", "clay": "#a0a4b2", "bedrock": "#555555",
    "water": "#3979b3", "lava": "#ef6a10", "snow": "#edf5f5",
    "snow_block": "#edf5f5", "ice": "#a0c9ec", "packed_ice": "#92b7e4",
    "powder_snow": "#edf5f5",
    "blue_ice": "#78a5e3", "moss_block": "#607c31", "moss_carpet": "#607c31",
    "short_grass": "#7ca650", "tall_grass": "#7ca650", "fern": "#628641",
    "large_fern": "#628641", "seagrass": "#3979b3", "kelp": "#3979b3",
    "tall_seagrass": "#3979b3", "bubble_column": "#3979b3",
    "wildflowers": "#c7b898", "dandelion": "#eacb43", "azure_bluet": "#deded0",
    "oxeye_daisy": "#deded0", "poppy": "#c14c40", "cornflower": "#6285c7",
    "allium": "#a381b7", "bush": "#628641", "firefly_bush": "#628641",
    "sugar_cane": "#8eaa52", "bamboo": "#8eaa52", "leaf_litter": "#97784e",
    "vine": "#527d35", "dripstone_block": "#a2856b", "pointed_dripstone": "#a2856b",
    "obsidian": "#30273d", "sculk": "#163b3d", "sculk_vein": "#163b3d",
    "sculk_catalyst": "#567369", "warped_nylium": "#397c79",
    "oak_leaves": "#527d35", "birch_leaves": "#6d8a3d",
    "spruce_leaves": "#3b6142", "cherry_leaves": "#e8aac5",
    "pale_oak_leaves": "#8d9474", "azalea_leaves": "#527d35",
    "flowering_azalea_leaves": "#91747c", "netherrack": "#813e3e",
    "end_stone": "#d8d9a0",
}


def material_color(name: str) -> str | None:
    """Return None for unhandled materials so the diagnostic reports them."""
    short = name.removeprefix("minecraft:")
    if name.startswith("minecraft:") and short in SURFACE_COLORS:
        return SURFACE_COLORS[short]
    color = BLOCK_COLORS.get(name)
    if color:
        return color
    if name.startswith("minecraft:"):
        if short.endswith("_leaves"):
            return "#527d35"
        if short.endswith(("_log", "_wood", "_stem", "_hyphae")):
            return "#795b37"
        if short.endswith(("_sign", "_fence_gate", "_button")):
            return "#795b37" if not short.startswith("stone_") else "#888888"
        if short.endswith(("_torch", "_lantern")) or short == "torch":
            return "#d0a04a"
        if short.endswith("_ore"):
            return "#505055" if short.startswith("deepslate_") else "#888888"
        if "amethyst" in short:
            return "#9672b0"
        for suffix in ("_stairs", "_slab", "_wall"):
            if short.endswith(suffix):
                base = short[:-len(suffix)]
                return (BLOCK_COLORS.get("minecraft:" + base)
                        or BLOCK_COLORS.get("minecraft:" + base + "s")
                        or SURFACE_COLORS.get(base))
    return None


def region_chunks(path: Path, coordinates):
    """Read only requested chunks and reject a region changed during the read."""
    before = path.stat()
    with path.open("rb") as stream:
        header = stream.read(8192)
        if len(header) != 8192:
            raise ValueError(f"Truncated region header: {path}")
        for cx, cz in coordinates:
            slot = (cx % 32) + (cz % 32) * 32
            location = struct.unpack_from(">I", header, slot * 4)[0]
            offset, sectors = location >> 8, location & 255
            if offset == 0 and sectors == 0:
                continue
            if offset < 2 or sectors == 0:
                raise ValueError(f"Invalid chunk location: {path}, {cx},{cz}")
            stream.seek(offset * 4096)
            chunk_header = stream.read(5)
            if len(chunk_header) != 5:
                raise ValueError(f"Truncated chunk: {path}, {cx},{cz}")
            length, compression = struct.unpack(">IB", chunk_header)
            if compression & 128:
                raise ValueError("External .mcc chunks are not supported by this prototype")
            if length < 1 or length + 4 > sectors * 4096:
                raise ValueError(f"Invalid chunk length: {path}, {cx},{cz}")
            payload = stream.read(length - 1)
            if len(payload) != length - 1:
                raise ValueError(f"Truncated chunk payload: {path}, {cx},{cz}")
            if compression == 1:
                raw = gzip.decompress(payload)
            elif compression == 2:
                raw = zlib.decompress(payload)
            elif compression == 3:
                raw = payload
            else:
                raise ValueError(f"Unsupported region compression: {compression}")
            if not raw or raw[0] != _T_COMP:
                raise ValueError("Expected an NBT compound root")
            _, start = _rs(raw, 1)
            root, end = _rv(raw, start, _T_COMP)
            if end != len(raw):
                raise ValueError("Unexpected trailing chunk data")
            if (root.get("xPos"), root.get("zPos")) != (cx, cz):
                raise ValueError(f"Chunk coordinates do not match region slot: {cx},{cz}")
            provenance = {
                "chunk": [cx, cz], "region": path.name,
                "timestamp": struct.unpack_from(">I", header, 4096 + slot * 4)[0],
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
            yield root, provenance
    after = path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError(f"Region changed during extraction; retry from a snapshot: {path}")


class Surface:
    """Five bytes per column: signed Y, state ID and validity, plus a palette."""

    def __init__(self, origin_x, origin_z, size, min_y):
        self.origin_x, self.origin_z, self.size, self.min_y = origin_x, origin_z, size, min_y
        self.heights = array("h", [0]) * (size * size)
        self.states = array("H", [0]) * (size * size)
        self.valid = bytearray(size * size)
        self.palette = [AIR]
        self._state_ids = {AIR: 0}
        self.sources = []
        self.versions = Counter()

    def add_chunk(self, root):
        if root.get("Status") != "minecraft:full":
            return
        self.versions[root.get("DataVersion", 0)] += 1
        heightmap = root.get("Heightmaps", {}).get("WORLD_SURFACE")
        if not heightmap:
            return
        if len(heightmap) != 37:
            raise ValueError("This crop extractor requires padded 1.18+ heightmaps (37 longs)")
        if "yPos" in root and root["yPos"] * 16 != self.min_y:
            raise ValueError("Chunk dimension minimum differs from --min-y")
        reader = BlockStateReader(root.get("sections", []))
        heights = _unpack_heightmap(heightmap)
        cx, cz = root["xPos"], root["zPos"]
        for z in range(16):
            pz = cz * 16 + z - self.origin_z
            if not 0 <= pz < self.size:
                continue
            for x in range(16):
                px = cx * 16 + x - self.origin_x
                if not 0 <= px < self.size:
                    continue
                y = surface_y(heights[z * 16 + x], self.min_y)
                if y is None:
                    continue
                state = reader.state_at(x, y, z)
                if state[0] in AIR_IDS:
                    raise ValueError(f"Heightmap points to air in chunk {cx},{cz}, column {x},{z}")
                if state not in self._state_ids:
                    if len(self.palette) >= 65536:
                        raise ValueError("Surface state palette exceeds uint16 capacity")
                    self._state_ids[state] = len(self.palette)
                    self.palette.append(state)
                i = pz * self.size + px
                self.heights[i] = y
                self.states[i] = self._state_ids[state]
                self.valid[i] = 1

    def metadata(self):
        return {
            "format": "vanilla-map-surface", "version": 1,
            "origin": [self.origin_x, self.origin_z], "size": [self.size, self.size],
            "blocks_per_pixel": 1, "min_y": self.min_y,
            "layout": "row-major; index = (z-origin_z)*width + (x-origin_x)",
            "height": {"file": "height.i16le", "meaning": "surface block world Y"},
            "state": {"file": "state.u16le", "meaning": "palette index"},
            "valid": {"file": "valid.u8", "meaning": "1=surface present; 0=missing or empty"},
            "palette": [{"id": name, "properties": dict(properties)}
                        for name, properties in self.palette],
            "valid_columns": sum(self.valid), "data_versions": dict(self.versions),
            "sources": self.sources,
        }

    def save(self, output: Path):
        output.mkdir(parents=True, exist_ok=True)
        with ZipFile(output / "surface.zip", "w", ZIP_DEFLATED) as archive:
            archive.writestr("metadata.json", json.dumps(self.metadata(), indent=2))
            for name, values in (("height.i16le", self.heights), ("state.u16le", self.states)):
                little = array(values.typecode, values)
                if sys.byteorder != "little":
                    little.byteswap()
                archive.writestr(name, little.tobytes())
            archive.writestr("valid.u8", self.valid)
        colors = [material_color(state[0]) for state in self.palette]
        rgba = bytearray(self.size * self.size * 4)
        unknown = Counter()
        for i, valid in enumerate(self.valid):
            if valid:
                color = colors[self.states[i]]
                if color is None:
                    unknown[self.palette[self.states[i]][0]] += 1
                    color = "#ff00ff"
                rgba[i*4:i*4+4] = bytes.fromhex(color[1:]) + b"\xff"
        Image.frombytes("RGBA", (self.size, self.size), bytes(rgba)).save(output / "surface.png")
        report = {
            "valid_columns": sum(self.valid), "total_columns": self.size * self.size,
            "array_bytes": len(self.heights) * 2 + len(self.states) * 2 + len(self.valid),
            "surface_zip_bytes": (output / "surface.zip").stat().st_size,
            "unknown_material_columns": dict(unknown.most_common()),
        }
        return report


def extract_surface(world: Path, origin_x: int, origin_z: int, size=512, min_y=-64):
    if not 1 <= size <= 2048:
        raise ValueError("Crop size must be between 1 and 2048 blocks")
    if not -32768 <= min_y <= 32767 - 511:
        raise ValueError("min_y is outside the signed int16 height range")
    surface = Surface(origin_x, origin_z, size, min_y)
    regions = {}
    for cz in range(origin_z // 16, (origin_z + size - 1) // 16 + 1):
        for cx in range(origin_x // 16, (origin_x + size - 1) // 16 + 1):
            regions.setdefault((cx // 32, cz // 32), []).append((cx, cz))
    for (rx, rz), coordinates in sorted(regions.items()):
        path = world / "region" / f"r.{rx}.{rz}.mca"
        if not path.exists():
            continue
        for root, source in region_chunks(path, coordinates):
            surface.add_chunk(root)
            surface.sources.append(source)
    if not any(surface.valid):
        raise ValueError("No populated surface columns in the requested crop")
    return surface


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True, help="Directory containing region/")
    parser.add_argument("--origin-x", type=int, required=True)
    parser.add_argument("--origin-z", type=int, required=True)
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--min-y", type=int, default=-64, help="Dimension minimum Y")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    # Do not allow generated files inside the input world directory.
    if args.world.resolve() == args.output.resolve() or args.world.resolve() in args.output.resolve().parents:
        parser.error("Output must be outside the world directory")
    start = time.perf_counter()
    surface = extract_surface(args.world, args.origin_x, args.origin_z, args.size, args.min_y)
    report = surface.save(args.output)
    report["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
