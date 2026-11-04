"""Build the VanillaOnlineMapMC packs from a completed web render."""
import argparse
import gzip
import json
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DATAPACK = ROOT / "minecraft" / "datapack"
SIZE = (256, 144)
LEVELS = (1, 2, 4)
TOOLBAR = ("-", "+", "Home", "Here", "Pin", "List", "Del", "Exit")
FLOATING_UI = "c4e53176bf3babdce089371173569378eb5f590a"
CLICK_ADVANCEMENTS = {
    "data/floating_ui/advancement/left_click.json": "player_hurt_entity",
    "data/floating_ui/advancement/right_click.json": "player_interacted_with_entity",
}


def json_file(pack, path, data):
    pack.writestr(path, json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def metadata(pack, version, description):
    json_file(pack, "pack.mcmeta", {"pack": {
        "min_format": version, "max_format": version, "description": description
    }})


def click_advancement(trigger):
    return {"criteria": {"click": {
        "trigger": f"minecraft:{trigger}",
        "conditions": {"entity": {
            "type": "minecraft:entity_properties",
            "entity": "this",
            "predicate": {
                "minecraft:entity_type": "minecraft:interaction",
                "minecraft:nbt": '{Tags:["floating_ui_interaction"]}',
            },
        }},
    }}}


def export_upstream(checkout, output):
    """Package a local, pinned checkout without redistributing its source here."""
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != FLOATING_UI:
        raise ValueError(f"Expected Floating UI revision {FLOATING_UI}, got {revision}")
    meta = json.loads((checkout / "pack.mcmeta").read_text(encoding="utf-8"))
    overlays = meta["overlays"]["entries"]
    for entry in overlays:
        entry["min_format"] = entry["max_format"] = [121, 0]
    meta["pack"]["min_format"] = meta["pack"]["max_format"] = [121, 0]
    data_dirs = ["data"] + [f'{entry["directory"]}/data' for entry in overlays]

    with ZipFile(output / "floating-ui-datapack.zip", "w", ZIP_DEFLATED) as pack:
        json_file(pack, "pack.mcmeta", meta)
        for directory in data_dirs:
            for file in sorted((checkout / directory).rglob("*")):
                if file.is_file():
                    path = file.relative_to(checkout).as_posix()
                    if path in CLICK_ADVANCEMENTS:
                        json_file(pack, path, click_advancement(CLICK_ADVANCEMENTS[path]))
                    elif path.endswith("/data/math/function/particle/13_15.mcfunction"):
                        commands = file.read_text(encoding="utf-8").replace(
                            'block_state:{Name:"barrier"}', 'block_state:"minecraft:barrier"'
                        )
                        pack.writestr(path, commands)
                    elif path == "data/floating_ui/function/ray/move/root_check_point.mcfunction":
                        commands = file.read_text(encoding="utf-8").replace(
                            "execute at 1bf52-0-0-0-0 run function math:_particle", ""
                        )
                        pack.writestr(path, commands)
                    elif path.endswith("/data/math/function/init_overworld.mcfunction"):
                        # The raycast does not need the remote sign and chest helpers.
                        # Their chunks would stretch the online map's rendered bounds.
                        commands = file.read_text(encoding="utf-8").splitlines()
                        pack.writestr(path, "\n".join(line for line in commands if line not in {
                            "function math:marker/_sign", "function math:marker/_chest",
                        }) + "\n")
                    else:
                        pack.write(file, path)


def render_input(render_dir):
    png_path = render_dir / "map_base.png"
    index_path = render_dir / "tile_index.json.gz"
    png_time, index_time = png_path.stat().st_mtime_ns, index_path.stat().st_mtime_ns
    if index_time < png_time:
        raise ValueError("The web render is still being written. Retry once it is complete.")
    with gzip.open(index_path, "rt", encoding="utf-8") as stream:
        bounds = json.load(stream)["bounds"]
    minimum = (bounds["bx4_min"], bounds["bz4_min"])
    expected = (bounds["bx4_max"] - minimum[0] + 1, bounds["bz4_max"] - minimum[1] + 1)
    with Image.open(png_path) as image:
        if image.size != expected:
            raise ValueError("Map image and bounds differ. Export from a completed web render.")
        source = image.convert("RGBA")
    if (png_time, index_time) != (png_path.stat().st_mtime_ns, index_path.stat().st_mtime_ns):
        raise ValueError("The web render changed during export. Retry once it is complete.")
    return source, minimum


def build_packs(render_dir, checkout, output):
    source, minimum = render_input(render_dir)
    width, height = SIZE
    units = max((source.width + width - 1) // width, (source.height + height - 1) // height)
    padded_width, padded_height = width * units, height * units
    left, top = (padded_width - source.width) // 2, (padded_height - source.height) // 2
    origin = ((minimum[0] - left) * 4, (minimum[1] - top) * 4)
    levels = []

    with ZipFile(output / "vanilla-map-resources.zip", "w", ZIP_DEFLATED) as pack:
        metadata(pack, [97, 1], "VanillaOnlineMapMC map views")
        for file in sorted((checkout / "assets").rglob("*")):
            if file.is_file():
                pack.write(file, file.relative_to(checkout).as_posix())
        for zoom, grid in enumerate(LEVELS):
            tile_width, tile_height = padded_width // grid, padded_height // grid
            levels.append({"grid": grid, "pixel": units * 4 // grid,
                           "width": tile_width * 4, "height": tile_height * 4})
            for row in range(grid):
                for column in range(grid):
                    x, y = column * tile_width - left, row * tile_height - top
                    frame = Image.new("RGBA", SIZE, "#20252b")
                    frame.alpha_composite(source.transform(
                        SIZE, Image.Transform.EXTENT, (x, y, x + tile_width, y + tile_height),
                        resample=Image.Resampling.NEAREST
                    ))
                    draw_toolbar(frame, grid)
                    key = f"view/{zoom}/{column}/{row}"
                    png = BytesIO()
                    frame.save(png, format="PNG", optimize=True)
                    pack.writestr(f"assets/vanilla_map/textures/{key}.png", png.getvalue())
                    json_file(pack, f"assets/vanilla_map/items/{key}.json", {"model": {
                        "type": "minecraft:model", "model": f"vanilla_map:{key}"
                    }})
                    faces = {"south": {"uv": [0, 0, 16, 16], "texture": "#map"},
                             "north": {"uv": [16, 0, 0, 16], "texture": "#map"}}
                    json_file(pack, f"assets/vanilla_map/models/{key}.json", {
                        "ambientocclusion": False, "textures": {"map": f"vanilla_map:{key}"},
                        "elements": [{"from": [0, 0, 8], "to": [16, 16, 8], "faces": faces,
                                      "shade": False}]
                    })

    atlas = {"x": origin[0], "z": origin[1], "width": padded_width * 4,
             "height": padded_height * 4, "levels": levels}
    with ZipFile(output / "vanilla-map-datapack.zip", "w", ZIP_DEFLATED) as pack:
        metadata(pack, [121, 0], "VanillaOnlineMapMC floating map")
        for path in sorted(DATAPACK.rglob("*")):
            if path.is_file():
                pack.write(path, path.relative_to(DATAPACK).as_posix())
        pack.writestr("data/vanilla_map/function/load_atlas.mcfunction",
                      "data modify storage vanilla_map:atlas config set value "
                      + json.dumps(atlas, separators=(",", ":")) + "\n")


def draw_toolbar(frame, grid):
    draw = ImageDraw.Draw(frame)
    font = ImageFont.load_default()
    for index, label in enumerate(TOOLBAR):
        x = index * 32
        draw.rectangle((x, 5, x + 31, 17), fill="#20252b", outline="#647182")
        draw.text((x + 16, 11), label, anchor="mm", fill="white", font=font)
    draw.rectangle((2, 128, 33, 141), fill="#20252b")
    draw.text((5, 130), f"x{grid}", fill="white", font=font)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, default=ROOT / "backend" / "map_images")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--floating-ui", type=Path, required=True, help="Pinned Floating UI checkout")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.output) as temporary:
        staging = Path(temporary)
        export_upstream(args.floating_ui, staging)
        build_packs(args.render_dir, args.floating_ui, staging)
        for pack in sorted(staging.glob("*.zip")):
            pack.replace(args.output / pack.name)
            print(args.output / pack.name)


if __name__ == "__main__":
    main()
