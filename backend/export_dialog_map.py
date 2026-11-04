"""Export a native Java 26.3 dialog from the web map's completed render."""

import argparse
import gzip
import json
from io import BytesIO
from math import ceil
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DATAPACK = ROOT / "minecraft" / "dialog" / "datapack"
NAMESPACE = "vanilla_map_dialog"
COLUMNS = 6
SECTOR_ROWS = 3
TILE_WIDTH = 48
LINE_HEIGHT = 9
TEXT_PADDING = 4
LINES_PER_SECTOR = 6
LINES = SECTOR_ROWS * LINES_PER_SECTOR
MARKER_STEP = 6
MARKER_VARIANTS = TILE_WIDTH // MARKER_STEP
WIDTH, HEIGHT = COLUMNS * TILE_WIDTH, LINES * LINE_HEIGHT
ATLAS_COLUMNS = 18


def json_text(value):
    return json.dumps(value, separators=(",", ":"))


def render_frame(render_dir):
    image_path = render_dir / "map_base.png"
    index_path = render_dir / "tile_index.json.gz"
    times = image_path.stat().st_mtime_ns, index_path.stat().st_mtime_ns
    if times[1] < times[0]:
        raise ValueError("The tile index predates the map image. Export from a completed render.")
    with gzip.open(index_path, "rt", encoding="utf-8") as index:
        bounds = json.load(index)["bounds"]
    min_x, min_z = bounds["bx4_min"], bounds["bz4_min"]
    size = bounds["bx4_max"] - min_x + 1, bounds["bz4_max"] - min_z + 1
    with Image.open(image_path) as source:
        if source.size != size:
            raise ValueError("The map image and tile index bounds do not match.")
        step = max(1, ceil(size[0] * 4 / WIDTH), ceil(size[1] * 4 / HEIGHT))
        pad_x = (WIDTH * step - size[0] * 4) // 2
        pad_z = (HEIGHT * step - size[1] * 4) // 2
        extent = (-pad_x / 4, -pad_z / 4, (WIDTH * step - pad_x) / 4, (HEIGHT * step - pad_z) / 4)
        frame = Image.new("RGBA", (WIDTH, HEIGHT), "#1d2730")
        frame.alpha_composite(source.convert("RGBA").transform(
            frame.size, Image.Transform.EXTENT, extent, Image.Resampling.NEAREST
        ))
    if times != (image_path.stat().st_mtime_ns, index_path.stat().st_mtime_ns):
        raise ValueError("The map changed during export. Retry once the render is complete.")
    return frame, min_x * 4 - pad_x, min_z * 4 - pad_z, step


