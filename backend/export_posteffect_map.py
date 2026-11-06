"""Build fullscreen map packs, optionally adding a one-block surface detail."""

import argparse
import gzip
import hashlib
import json
import math
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "minecraft" / "posteffect"
NAMESPACE = "vanilla_map_post"
TEXTURE_LIMIT = 2048
PAN_CENTER = 32767
RELIEF_LAYERS = (("hillshade", 1.0),)


def read_render(render_dir, style="relief"):
    if style not in {"relief", "biomes"}:
        raise ValueError(f"Unknown map style: {style}")
    png_path = render_dir / "map_base.png"
    index_path = render_dir / "tile_index.json.gz"
    layers = tuple((render_dir / f"map_{name}.png", strength)
                   for name, strength in RELIEF_LAYERS) if style == "relief" else ()
    for path, _ in layers:
        if not path.is_file():
            raise ValueError(f"Relief requires {path.name} from the same web render; "
                             "regenerate the render or use --style biomes.")
    files = (png_path, *(path for path, _ in layers), index_path)
    timestamps = tuple(path.stat().st_mtime_ns for path in files)
    if timestamps[-1] < max(timestamps[:-1]) or any(
        timestamp < timestamps[0] for timestamp in timestamps[1:-1]
    ):
        raise ValueError("Map layers and tile index must come from the same completed render.")

    with gzip.open(index_path, "rt", encoding="utf-8") as index:
        bounds = json.load(index)["bounds"]
    min_x, min_z = bounds["bx4_min"], bounds["bz4_min"]
    width = bounds["bx4_max"] - min_x + 1
    height = bounds["bz4_max"] - min_z + 1
    with Image.open(png_path) as image:
        if image.size != (width, height):
            raise ValueError("The map image and tile index bounds do not match.")
        texture = image.convert("RGBA")
        alpha = texture.getchannel("A")
        for path, strength in layers:
            with Image.open(path) as layer:
                if layer.size != texture.size:
                    raise ValueError(f"{path.name} dimensions do not match the map image.")
                overlay = layer.convert("RGBA")
                # Transparent overlay pixels must leave the biome color unchanged.
                lighting = Image.new("RGBA", texture.size, "white")
                lighting.alpha_composite(overlay)
            lighting = Image.blend(Image.new("RGB", texture.size, "white"),
                                   lighting.convert("RGB"), strength)
            texture = ImageChops.multiply(texture.convert("RGB"), lighting).convert("RGBA")
        texture.putalpha(alpha)
        texture.thumbnail((TEXTURE_LIMIT, TEXTURE_LIMIT), Image.Resampling.NEAREST)

    if timestamps != tuple(path.stat().st_mtime_ns for path in files):
        raise ValueError("The map changed during export. Retry once the render is complete.")
    return texture, (min_x * 4, 0, min_z * 4), (width * 4, height * 4)


def write_metadata(pack, version, description):
    pack.writestr("pack.mcmeta", json.dumps({"pack": {
        "min_format": version, "max_format": version, "description": description
    }}))


