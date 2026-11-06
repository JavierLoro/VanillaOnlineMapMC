"""
mc-chunk-map — backend/main.py
FastAPI que lee archivos .mca del mundo Minecraft y expone:
  GET /api/chunks  → lista de tiles 4×4 bloques con bioma, color y datos de relieve
  GET /api/stats   → estadísticas del mundo
  GET /            → sirve el frontend

Caché persistente por chunk: cada chunk procesado se guarda en disco.
Cuando un .mca cambia de mtime, solo se parsean los chunks nuevos que
aún no estaban en el caché — los ya conocidos se reusan directamente.
Datos derivados (shade, hillshade, isolines) se recomputan en memoria
tras cada cambio y no se persisten.
"""

import os, struct, zlib, math, time, json, logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

WORLD_PATH  = Path(os.getenv("WORLD_PATH", "/opt/minecraft/world"))
CACHE_TTL   = int(os.getenv("CACHE_TTL", "120"))
LOG_LEVEL   = os.getenv("LOG_LEVEL", "info").upper()
CACHE_FILE  = Path(__file__).parent / "chunk_cache.json"
MAP_PNG_DIR = Path(__file__).parent / "map_images"

ACTIVE_ZONE_RADIUS   = int(os.getenv("ACTIVE_ZONE_RADIUS",   "32"))
ACTIVE_ZONE_TTL      = int(os.getenv("ACTIVE_ZONE_TTL",    "3600"))
ACTIVE_ZONE_CENTER_X = int(os.getenv("ACTIVE_ZONE_CENTER_X",    "0"))
ACTIVE_ZONE_CENTER_Z = int(os.getenv("ACTIVE_ZONE_CENTER_Z",    "0"))

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
log = logging.getLogger("mc-chunk-map")

if __package__:
    from .map_colors import BIOME_COLORS, DEFAULT_COLOR, CAVE_BIOMES, BLOCK_COLORS
    from .world_reader import (_rv, _T_COMP, _unpack_heightmap,
                               _unpack_biome_indices, _top_block_4x4)
else:
    from map_colors import BIOME_COLORS, DEFAULT_COLOR, CAVE_BIOMES, BLOCK_COLORS
    from world_reader import (_rv, _T_COMP, _unpack_heightmap,
                              _unpack_biome_indices, _top_block_4x4)

def _surface_biomes_4x4(sections: list) -> dict:
    surface: dict = {}
    for sec in sorted(sections, key=lambda s: s.get("Y", 0), reverse=True):
        biomes_tag = sec.get("biomes")
        if not biomes_tag: continue
        palette = biomes_tag.get("palette", [])
        data    = biomes_tag.get("data", [])
        if not palette: continue

        if len(palette) == 1:
            biome = palette[0]
            if biome not in CAVE_BIOMES:
                for x4 in range(4):
                    for z4 in range(4):
                        surface.setdefault((x4, z4), biome)
        else:
            indices = _unpack_biome_indices(data, len(palette))
            for y4 in range(3, -1, -1):
                for z4 in range(4):
                    for x4 in range(4):
                        if (x4, z4) in surface: continue
                        idx = y4*16 + z4*4 + x4
                        if idx < len(indices):
                            pi    = indices[idx]
                            biome = palette[pi] if pi < len(palette) else "unknown"
                            if biome not in CAVE_BIOMES:
                                surface[(x4, z4)] = biome
    return surface


