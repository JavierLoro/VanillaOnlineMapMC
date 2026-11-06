"""Render all populated MCA regions into bounded, one-block terrain textures."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct
import time

from PIL import Image

if __package__:
    from .compare_surface import Raster, render
    from .extract_surface import extract_window, material_color
else:
    from compare_surface import Raster, render
    from extract_surface import extract_window, material_color


MAX_TILES = 15  # Leave one of OpenGL 3.3's 16 guaranteed fragment samplers for state.


def discover_world(world: Path):
    """Use allocated chunk slots; unfinished chunks remain transparent on rendering."""
    coordinates, sources = [], []
    for path in sorted((world / "region").glob("r.*.*.mca")):
        before = path.stat()
        if before.st_size == 0:
            continue
        _, rx, rz = path.stem.split(".")
        rx, rz = int(rx), int(rz)
        with path.open("rb") as stream:
            header = stream.read(8192)
        if len(header) != 8192:
            raise ValueError(f"Truncated region: {path.name}")
        for i in range(1024):
            value = struct.unpack_from(">I", header, i * 4)[0]
            if value:
                if value >> 8 < 2 or value & 255 == 0:
                    raise ValueError(f"Invalid region location: {path.name}, slot {i}")
                coordinates.append((rx * 32 + i % 32, rz * 32 + i // 32))
        sources.append({"name": path.name, "bytes": before.st_size, "mtime_ns": before.st_mtime_ns,
                        "header_sha256": hashlib.sha256(header).hexdigest()})
    if not coordinates:
        raise ValueError("No allocated chunks found")
    x0, z0 = min(x for x, z in coordinates) * 16, min(z for x, z in coordinates) * 16
    width = (max(x for x, z in coordinates) + 1) * 16 - x0
    height = (max(z for x, z in coordinates) + 1) * 16 - z0
    return (x0, z0), (width, height), sources


def validate_sources(world: Path, sources):
    current = {p.name for p in (world / "region").glob("r.*.*.mca") if p.stat().st_size}
    if current != {s["name"] for s in sources}:
        raise ValueError("World region list changed during rendering")
    for source in sources:
        stat = (world / "region" / source["name"]).stat()
        if (stat.st_size, stat.st_mtime_ns) != (source["bytes"], source["mtime_ns"]):
            raise ValueError("World changed during rendering; use a stable snapshot")


def render_world(world: Path, output: Path, tile_size=4096, min_y=-64):
    if not 1 <= tile_size <= 4096:
        raise ValueError("Tile size must be between 1 and 4096")
    world, output = world.resolve(), output.resolve()
    if output == world or world in output.parents:
        raise ValueError("Output must be outside the source world")
    if (output / "world-map.json").exists():
        raise ValueError("Use a fresh output directory for each generation")
    started = time.perf_counter()
    origin, size, sources = discover_world(world)
    grid = [math.ceil(axis / tile_size) for axis in size]
    if grid[0] * grid[1] > MAX_TILES:
        raise ValueError(f"World needs {grid[0] * grid[1]} tiles; supported maximum is {MAX_TILES}")
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"format": "vanilla-map-world", "version": 1, "blocks_per_pixel": 1,
                "origin": list(origin), "world_size": list(size), "tile_size": tile_size,
                "grid": grid, "min_y": min_y, "vertical_scale": 1,
                "unknown_color": "#6a6a6a", "tiles": [], "sources": sources}
    unknown = Counter()
    for tz in range(grid[1]):
        for tx in range(grid[0]):
            tick = time.perf_counter()
            width, height = (min(tile_size, size[0] - tx * tile_size),
                             min(tile_size, size[1] - tz * tile_size))
            # Neighbor heights are read past the tile edge to prevent lighting seams.
            surface = extract_window(world, origin[0] + tx * tile_size - 1,
                                     origin[1] + tz * tile_size - 1,
                                     max(width, height) + 2, min_y, allow_empty=True)
            valid = 0
            for z in range(1, height + 1):
                for x in range(1, width + 1):
                    i = z * surface.size + x
                    if surface.valid[i]:
                        valid += 1
                        name = surface.palette[surface.states[i]][0]
                        if material_color(name) is None:
                            unknown[name] += 1
            if valid:
                raster = Raster(surface.size, 1, surface.heights, surface.states,
                                surface.valid, surface.palette)
                _, shaded = render(raster, unknown_color=manifest["unknown_color"], include_base=False)
                texture = shaded.crop((1, 1, width + 1, height + 1))
                shaded.close()
            else:
                texture = Image.new("RGBA", (width, height))
            name = f"tile-{tx}-{tz}.png"
            destination = output / name
            texture.save(destination, optimize=True)
            texture.close()
            tile = {"cell": [tx, tz], "size": [width, height], "file": name,
                    "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                    "png_bytes": destination.stat().st_size, "valid_columns": valid}
            manifest["tiles"].append(tile)
            print(json.dumps({"tile": len(manifest["tiles"]), "total": grid[0] * grid[1],
                              "valid_columns": valid, "seconds": round(time.perf_counter()-tick, 2)}), flush=True)
            del surface
    validate_sources(world, sources)
    manifest["valid_columns"] = sum(t["valid_columns"] for t in manifest["tiles"])
    manifest["png_bytes"] = sum(t["png_bytes"] for t in manifest["tiles"])
    manifest["rgba_bytes"] = size[0] * size[1] * 4
    manifest["unknown_material_columns"] = dict(unknown.most_common())
    manifest["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    temporary = output / "world-map.json.new"
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(output / "world-map.json")
    print(json.dumps({k: manifest[k] for k in ("world_size", "valid_columns", "png_bytes",
                                             "rgba_bytes", "elapsed_seconds")}), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--world", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=4096)
    parser.add_argument("--min-y", type=int, default=-64)
    args = parser.parse_args()
    render_world(args.world, args.output, args.tile_size, args.min_y)


if __name__ == "__main__":
    main()