def read_detail(path, origin, world_size):
    if path is None:
        return Image.new("RGBA", (1, 1)), (0, 0), (0, 0)
    if __package__:
        from .compare_surface import load_surface, render, sample_surface
        from .extract_surface import material_color
    else:
        from compare_surface import load_surface, render, sample_surface
        from extract_surface import material_color
    before = path.stat()
    surface = load_surface(path)
    if surface.size > TEXTURE_LIMIT:
        raise ValueError("Surface detail must fit without reducing its one-block resolution")
    offset = (surface.origin_x - origin[0], surface.origin_z - origin[2])
    if any(start < 0 or start + surface.size > extent
           for start, extent in zip(offset, world_size)):
        raise ValueError("Surface detail must lie inside the full map bounds")
    _, texture = render(sample_surface(surface, 1))
    unknown = {i for i, (name, _) in enumerate(surface.palette) if material_color(name) is None}
    for i, state in enumerate(surface.states):
        if state in unknown:
            # Production packs retain the overview instead of diagnostic magenta.
            texture.putpixel((i % surface.size, i // surface.size), (0, 0, 0, 0))
    after = path.stat()
    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError("Surface detail changed during export")
    return texture, offset, (surface.size, surface.size)


def read_world_tiles(directory):
    path = directory / "world-map.json"
    before = path.read_bytes()
    world = json.loads(before)
    if (world.get("format"), world.get("version"), world.get("blocks_per_pixel")) != (
            "vanilla-map-world", 1, 1):
        raise ValueError("Expected a version-one, one-block world map")
    width, height = world["world_size"]
    tile_size = world["tile_size"]
    if not all(isinstance(v, int) and v > 0 for v in (width, height, tile_size)) or tile_size > 4096:
        raise ValueError("Invalid world or tile dimensions")
    grid = [math.ceil(width / tile_size), math.ceil(height / tile_size)]
    count = grid[0] * grid[1]
    if world["grid"] != grid or not 1 <= count <= 15 or len(world["tiles"]) != count:
        raise ValueError("World map must contain a complete grid of at most 15 tiles")
    for i, tile in enumerate(world["tiles"]):
        tx, tz = i % grid[0], i // grid[0]
        expected = [min(tile_size, width - tx * tile_size), min(tile_size, height - tz * tile_size)]
        if (tile["cell"] != [tx, tz] or tile["size"] != expected
                or tile["file"] != f"tile-{tx}-{tz}.png"):
            raise ValueError("Tile coordinates, dimensions or filename do not match the grid")
        payload = (directory / tile["file"]).read_bytes()
        if hashlib.sha256(payload).hexdigest() != tile["sha256"]:
            raise ValueError("World tile checksum does not match its completed generation")
        with Image.open(BytesIO(payload)) as image:
            if image.size != tuple(expected) or image.mode != "RGBA":
                raise ValueError("World tile must preserve its one-block RGBA dimensions")
    if path.read_bytes() != before:
        raise ValueError("World manifest changed during export")
    return world


def world_shader(count):
    """Choose one sampler through a balanced tree, avoiding a scan of all tiles."""
    def dispatch(start, end, indent="    "):
        if end - start == 1:
            return indent + f"return texelFetch(Tile{start}Sampler, pixel, 0);"
        middle = (start + end) // 2
        return (indent + f"if (index < {middle}) {{\n" + dispatch(start, middle, indent + "    ")
                + "\n" + indent + "} else {\n" + dispatch(middle, end, indent + "    ")
                + "\n" + indent + "}")
    if not 1 <= count <= 15:
        raise ValueError("World shader supports one to fifteen tiles")
    source = (PACK_ROOT / "world_map.fsh").read_text()
    return (source.replace("// TILE_SAMPLERS", "\n".join(
                f"uniform sampler2D Tile{i}Sampler;" for i in range(count)))
            .replace("// TILE_SIZES", "\n    ".join(f"vec2 Tile{i}Size;" for i in range(count)))
            .replace("// TILE_FETCH", dispatch(0, count).lstrip()))


def build(render_dir, output, view_height, style="relief", surface_path=None, world_tiles=None):
    if surface_path is not None and world_tiles is not None:
        raise ValueError("Choose either a surface detail or a full world map")
    world = read_world_tiles(world_tiles) if world_tiles is not None else None
    if world is None:
        texture, origin, world_size = read_render(render_dir, style)
        detail, detail_offset, detail_size = read_detail(surface_path, origin, world_size)
    else:
        origin = (world["origin"][0], 0, world["origin"][1])
        world_size = world["world_size"]
    pan_units = max(1, math.ceil(max(world_size) * 16 / PAN_CENTER))
    pan_step = pan_units / 16
    pan_sensitivity = max(1, min(32767, round(view_height / (128 * pan_step))))
    png = BytesIO()
    detail_png = BytesIO()
    if world is None:
        texture.save(png, format="PNG", optimize=True)
        detail.save(detail_png, format="PNG", optimize=True)
    map_pass = {
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": f"{NAMESPACE}:post/" + ("world_map" if world is not None else "map"),
        "inputs": [{"sampler_name": "State", "target": "next_state"}],
        "output": "swap",
    }
    if world is None:
        map_pass["inputs"].extend([
            {"sampler_name": "Map", "location": f"{NAMESPACE}:map",
             "width": texture.width, "height": texture.height},
            {"sampler_name": "Detail", "location": f"{NAMESPACE}:detail",
             "width": detail.width, "height": detail.height}])
    else:
        map_pass["inputs"].extend([
            {"sampler_name": f"Tile{i}", "location": f"{NAMESPACE}:world/{i}",
             "width": tile["size"][0], "height": tile["size"][1]}
            for i, tile in enumerate(world["tiles"])])
    blit_pass = {
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": "minecraft:post/blit",
        "inputs": [{"sampler_name": "In", "target": "swap"}],
        "uniforms": {"BlitConfig": [
            {"name": "ColorModulate", "type": "vec4", "value": [1, 1, 1, 1]},
        ]},
        "output": "minecraft:main",
    }
    assets = f"assets/{NAMESPACE}"
    state_pass = {
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": f"{NAMESPACE}:post/navigation",
        "inputs": [
            {"sampler_name": "Main", "target": "minecraft:main"},
            {"sampler_name": "Previous", "target": "history"},
        ],
        "output": "next_state",
    }
    save_state = dict(blit_pass, inputs=[{"sampler_name": "In", "target": "next_state"}], output="history")
    with ZipFile(output / "vanilla-map-post-resources.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [97, 1], "VanillaOnlineMapMC fullscreen map effect")
        for name, span in (
            ("map_far", view_height * 4),
            ("map", view_height * 2),
            ("map_near", view_height),
            ("map_close", view_height / 2),
        ):
            config = [
                {"name": "MapOrigin", "type": "ivec3", "value": origin},
                {"name": "ViewHeight", "type": "float", "value": span},
                {"name": "MapWorldSize", "type": "vec2", "value": world_size},
                {"name": "PanStep", "type": "float", "value": pan_step},
            ]
            if world is None:
                config.extend([
                    {"name": "DetailOffset", "type": "vec2", "value": detail_offset},
                    {"name": "DetailWorldSize", "type": "vec2", "value": detail_size}])
            else:
                config.extend([
                    {"name": "TileSize", "type": "int", "value": world["tile_size"]},
                    {"name": "TilesX", "type": "int", "value": world["grid"][0]}])
            render = dict(map_pass, uniforms={"MapConfig": config})
            effect = {
                "targets": {
                    "swap": {},
                    "history": {"width": 2, "height": 1, "persistent": True},
                    "next_state": {"width": 2, "height": 1},
                },
                "passes": [state_pass, render, blit_pass, save_state],
            }
            pack.writestr(f"{assets}/post_effect/{name}.json", json.dumps(effect))

        for pixel in range(8):
            for value in range(16):
                signal = {"passes": [{
                    "vertex_shader": f"{NAMESPACE}:post/pan_signal",
                    "fragment_shader": f"{NAMESPACE}:post/pan_signal",
                    "output": "minecraft:main",
                    "uniforms": {"PanSignal": [
                        {"name": "Signal", "type": "vec2", "value": [pixel, value]},
                    ]},
                }]}
                pack.writestr(f"{assets}/post_effect/pan/{pixel}_{value}.json", json.dumps(signal))

        if world is None:
            pack.writestr(f"{assets}/textures/effect/map.png", png.getvalue())
            pack.writestr(f"{assets}/textures/effect/detail.png", detail_png.getvalue())
            pack.write(PACK_ROOT / "map.fsh", f"{assets}/shaders/post/map.fsh")
        else:
            for i, tile in enumerate(world["tiles"]):
                payload = (world_tiles / tile["file"]).read_bytes()
                if hashlib.sha256(payload).hexdigest() != tile["sha256"]:
                    raise ValueError("World tile changed during export")
                pack.writestr(f"{assets}/textures/effect/world/{i}.png", payload)
            pack.writestr(f"{assets}/shaders/post/world_map.fsh", world_shader(len(world["tiles"])))
        for shader in ("navigation.fsh", "pan_signal.vsh", "pan_signal.fsh"):
            pack.write(PACK_ROOT / shader, f"{assets}/shaders/post/{shader}")

    datapack = PACK_ROOT / "datapack"
    with ZipFile(output / "vanilla-map-post-datapack.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [121, 0], "VanillaOnlineMapMC map effect controls")
        for file in sorted(datapack.rglob("*")):
            if file.is_file():
                pack.write(file, file.relative_to(datapack).as_posix())
        pack.writestr(
            f"data/{NAMESPACE}/function/pan_config.mcfunction",
            f"scoreboard players set #sensitivity vmp_pan {pan_sensitivity}\n"
            f"scoreboard players set #pan_units vmp_pan {pan_units}\n",
        )
        limits = []
        for index, axis in ((0, "x"), (2, "z")):
            extent = world_size[index // 2] * 16
            shift_operation = "remove" if origin[index] >= 0 else "add"
            limits.extend([
                f"execute store result score @s vmp_word run data get entity @s Pos[{index}] 16",
                f"scoreboard players {shift_operation} @s vmp_word {abs(origin[index] * 16)}",
                "execute if score @s vmp_word matches ..-1 run scoreboard players set @s vmp_word 0",
                f"execute if score @s vmp_word matches {extent + 1}.. run scoreboard players set @s vmp_word {extent}",
                "scoreboard players operation @s vmp_word /= #pan_units vmp_pan",
                "scoreboard players operation @s vmp_word *= #pan_step vmp_pan",
                f"scoreboard players set @s vmp_digit {PAN_CENTER * 100}",
                "scoreboard players operation @s vmp_digit -= @s vmp_word",
                f"execute if score @s vmp_{axis} < @s vmp_digit run scoreboard players operation @s vmp_{axis} = @s vmp_digit",
                f"scoreboard players add @s vmp_digit {math.ceil(extent / pan_units) * 100}",
                f"execute if score @s vmp_{axis} > @s vmp_digit run scoreboard players operation @s vmp_{axis} = @s vmp_digit",
            ])
        pack.writestr(f"data/{NAMESPACE}/function/limit_pan.mcfunction", "\n".join(limits) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, default=ROOT / "backend" / "map_images")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--view-height", type=int, default=1024,
                        help="Initial vertical map span; closest level shows half this height")
    parser.add_argument("--style", choices=("relief", "biomes"), default="relief",
                        help="Terrain shading (default) or plain biome colors")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--surface", type=Path,
                        help="Optional surface.zip: one-block material/hillshade detail over the full map")
    source.add_argument("--world-tiles", type=Path,
                        help="Completed world-map.json directory: full one-block tiled map")
    args = parser.parse_args()
    if not 1 <= args.view_height <= 60_000_000:
        parser.error("--view-height must be between 1 and 60000000 blocks")

    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output) as temporary:
        staging = Path(temporary)
        build(args.render_dir, staging, args.view_height, args.style, args.surface, args.world_tiles)
        for pack in sorted(staging.glob("*.zip")):
            destination = args.output / pack.name
            pack.replace(destination)
            print(destination)


if __name__ == "__main__":
    main()