def update_region_chunks(mca_path: Path, existing: dict) -> tuple[dict, int]:
    """
    Lee mca_path y devuelve (chunks_actualizados, nuevos_añadidos).
    existing: {"cx,cz": [tiles]} — chunks ya conocidos, se reusan sin parsear.
    """
    parts = mca_path.stem.split(".")
    try:    rx, rz = int(parts[1]), int(parts[2])
    except: log.warning(f"Nombre inválido: {mca_path.name}"); return existing, 0

    try:    data = mca_path.read_bytes()
    except OSError as e: log.error(f"No se puede leer {mca_path}: {e}"); return existing, 0

    if len(data) < 8192: return existing, 0

    chunks = dict(existing)
    added  = 0

    for local_cz in range(32):
        for local_cx in range(32):
            key = f"{local_cx},{local_cz}"
            if key in chunks:
                continue  # bioma inmutable, ya lo tenemos

            header_idx = 4 * (local_cx + local_cz * 32)
            raw        = struct.unpack_from(">I", data, header_idx)[0]
            offset_sec = raw >> 8
            sector_cnt = raw & 0xFF
            if offset_sec == 0 or sector_cnt == 0:
                continue  # chunk no generado todavía

            bo = offset_sec * 4096
            if bo + 5 > len(data): continue

            cl          = struct.unpack_from(">I", data, bo)[0]
            compression = data[bo + 4]
            compressed  = data[bo + 5 : bo + 4 + cl]

            try:
                if   compression == 2: nbt_data = zlib.decompress(compressed)
                elif compression == 1:
                    import gzip; nbt_data = gzip.decompress(compressed)
                else: nbt_data = compressed
            except Exception: continue

            try:
                root, _ = _rv(nbt_data, 3, _T_COMP)
            except Exception: continue

            if root.get("Status") != "minecraft:full": continue

            it       = root.get("InhabitedTime", 0)
            grid     = _surface_biomes_4x4(root.get("sections", []))
            base_bx4 = (rx * 32 + local_cx) * 4
            base_bz4 = (rz * 32 + local_cz) * 4

            hm      = root.get("Heightmaps", {})
            ws_grid = _unpack_heightmap(hm.get("WORLD_SURFACE", []))
            of_grid = _unpack_heightmap(hm.get("OCEAN_FLOOR", []))

            cx_abs    = rx * 32 + local_cx
            cz_abs    = rz * 32 + local_cz
            cx_center = ACTIVE_ZONE_CENTER_X // 16
            cz_center = ACTIVE_ZONE_CENTER_Z // 16
            in_zone   = (abs(cx_abs - cx_center) <= ACTIVE_ZONE_RADIUS and
                         abs(cz_abs - cz_center) <= ACTIVE_ZONE_RADIUS)
            sections  = root.get("sections", [])
            top_blocks = _top_block_4x4(sections, ws_grid) if in_zone else {}

            tiles = []
            for (x4, z4), biome in grid.items():
                ws_vals = [ws_grid[(z4*4+dz)*16 + x4*4+dx] for dz in range(4) for dx in range(4)]
                of_vals = [of_grid[(z4*4+dz)*16 + x4*4+dx] for dz in range(4) for dx in range(4)]
                tiles.append({
                    "bx4":      base_bx4 + x4,
                    "bz4":      base_bz4 + z4,
                    "biome":    biome,
                    "color":    BIOME_COLORS.get(biome, DEFAULT_COLOR),
                    "ws":       round(sum(ws_vals) / 16, 1),
                    "of":       round(sum(of_vals) / 16, 1),
                    "it":       it,
                    "top_block": top_blocks.get((x4, z4)),
                })

            if tiles:
                chunks[key] = tiles
                added += 1

    return chunks, added

# ── Caché persistente por chunk ───────────────────────────────────────────────
# Disco: {"regions": {"ruta": {"mtime": float, "chunks": {"cx,cz": [tiles]}}}}

_cache: dict = {
    "regions":             {},
    "all_tiles":           None,
    "stats":               None,
    "last_check":          0.0,
    "last_active_refresh": 0.0,
    "world_seed":          None,
    "png_bounds":          None,
}

def _load_disk_cache() -> None:
    if not CACHE_FILE.exists(): return
    try:
        data = json.loads(CACHE_FILE.read_text())
        _cache["regions"]    = data.get("regions", {})
        _cache["world_seed"] = data.get("world_seed")
        # Invalidate cache if it predates height or activity fields
        sample = next(
            (tiles[0] for entry in _cache["regions"].values()
             for tiles in entry["chunks"].values() if tiles),
            None
        )
        if sample is not None and ("ws" not in sample or "it" not in sample):
            log.info("Caché sin datos de altura/actividad detectado — regenerando desde cero")
            _cache["regions"]    = {}
            _cache["world_seed"] = None
            return
        total = sum(len(r["chunks"]) for r in _cache["regions"].values())
        log.info(f"Caché cargado: {len(_cache['regions'])} regiones, {total} chunks desde {CACHE_FILE}")
    except Exception as e:
        log.warning(f"No se pudo cargar el caché del disco: {e}")

