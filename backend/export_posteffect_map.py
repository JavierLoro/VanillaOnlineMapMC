"""Build the Java 26.3 fullscreen map packs from a completed web render."""

import argparse
import gzip
import json
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = ROOT / "minecraft" / "posteffect"
NAMESPACE = "vanilla_map_post"
TEXTURE_LIMIT = 2048


def read_render(render_dir):
    png_path = render_dir / "map_base.png"
    index_path = render_dir / "tile_index.json.gz"
    files = (png_path, index_path)
    timestamps = tuple(path.stat().st_mtime_ns for path in files)
    if timestamps[1] < timestamps[0]:
        raise ValueError("The tile index predates the map image. Export from a completed render.")

    with gzip.open(index_path, "rt", encoding="utf-8") as index:
        bounds = json.load(index)["bounds"]
    min_x, min_z = bounds["bx4_min"], bounds["bz4_min"]
    width = bounds["bx4_max"] - min_x + 1
    height = bounds["bz4_max"] - min_z + 1
    with Image.open(png_path) as image:
        if image.size != (width, height):
            raise ValueError("The map image and tile index bounds do not match.")
        texture = image.convert("RGBA")
        texture.thumbnail((TEXTURE_LIMIT, TEXTURE_LIMIT), Image.Resampling.NEAREST)

    if timestamps != tuple(path.stat().st_mtime_ns for path in files):
        raise ValueError("The map changed during export. Retry once the render is complete.")
    return texture, (min_x * 4, 0, min_z * 4), (width * 4, height * 4)


def write_metadata(pack, version, description):
    pack.writestr("pack.mcmeta", json.dumps({"pack": {
        "min_format": version, "max_format": version, "description": description
    }}))


def build(render_dir, output, view_height):
    texture, origin, world_size = read_render(render_dir)
    png = BytesIO()
    texture.save(png, format="PNG", optimize=True)
    effect = {"passes": [{
        "vertex_shader": "minecraft:core/screenquad",
        "fragment_shader": f"{NAMESPACE}:post/map",
        "inputs": [{
            "sampler_name": "Map", "location": f"{NAMESPACE}:map",
            "width": texture.width, "height": texture.height,
        }],
        "output": "minecraft:main",
        "uniforms": {"MapConfig": [
            {"name": "MapOrigin", "type": "ivec3", "value": origin},
            {"name": "ViewHeight", "type": "float", "value": view_height},
            {"name": "MapWorldSize", "type": "vec2", "value": world_size},
        ]},
    }]}
    assets = f"assets/{NAMESPACE}"
    with ZipFile(output / "vanilla-map-post-resources.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [97, 1], "VanillaOnlineMapMC fullscreen map effect")
        pack.writestr(f"{assets}/post_effect/map.json", json.dumps(effect))
        pack.writestr(f"{assets}/textures/effect/map.png", png.getvalue())
        pack.write(PACK_ROOT / "map.fsh", f"{assets}/shaders/post/map.fsh")

    datapack = PACK_ROOT / "datapack"
    with ZipFile(output / "vanilla-map-post-datapack.zip", "w", ZIP_DEFLATED) as pack:
        write_metadata(pack, [121, 0], "VanillaOnlineMapMC map effect controls")
        for file in sorted(datapack.rglob("*")):
            if file.is_file():
                pack.write(file, file.relative_to(datapack).as_posix())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-dir", type=Path, default=ROOT / "backend" / "map_images")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--view-height", type=int, default=1024, help="Vertical map span in blocks")
    args = parser.parse_args()
    if not 1 <= args.view_height <= 60_000_000:
        parser.error("--view-height must be between 1 and 60000000 blocks")

    args.output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=args.output) as temporary:
        staging = Path(temporary)
        build(args.render_dir, staging, args.view_height)
        for pack in sorted(staging.glob("*.zip")):
            destination = args.output / pack.name
            pack.replace(destination)
            print(destination)


if __name__ == "__main__":
    main()
