"""Compare surface resolutions with the same material palette and hillshading."""

import argparse
from array import array
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFont

if __package__:
    from .extract_surface import Surface, material_color
    from .world_reader import normalize_block_state
else:
    from extract_surface import Surface, material_color
    from world_reader import normalize_block_state


def load_surface(path: Path) -> Surface:
    """Read the version-one compact archive without consulting world files."""
    with ZipFile(path) as archive:
        metadata = json.loads(archive.read("metadata.json"))
        if (metadata.get("format"), metadata.get("version"), metadata.get("blocks_per_pixel")) != (
                "vanilla-map-surface", 1, 1):
            raise ValueError("Expected a version-one, one-block surface archive")
        width, height = metadata["size"]
        if width != height or not isinstance(width, int) or not 1 <= width <= 2048:
            raise ValueError("Expected a square surface between 1 and 2048 blocks")
        surface = Surface(*metadata["origin"], width, metadata["min_y"])
        for name, attribute, code in (("height.i16le", "heights", "h"),
                                      ("state.u16le", "states", "H")):
            if archive.getinfo(name).file_size != width * height * 2:
                raise ValueError(f"Invalid surface array length: {name}")
            values = array(code)
            values.frombytes(archive.read(name))
            if sys.byteorder != "little":
                values.byteswap()
            setattr(surface, attribute, values)
        if archive.getinfo("valid.u8").file_size != width * height:
            raise ValueError("Invalid surface validity length")
        surface.valid = bytearray(archive.read("valid.u8"))
        surface.palette = [normalize_block_state(state) for state in metadata["palette"]]
        if not surface.palette or any(value not in (0, 1) for value in surface.valid):
            raise ValueError("Invalid surface palette or validity values")
        if any(index >= len(surface.palette) for index in surface.states):
            raise ValueError("Surface state index outside palette")
        surface.sources = metadata.get("sources", [])
        surface.versions.update({int(k): v for k, v in metadata.get("data_versions", {}).items()})
        surface._state_ids = {state: i for i, state in enumerate(surface.palette)}
    return surface


@dataclass
class Raster:
    size: int
    spacing: int
    heights: array
    states: array
    valid: bytearray
    palette: list


def sample_surface(surface: Surface, spacing: int) -> Raster:
    """Average height; sample material at +1,+1 in each four-block cell."""
    if spacing not in (1, 4) or surface.size % spacing:
        raise ValueError("Resolution must be 1 or 4 and divide the surface size")
    if surface.origin_x % spacing or surface.origin_z % spacing:
        raise ValueError("Crop origin must align with the world sampling grid")
    size = surface.size // spacing
    heights, states, valid = array("f", [0]) * (size * size), array("H", [0]) * (size * size), bytearray(size * size)
    for z in range(size):
        for x in range(size):
            indices = [(z * spacing + dz) * surface.size + x * spacing + dx
                       for dz in range(spacing) for dx in range(spacing)]
            i = z * size + x
            # A hole never contributes a fabricated zero height or material.
            if all(surface.valid[j] for j in indices):
                heights[i] = sum(surface.heights[j] for j in indices) / len(indices)
                offset = 1 if spacing == 4 else 0
                sample = (z * spacing + offset) * surface.size + x * spacing + offset
                states[i] = surface.states[sample]
                valid[i] = 1
    return Raster(size, spacing, heights, states, valid, surface.palette)


def hillshade(raster: Raster, x: int, z: int, vertical_scale=1.0) -> float:
    """Use the web light coefficients and floor, with derivatives in world blocks."""
    size = raster.size
    center = raster.heights[z * size + x]

    def height_at(px, pz):
        if 0 <= px < size and 0 <= pz < size and raster.valid[pz * size + px]:
            return raster.heights[pz * size + px]
        return center

    dx = (height_at(x + 1, z) - height_at(x - 1, z)) * vertical_scale / (2 * raster.spacing)
    dz = (height_at(x, z + 1) - height_at(x, z - 1)) * vertical_scale / (2 * raster.spacing)
    light = (1 - dx - dz) / math.sqrt(3 * (dx * dx + 1 + dz * dz))
    return max(0.3, min(1.0, light))