def _save_disk_cache() -> None:
    try:
        tmp = CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(
            {"regions": _cache["regions"], "world_seed": _cache["world_seed"]},
            separators=(",", ":"),
        ))
        tmp.replace(CACHE_FILE)
        total = sum(len(r["chunks"]) for r in _cache["regions"].values())
        log.info(f"Caché guardado: {len(_cache['regions'])} regiones, {total} chunks → {CACHE_FILE}")
    except Exception as e:
        log.error(f"Error guardando caché: {e}")


def _read_world_seed() -> int | None:
    """Lee el seed del mundo desde world_gen_settings.dat (1.21+).
    Fallback a level.dat para formatos anteriores."""
    import gzip as _gzip
    world_root = WORLD_PATH.parents[2]

    # 1.21+: world_gen_settings.dat contiene el seed estable
    wgs_path = world_root / "data" / "minecraft" / "world_gen_settings.dat"
    if wgs_path.exists():
        try:
            with _gzip.open(wgs_path, "rb") as f:
                raw = f.read()
            root, _ = _rv(raw, 3, _T_COMP)
            seed = root.get("data", {}).get("seed")
            if seed is not None:
                return int(seed)
        except Exception as e:
            log.warning(f"No se pudo leer seed de world_gen_settings.dat: {e}")

    # Fallback: level.dat (1.16–1.20)
    level_dat = world_root / "level.dat"
    if not level_dat.exists():
        log.warning(f"No se encontró world_gen_settings.dat ni level.dat en {world_root}")
        return None
    try:
        with _gzip.open(level_dat, "rb") as f:
            raw = f.read()
        root, _ = _rv(raw, 3, _T_COMP)
        data_tag = root.get("Data", {})
        seed = data_tag.get("WorldGenSettings", {}).get("seed")
        if seed is None:
            seed = data_tag.get("RandomSeed")
        return int(seed) if seed is not None else None
    except Exception as e:
        log.warning(f"No se pudo leer seed de level.dat: {e}")
        return None

def _compute_derived_layers(raw_tiles: list) -> dict:
    """Compute shade, hillshade, isoline and it_opacity for each tile from stored ws/it values.
    Returns dict (bx4, bz4) → {shade, hillshade, isoline, it_opacity}.
    Not persisted — recomputed after every cache change."""
    if not raw_tiles:
        return {}

    it_max = max((t.get("it", 0) for t in raw_tiles), default=0) or 1

    H = {(t["bx4"], t["bz4"]): t.get("ws", 0.0) for t in raw_tiles}
    ws_vals = list(H.values())
    ws_min, ws_max = min(ws_vals), max(ws_vals)
    ws_range = (ws_max - ws_min) or 1.0

    inv_sqrt3 = 1.0 / math.sqrt(3)
    lx = ly = lz = inv_sqrt3  # NW light direction (normalized)

    derived = {}
    for t in raw_tiles:
        bx4, bz4 = t["bx4"], t["bz4"]
        ws = H[(bx4, bz4)]

        # Topographic shade: valleys darker, peaks brighter
        shade = 0.55 + 0.45 * (ws - ws_min) / ws_range

        # Hillshading: approximate surface normal from neighbor heights
        h_e = H.get((bx4 + 1, bz4), ws)
        h_w = H.get((bx4 - 1, bz4), ws)
        h_s = H.get((bx4, bz4 + 1), ws)
        h_n = H.get((bx4, bz4 - 1), ws)
        dx = (h_e - h_w) / 2.0
        dz = (h_s - h_n) / 2.0
        nx, ny, nz = -dx, 1.0, -dz
        mag = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
        nx /= mag; ny /= mag; nz /= mag
        hillshade = max(0.3, min(1.0, nx*lx + ny*ly + nz*lz))

        # Isoline: height jump > 20 blocks with any cardinal neighbor
        isoline = any(
            abs(ws - H[nb]) > 20
            for nb in ((bx4+1, bz4), (bx4-1, bz4), (bx4, bz4+1), (bx4, bz4-1))
            if nb in H
        )

        # Activity overlay: logarithmic opacity relative to most-visited chunk
        it = t.get("it", 0)
        it_opacity = round(min(0.75, math.log1p(it) / math.log1p(it_max) * 0.75), 4) if it > 0 else 0.0

        derived[(bx4, bz4)] = {
            "shade":      round(shade, 4),
            "hillshade":  round(hillshade, 4),
            "isoline":    isoline,
            "it_opacity": it_opacity,
        }

    return derived


