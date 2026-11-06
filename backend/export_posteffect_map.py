"""Build the Java 26.3 fullscreen map packs from a completed web render."""

import argparse
import gzip
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


def build(render_dir, output, view_height, style="relief"):
    texture, origin, world_size = read_render(render_dir, style)
    pan_units = max(1, math.ceil(max(world_size) * 16 / PAN_CENTER))
    pan_step = pan_units / 16
    pan_sensitivity = max(1, min(32767, round(view_height / (128 * pan_step))))
    png = BytesIO()
    texture.save(png, format="PNG", optimize=True)
    map_pass = {
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": f"{NAMESPACE}:post/map",
        "inputs": [
            {"sampler_name": "State", "target": "next_state"},
            {
                "sampler_name": "Map", "location": f"{NAMESPACE}:map",
                "width": texture.width, "height": texture.height,
            },
        ],
        "output": "swap",
    }
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
        ):
            render = dict(map_pass, uniforms={"MapConfig": [
                {"name": "MapOrigin", "type": "ivec3", "value": origin},
                {"name": "ViewHeight", "type": "float", "value": span},
                {"name": "MapWorldSize", "type": "vec2", "value": world_size},
                {"name": "PanStep", "type": "float", "value": pan_step},
            ]})
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

        pack.writestr(f"{assets}/textures/effect/map.png", png.getvalue())
        for shader in ("map.fsh", "navigation.fsh", "pan_signal.vsh", "pan_signal.fsh"):
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
    parser.add_argument("--view-height", type=int, default=1024, help="Initial and minimum vertical map span in blocks")
    parser.add_argument("--style", choices=("relief", "biomes"), default="relief",
                        help="Terrain shading (default) or plain biome colors")
    args = parser.parse_args()
    if not 1 <= args.view_height <= 60_000_000:
        parser.error("--view-height must be between 1 and 60000000 blocks")

    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output) as temporary:
        staging = Path(temporary)
        build(args.render_dir, staging, args.view_height, args.style)
        for pack in sorted(staging.glob("*.zip")):
            destination = args.output / pack.name
            pack.replace(destination)
            print(destination)


if __name__ == "__main__":
    main()