def make_glyphs(frame):
    glyph_count = COLUMNS * LINES * (1 + MARKER_VARIANTS)
    atlas = Image.new("RGBA", (ATLAS_COLUMNS * TILE_WIDTH, ceil(glyph_count / ATLAS_COLUMNS) * LINE_HEIGHT))
    glyphs = [chr(0xE000 + index) for index in range(glyph_count)]
    for line in range(LINES):
        for column in range(COLUMNS):
            left, top = column * TILE_WIDTH, line * LINE_HEIGHT
            tile = frame.crop((left, top, left + TILE_WIDTH, top + LINE_HEIGHT))
            for variant in range(1 + MARKER_VARIANTS):
                image = tile.copy()
                if variant:
                    x = (variant - 1) * MARKER_STEP + MARKER_STEP // 2
                    ImageDraw.Draw(image).ellipse((x - 2, 2, x + 2, 6), fill="white", outline="#101820")
                index = (line * COLUMNS + column) * (1 + MARKER_VARIANTS) + variant
                atlas.paste(image, (index % ATLAS_COLUMNS * TILE_WIDTH, index // ATLAS_COLUMNS * LINE_HEIGHT))
    rows = ["".join(glyphs[start:start + ATLAS_COLUMNS]) for start in range(0, glyph_count, ATLAS_COLUMNS)]
    return atlas, glyphs, rows


def trigger(value):
    return {"action": "run_command", "command": f"trigger vmd_action set {value}"}


def make_dialog(glyphs):
    contents = []
    for line in range(LINES):
        if line:
            contents.append({"text": "\n"})
        for column in range(COLUMNS):
            index = (line * COLUMNS + column) * (1 + MARKER_VARIANTS)
            sector = line // LINES_PER_SECTOR * COLUMNS + column + 1
            contents.append({"text": glyphs[index], "click_event": trigger(sector)})
    refresh = trigger(99)
    refresh["type"] = refresh.pop("action")
    # The dialog widget reserves padding inside its declared width.
    body_width = COLUMNS * (TILE_WIDTH + 1) + 2 * TEXT_PADDING
    return {
        "type": "minecraft:multi_action",
        "title": [{"text": "World map"}, {"text": ""}, {"text": ""}],
        "pause": False,
        "after_action": "none",
        "body": {"type": "minecraft:plain_message", "width": body_width,
                 "contents": {"text": "", "font": f"{NAMESPACE}:map", "color": "white",
                              "shadow_color": 0, "extra": contents}},
        "actions": [{"label": "Refresh position", "width": 142, "action": refresh},
                    {"label": "Clear selection", "width": 142,
                     "action": {"type": "run_command", "command": "trigger vmd_action set 98"}}],
        "columns": 2,
        "exit_action": {"label": "Close", "width": 100,
                        "action": {"type": "run_command", "command": "trigger vmd_action set 97"}},
    }


def write_metadata(pack, version, description):
    pack.writestr("pack.mcmeta", json_text({"pack": {
        "min_format": version, "max_format": version, "description": description
    }}))


def build(render_dir, output):
    frame, origin_x, origin_z, step = render_frame(render_dir)
    atlas, glyphs, rows = make_glyphs(frame)
    png = BytesIO()
    atlas.save(png, format="PNG", optimize=True)
    dialog = make_dialog(glyphs)
    with ZipFile(output / "vanilla-map-dialog-resources.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [97, 1], "VanillaOnlineMapMC dialog textures")
        pack.writestr(f"assets/{NAMESPACE}/textures/font/map.png", png.getvalue())
        pack.writestr(f"assets/{NAMESPACE}/font/map.json", json_text({"providers": [{
            "type": "bitmap", "file": f"{NAMESPACE}:font/map.png",
            "height": LINE_HEIGHT, "ascent": 7, "chars": rows,
        }]}))
    constants = {
        "origin_x": origin_x, "origin_z": origin_z, "step": step, "width": WIDTH, "height": HEIGHT,
        "tile": TILE_WIDTH, "line": LINE_HEIGHT, "columns": COLUMNS, "stride": COLUMNS + 1,
        "marker_step": MARKER_STEP, "variants": 1 + MARKER_VARIANTS, "sectors": COLUMNS * SECTOR_ROWS,
    }
    commands = [f"scoreboard players set #{key} vmd_calc {value}" for key, value in constants.items()]
    commands.extend([
        f"data modify storage {NAMESPACE}:atlas dialog set value {json_text(dialog)}",
        f"data modify storage {NAMESPACE}:atlas glyphs set value {json_text(glyphs)}",
        f"data modify storage {NAMESPACE}:atlas sectors set value " + json_text([
            f" | Selected {chr(65 + column)}{row + 1}"
            for row in range(SECTOR_ROWS) for column in range(COLUMNS)
        ]),
    ])
    with ZipFile(output / "vanilla-map-dialog-datapack.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [121, 0], "VanillaOnlineMapMC dialog test")
        for path in sorted(DATAPACK.rglob("*")):
            if path.is_file():
                pack.write(path, path.relative_to(DATAPACK).as_posix())
        pack.writestr(f"data/{NAMESPACE}/function/load_atlas.mcfunction", "\n".join(commands) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, default=ROOT / "backend" / "map_images")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output) as temporary:
        staging = Path(temporary)
        build(args.render_dir, staging)
        for path in sorted(staging.glob("*.zip")):
            destination = args.output / path.name
            path.replace(destination)
            print(destination)


if __name__ == "__main__":
    main()