def _render_pngs(all_tiles: list) -> None:
    try:
        from PIL import Image
    except ImportError:
        log.warning("Pillow no instalado — omitiendo generación de PNG")
        return
    if not all_tiles:
        return

    bx4_min = min(t["bx4"] for t in all_tiles)
    bz4_min = min(t["bz4"] for t in all_tiles)
    bx4_max = max(t["bx4"] for t in all_tiles)
    bz4_max = max(t["bz4"] for t in all_tiles)
    w = bx4_max - bx4_min + 1
    h = bz4_max - bz4_min + 1

    base_img      = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shade_img     = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hillshade_img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    isolines_img  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    blocks_img    = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    base_px      = base_img.load()
    shade_px     = shade_img.load()
    hillshade_px = hillshade_img.load()
    isolines_px  = isolines_img.load()
    blocks_px    = blocks_img.load()

    for t in all_tiles:
        x = t["bx4"] - bx4_min
        y = t["bz4"] - bz4_min
        hc = t["color"].lstrip("#")
        r, g, b = int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)
        base_px[x, y]      = (r, g, b, 255)
        sv = int(t.get("shade", 1.0) * 255)
        shade_px[x, y]     = (sv, sv, sv, 255)
        hv = int(t.get("hillshade", 1.0) * 255)
        hillshade_px[x, y] = (hv, hv, hv, 255)
        if t.get("isoline"):
            isolines_px[x, y] = (0, 0, 0, 160)
        block_hex = BLOCK_COLORS.get(t.get("top_block") or "")
        if block_hex:
            br = int(block_hex[1:3], 16)
            bg = int(block_hex[3:5], 16)
            bb = int(block_hex[5:7], 16)
            blocks_px[x, y] = (br, bg, bb, 220)

    MAP_PNG_DIR.mkdir(exist_ok=True)
    base_img.save(MAP_PNG_DIR / "map_base.png",          optimize=True)
    shade_img.save(MAP_PNG_DIR / "map_shade.png",         optimize=True)
    hillshade_img.save(MAP_PNG_DIR / "map_hillshade.png", optimize=True)
    isolines_img.save(MAP_PNG_DIR / "map_isolines.png",   optimize=True)
    blocks_img.save(MAP_PNG_DIR / "map_blocks.png",       optimize=True)

    _cache["png_bounds"] = {
        "bx4_min": bx4_min, "bx4_max": bx4_max,
        "bz4_min": bz4_min, "bz4_max": bz4_max,
    }
    import gzip as _gz
    biomes = list({t["biome"] for t in all_tiles})
    b2i    = {b: i for i, b in enumerate(biomes)}
    blocks = list({t.get("top_block") or "null" for t in all_tiles})
    blk2i  = {b: i for i, b in enumerate(blocks)}
    ti_data = {
        "bounds":        {"bx4_min": bx4_min, "bx4_max": bx4_max, "bz4_min": bz4_min, "bz4_max": bz4_max},
        "palette":       [{"name": b, "color": BIOME_COLORS.get(b, "#888888")} for b in biomes],
        "block_palette": blocks,
        "tiles":         [[t["bx4"], t["bz4"], b2i[t["biome"]], int(t.get("ws", 0)),
                           blk2i[t.get("top_block") or "null"]] for t in all_tiles],
    }
    with _gz.open(MAP_PNG_DIR / "tile_index.json.gz", "wb") as f:
        f.write(json.dumps(ti_data).encode())
    log.info(f"PNGs generados: {w}×{h} px, {len(all_tiles)} tiles")