def render(raster: Raster, vertical_scale=1.0, unknown_color="#ff00ff", include_base=True):
    if not math.isfinite(vertical_scale) or vertical_scale <= 0:
        raise ValueError("Vertical scale must be a positive finite number")
    colors = [bytes.fromhex((material_color(name) or unknown_color)[1:])
              for name, _ in raster.palette]
    base = bytearray(raster.size * raster.size * 4) if include_base else None
    shaded = bytearray(raster.size * raster.size * 4)
    for i, valid in enumerate(raster.valid):
        if valid:
            color = colors[raster.states[i]]
            light = hillshade(raster, i % raster.size, i // raster.size, vertical_scale)
            if base is not None:
                base[i*4:i*4+4] = color + b"\xff"
            shaded[i*4:i*4+4] = bytes(int(channel * light) for channel in color) + b"\xff"
    dimensions = (raster.size, raster.size)
    return (Image.frombytes("RGBA", dimensions, bytes(base)) if base is not None else None,
            Image.frombytes("RGBA", dimensions, bytes(shaded)))


def path_metrics(surface: Surface, coarse: Raster):
    """Measure exact overlap, so thickened paths cannot masquerade as extra detail."""
    path_ids = {i for i, (name, _) in enumerate(surface.palette) if name == "minecraft:dirt_path"}
    actual = predicted = overlap = 0
    for i, valid in enumerate(surface.valid):
        if valid:
            x, z = i % surface.size, i // surface.size
            ci = (z // 4) * coarse.size + x // 4
            truth = surface.states[i] in path_ids
            estimate = bool(coarse.valid[ci] and coarse.states[ci] in path_ids)
            actual += truth
            predicted += estimate
            overlap += truth and estimate
    return {
        "actual_path_blocks": actual, "coarse_path_area_blocks": predicted,
        "overlapping_path_blocks": overlap,
        "recall": overlap / actual if actual else None,
        "precision": overlap / predicted if predicted else None,
    }


def detail_box(surface: Surface, size=128):
    """Select the road-richest window on a fixed 32-block grid, including crop edges."""
    size = min(size, surface.size)
    path_ids = {i for i, (name, _) in enumerate(surface.palette) if name == "minecraft:dirt_path"}
    width = surface.size
    stride = width + 1
    prefix = array("I", [0]) * (stride * stride)
    for z in range(width):
        row = 0
        for x in range(width):
            i = z * width + x
            row += bool(surface.valid[i] and surface.states[i] in path_ids)
            prefix[(z+1)*stride+x+1] = prefix[z*stride+x+1] + row
    positions = sorted(set(range(0, width - size + 1, 32)) | {width - size})
    best = (-1, 0, 0)
    for z in positions:
        for x in positions:
            count = (prefix[(z+size)*stride+x+size] - prefix[z*stride+x+size]
                     - prefix[(z+size)*stride+x] + prefix[z*stride+x])
            if count > best[0]:
                best = count, x, z
    _, x, z = best
    return x, z, x + size, z + size


def comparison_panel(coarse, fine, path: Path):
    """Save an exportable figure at identical pixel scale on each side."""
    width, height = fine.size
    panel = Image.new("RGB", (width * 2 + 48, height + 60), "#151b21")
    draw = ImageDraw.Draw(panel)
    try:
        font = ImageFont.load_default(size=22)
    except TypeError:  # Pillow 10.0 does not expose the size argument.
        font = ImageFont.load_default()
    for image, label, x in ((coarse, "4x4", 16), (fine, "1x1", width + 32)):
        draw.text((x, 12), label, font=font, fill="#edf1f4")
        panel.paste(image, (x, 48), image)
    panel.save(path)


def compare(path: Path, output: Path, vertical_scale=1.0):
    start = time.perf_counter()
    surface = load_surface(path)
    coarse = sample_surface(surface, 4)
    fine = sample_surface(surface, 1)
    output.mkdir(parents=True, exist_ok=True)
    images = {}
    timings = {}
    for label, raster in (("4x4", coarse), ("1x1", fine)):
        tick = time.perf_counter()
        base, shaded = render(raster, vertical_scale)
        timings[label] = round(time.perf_counter() - tick, 4)
        base.save(output / f"materials-{label}.png")
        shaded.save(output / f"hillshade-{label}.png")
        images[label] = shaded.resize((surface.size, surface.size), Image.Resampling.NEAREST)
    comparison_panel(images["4x4"], images["1x1"], output / "comparison.png")
    box = detail_box(surface)
    details = [images[label].crop(box).resize((512, 512), Image.Resampling.NEAREST)
               for label in ("4x4", "1x1")]
    comparison_panel(*details, output / "detail.png")
    report = {
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "origin": [surface.origin_x, surface.origin_z], "world_size": [surface.size] * 2,
        "method": {
            "palette": "same approximate material palette, not biome colors or block models",
            "coarse_height": "mean of all 16 valid columns; no rounding",
            "coarse_material": "sample at offset +1,+1, matching the web reader",
            "mask": "coarse cell is valid only if all 16 columns are valid",
            "hillshade": "100% multiply; same light and 0.3 floor; physical block spacing; no blur",
            "vertical_scale": vertical_scale,
            "production_difference": "current web divides slopes by cell count, exaggerating 4x4 slopes by four",
        },
        "native_image_size": {"4x4": [coarse.size] * 2, "1x1": [fine.size] * 2},
        "path_overlap": path_metrics(surface, coarse),
        "detail": {"pixel_box": list(box),
                   "world_origin": [surface.origin_x + box[0], surface.origin_z + box[1]],
                   "world_size": box[2] - box[0],
                   "selection": "maximum dirt_path coverage on a fixed 32-block grid"},
        "render_seconds": timings,
        "png_bytes": {name: (output / name).stat().st_size
                      for name in ("materials-4x4.png", "materials-1x1.png",
                                   "hillshade-4x4.png", "hillshade-1x1.png")},
        "elapsed_seconds": round(time.perf_counter() - start, 4),
    }
    (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vertical-scale", type=float, default=1.0)
    args = parser.parse_args()
    print(json.dumps(compare(args.surface, args.output, args.vertical_scale), indent=2))


if __name__ == "__main__":
    main()