def _rebuild_all_tiles() -> None:
    raw_tiles: list[dict] = []
    for entry in _cache["regions"].values():
        for tiles in entry["chunks"].values():
            raw_tiles.extend(tiles)

    derived = _compute_derived_layers(raw_tiles)
    all_tiles = [{**t, **derived.get((t["bx4"], t["bz4"]), {})} for t in raw_tiles]
    _cache["all_tiles"] = all_tiles

    biome_count: dict[str, int] = {}
    ws_list: list[float] = []
    isoline_count = 0
    for t in all_tiles:
        biome_count[t["biome"]] = biome_count.get(t["biome"], 0) + 1
        if "ws" in t:
            ws_list.append(t["ws"])
        if t.get("isoline"):
            isoline_count += 1

    inhabited = sum(1 for t in all_tiles[::16] if t.get("it", 0) > 0)
    max_it    = int(max((t.get("it", 0) for t in all_tiles), default=0))

    total_chunks = sum(len(r["chunks"]) for r in _cache["regions"].values())
    _cache["stats"] = {
        "total_tiles":        len(all_tiles),
        "total_full_chunks":  total_chunks,
        "total_regions":      len(_cache["regions"]),
        "biome_distribution": dict(sorted(biome_count.items(), key=lambda x: x[1], reverse=True)),
        "height_range":       {"min": int(min(ws_list, default=0)), "max": int(max(ws_list, default=0))},
        "isoline_tiles":      isoline_count,
        "inhabited_chunks":   inhabited,
        "max_inhabited_ticks": max_it,
        "active_zone": {
            "center_x":      ACTIVE_ZONE_CENTER_X,
            "center_z":      ACTIVE_ZONE_CENTER_Z,
            "radius_chunks": ACTIVE_ZONE_RADIUS,
            "radius_blocks": ACTIVE_ZONE_RADIUS * 16,
            "ttl_seconds":   ACTIVE_ZONE_TTL,
            "last_refresh":  _cache["last_active_refresh"],
        },
        "world_path":         str(WORLD_PATH),
        "cache_ttl":          CACHE_TTL,
        "last_scan":          time.time(),
    }
    _render_pngs(all_tiles)

def _invalidate_active_zone() -> None:
    cx_center = ACTIVE_ZONE_CENTER_X // 16
    cz_center = ACTIVE_ZONE_CENTER_Z // 16
    invalidated = 0
    for region_key, entry in _cache["regions"].items():
        parts = Path(region_key).stem.split(".")
        try:    rx, rz = int(parts[1]), int(parts[2])
        except: continue
        to_remove = [
            k for k in entry["chunks"]
            if (abs(rx*32 + int(k.split(",")[0]) - cx_center) <= ACTIVE_ZONE_RADIUS and
                abs(rz*32 + int(k.split(",")[1]) - cz_center) <= ACTIVE_ZONE_RADIUS)
        ]
        for k in to_remove:
            del entry["chunks"][k]
        if to_remove:
            entry["mtime"] = 0  # fuerza re-parse de la región
            invalidated += len(to_remove)
    _cache["last_active_refresh"] = time.time()
    log.info(f"Zona activa: {invalidated} chunks invalidados para re-scan (centro chunk {cx_center},{cz_center}, radio {ACTIVE_ZONE_RADIUS})")

def get_chunks_cached() -> list[dict]:
    now = time.time()

    if (now - _cache["last_active_refresh"]) >= ACTIVE_ZONE_TTL:
        _invalidate_active_zone()

    if _cache["all_tiles"] is not None and (now - _cache["last_check"]) < CACHE_TTL:
        return _cache["all_tiles"]

    region_dir = WORLD_PATH / "region"
    if not region_dir.exists():
        log.warning(f"Directorio región no encontrado: {region_dir}")
        return _cache["all_tiles"] or []

    mca_files = {str(p): p for p in region_dir.glob("r.*.*.mca")}
    changed = False

    for key in list(_cache["regions"].keys()):
        if key not in mca_files:
            log.info(f"Región eliminada: {Path(key).name}")
            del _cache["regions"][key]
            changed = True

    # Collect regions that need reparsing
    pending = []
    for key, mca_path in mca_files.items():
        try:    current_mtime = mca_path.stat().st_mtime
        except OSError: continue
        cached = _cache["regions"].get(key)
        if cached and cached["mtime"] == current_mtime:
            continue
        pending.append((key, mca_path, current_mtime, cached["chunks"] if cached else {}))

    if pending:
        def _parse_region(args):
            key, mca_path, mtime, existing = args
            chunks, added = update_region_chunks(mca_path, existing)
            return key, mtime, chunks, added

        workers = min(2, len(pending))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_parse_region, args) for args in pending]
            for fut in as_completed(futures):
                key, mtime, chunks, added = fut.result()
                cached = _cache["regions"].get(key)
                if added > 0 or not cached:
                    log.info(f"{Path(key).name}: {added} chunks nuevos (total región: {len(chunks)})")
                    _cache["regions"][key] = {"mtime": mtime, "chunks": chunks}
                    changed = True
                else:
                    _cache["regions"][key]["mtime"] = mtime

    _cache["last_check"] = now

    if changed or _cache["all_tiles"] is None:
        _rebuild_all_tiles()
        _save_disk_cache()

    return _cache["all_tiles"]

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Minecraft Chunk Map", version="4.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=1000)

frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

@app.on_event("startup")
def on_startup():
    _load_disk_cache()
    # Migración: re-parsear chunks de zona activa sin top_block
    _mig_cx = ACTIVE_ZONE_CENTER_X // 16
    _mig_cz = ACTIVE_ZONE_CENTER_Z // 16
    _mig_removed = 0
    for _rkey, _region in _cache["regions"].items():
        _parts = Path(_rkey).stem.split(".")
        try: _rx, _rz = int(_parts[1]), int(_parts[2])
        except: continue
        _to_remove = [
            k for k, tiles in _region["chunks"].items()
            if tiles and "top_block" not in tiles[0]
               and abs(_rx*32 + int(k.split(",")[0]) - _mig_cx) <= ACTIVE_ZONE_RADIUS
               and abs(_rz*32 + int(k.split(",")[1]) - _mig_cz) <= ACTIVE_ZONE_RADIUS
        ]
        if _to_remove:
            for k in _to_remove: del _region["chunks"][k]
            _region["mtime"] = 0  # force re-parse of this region on next get_chunks_cached()
        _mig_removed += len(_to_remove)
    if _mig_removed:
        log.info(f"Migración top_block: {_mig_removed} chunks de zona activa pendientes de re-parseo")
    if _cache["regions"]:
        if _mig_removed:
            # Re-parse missing chunks during startup (last_check=0 triggers full scan)
            get_chunks_cached()
        else:
            _rebuild_all_tiles()
            _cache["last_check"] = time.time()
        total = sum(len(r["chunks"]) for r in _cache["regions"].values())
        log.info(f"Arrancado con {total} chunks desde caché persistente")
    if _cache["world_seed"] is None:
        seed = _read_world_seed()
        if seed is not None:
            _cache["world_seed"] = seed
            _save_disk_cache()
            log.info(f"Seed del mundo registrado: {seed}")

@app.get("/", include_in_schema=False)
def serve_frontend():
    index = frontend_dir / "index.html"
    if index.exists(): return FileResponse(str(index))
    return JSONResponse({"message": "Frontend no encontrado."})

@app.get("/api/chunks")
def api_chunks(
    biome:    Optional[str] = Query(None),
    bx4_min:  Optional[int] = Query(None),
    bx4_max:  Optional[int] = Query(None),
    bz4_min:  Optional[int] = Query(None),
    bz4_max:  Optional[int] = Query(None),
):
    tiles = get_chunks_cached()
    if biome:    tiles = [t for t in tiles if t["biome"] == biome]
    if bx4_min is not None: tiles = [t for t in tiles if t["bx4"] >= bx4_min]
    if bx4_max is not None: tiles = [t for t in tiles if t["bx4"] <= bx4_max]
    if bz4_min is not None: tiles = [t for t in tiles if t["bz4"] >= bz4_min]
    if bz4_max is not None: tiles = [t for t in tiles if t["bz4"] <= bz4_max]
    return {"count": len(tiles), "tiles": tiles}

@app.get("/api/stats")
def api_stats():
    if _cache["stats"] is None:
        get_chunks_cached()
    if _cache["stats"] is None:
        raise HTTPException(status_code=503, detail="Todavía procesando el mundo")
    result = dict(_cache["stats"])
    if _cache.get("png_bounds"):
        result["map_bounds"] = _cache["png_bounds"]
    return result


@app.get("/api/map.png")
def api_map_png(layer: str = Query("base")):
    if layer not in {"base", "shade", "hillshade", "isolines", "blocks"}:
        raise HTTPException(status_code=400, detail="layer inválido")
    path = MAP_PNG_DIR / f"map_{layer}.png"
    if not path.exists():
        raise HTTPException(status_code=503, detail="PNG no generado todavía")
    return FileResponse(str(path), media_type="image/png",
                        headers={"Cache-Control": "no-cache"})

@app.get("/api/tile-index")
def api_tile_index():
    path = MAP_PNG_DIR / "tile_index.json.gz"
    if not path.exists():
        get_chunks_cached()
        raise HTTPException(status_code=503, detail="tile-index no generado todavía")
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        headers={"Content-Encoding": "gzip", "Cache-Control": "no-cache"},
    )

@app.post("/api/refresh")
def api_refresh():
    """Fuerza comprobación de mtime en todos los archivos .mca."""
    _cache["last_check"] = 0.0
    get_chunks_cached()
    return {"ok": True, "total_chunks": sum(len(r["chunks"]) for r in _cache["regions"].values())}


@app.post("/api/reset-world")
def api_reset_world():
    """Comprueba el seed del level.dat. Si cambió respecto al registrado, limpia la caché completa."""
    current_seed = _read_world_seed()
    if current_seed is None:
        raise HTTPException(status_code=503, detail="No se pudo leer level.dat")

    stored_seed = _cache["world_seed"]
    if stored_seed is not None and stored_seed == current_seed:
        return {"reset": False, "seed": current_seed}

    log.info(f"Mundo nuevo detectado — seed {stored_seed} → {current_seed}. Limpiando caché.")
    _cache["regions"]    = {}
    _cache["all_tiles"]  = None
    _cache["stats"]      = None
    _cache["last_check"] = 0.0
    _cache["world_seed"] = current_seed
    _save_disk_cache()
    get_chunks_cached()
    return {"reset": True, "old_seed": stored_seed, "new_seed": current_seed}

@app.get("/api/biomes")
def api_biomes():
    return {"biomes": {k: v for k, v in BIOME_COLORS.items()}}

@app.get("/api/spawn")
def api_spawn():
    import gzip as _gzip
    world_root = WORLD_PATH.parents[2]
    level_dat  = world_root / "level.dat"
    if not level_dat.exists():
        raise HTTPException(status_code=404, detail=f"level.dat no encontrado en {world_root}")
    try:
        with _gzip.open(level_dat, "rb") as f:
            raw = f.read()
        root, _ = _rv(raw, 3, _T_COMP)
        spawn    = root.get("Data", {}).get("spawn", {})
        pos      = spawn.get("pos")
        if not isinstance(pos, list) or len(pos) < 3:
            raise ValueError(f"pos inesperado: {pos}")
        sx, sy, sz = pos[0], pos[1], pos[2]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error leyendo level.dat: {e}")
    return {
        "x": sx, "y": sy, "z": sz,
        "bx4": sx // 4, "bz4": sz // 4,
        "chunk_x": sx // 16, "chunk_z": sz // 16,
        "dimension": spawn.get("dimension", "minecraft:overworld"),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8200, reload=True, log_level="info")
