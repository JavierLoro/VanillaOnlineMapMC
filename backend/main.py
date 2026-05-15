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

BIOME_COLORS: dict[str, str] = {
    "minecraft:ocean":               "#1a5fa8",
    "minecraft:deep_ocean":          "#0d3d6e",
    "minecraft:cold_ocean":          "#1d6b9e",
    "minecraft:deep_cold_ocean":     "#0f4d73",
    "minecraft:lukewarm_ocean":      "#2e86c1",
    "minecraft:deep_lukewarm_ocean": "#1f5f8b",
    "minecraft:warm_ocean":          "#4fa8d5",
    "minecraft:deep_dark":           "#1a0a2e",
    "minecraft:frozen_ocean":        "#8ab4cc",
    "minecraft:deep_frozen_ocean":   "#5a8ca6",
    "minecraft:river":               "#3a7ebf",
    "minecraft:frozen_river":        "#a8c8e0",
    "minecraft:swamp":               "#4c6741",
    "minecraft:mangrove_swamp":      "#3d5c2a",
    "minecraft:plains":              "#7cb87c",
    "minecraft:sunflower_plains":    "#a8d44c",
    "minecraft:meadow":              "#8fc45a",
    "minecraft:cherry_grove":        "#f4a7c3",
    "minecraft:forest":              "#2d6a2d",
    "minecraft:flower_forest":       "#4a9a4a",
    "minecraft:birch_forest":        "#4f7a3a",
    "minecraft:old_growth_birch_forest": "#5a8a40",
    "minecraft:dark_forest":         "#1a3d1a",
    "minecraft:jungle":              "#1a5e1a",
    "minecraft:sparse_jungle":       "#3a7a3a",
    "minecraft:bamboo_jungle":       "#2a6e2a",
    "minecraft:taiga":               "#3d6b52",
    "minecraft:snowy_taiga":         "#b0c8b0",
    "minecraft:old_growth_pine_taiga":   "#2d5040",
    "minecraft:old_growth_spruce_taiga": "#3a5e4a",
    "minecraft:snowy_plains":        "#d4e8d4",
    "minecraft:ice_spikes":          "#c8e8f0",
    "minecraft:snowy_slopes":        "#d8ecec",
    "minecraft:grove":               "#a8c8b8",
    "minecraft:frozen_peaks":        "#e8f4f4",
    "minecraft:jagged_peaks":        "#c8d8d8",
    "minecraft:desert":              "#d4a843",
    "minecraft:badlands":            "#c8622a",
    "minecraft:eroded_badlands":     "#d4743a",
    "minecraft:wooded_badlands":     "#a8522a",
    "minecraft:savanna":             "#c8b84a",
    "minecraft:savanna_plateau":     "#b8a83a",
    "minecraft:windswept_savanna":   "#d4c45a",
    "minecraft:stony_peaks":         "#9a9a8a",
    "minecraft:windswept_hills":     "#8a9a7a",
    "minecraft:windswept_gravelly_hills": "#9a9a8a",
    "minecraft:windswept_forest":    "#5a7a5a",
    "minecraft:stony_shore":         "#8a8a7a",
    "minecraft:beach":               "#d4c87a",
    "minecraft:snowy_beach":         "#d8e8d8",
    "minecraft:mushroom_fields":     "#9a4ab8",
    "minecraft:dripstone_caves":     "#7a6a5a",
    "minecraft:lush_caves":          "#4a8a4a",
    "minecraft:nether_wastes":       "#8a2020",
    "minecraft:crimson_forest":      "#9a1a30",
    "minecraft:warped_forest":       "#1a7a6a",
    "minecraft:soul_sand_valley":    "#4a3820",
    "minecraft:basalt_deltas":       "#3a3a3a",
    "minecraft:the_end":             "#2a2040",
    "minecraft:small_end_islands":   "#352850",
    "minecraft:end_midlands":        "#3a2e55",
    "minecraft:end_highlands":       "#453565",
    "minecraft:end_barrens":         "#2e2448",
}
DEFAULT_COLOR = "#6a6a6a"
CAVE_BIOMES   = {"minecraft:deep_dark", "minecraft:dripstone_caves", "minecraft:lush_caves"}

BLOCK_COLORS: dict[str, str | None] = {
    # Naturales → None (transparente, muestra color de bioma)
    "minecraft:grass_block": None, "minecraft:water": None,
    "minecraft:sand": None, "minecraft:red_sand": None,
    "minecraft:dirt": None, "minecraft:coarse_dirt": None,
    "minecraft:gravel": None, "minecraft:stone": None,
    "minecraft:deepslate": None, "minecraft:andesite": None,
    "minecraft:diorite": None, "minecraft:granite": None,
    "minecraft:tuff": None, "minecraft:calcite": None,
    "minecraft:clay": None, "minecraft:dirt_path": None,
    "minecraft:podzol": None, "minecraft:mycelium": None,
    "minecraft:rooted_dirt": None, "minecraft:mud": None,
    "minecraft:moss_block": None, "minecraft:moss_carpet": None,
    "minecraft:muddy_mangrove_roots": None, "minecraft:mangrove_roots": None,
    "minecraft:air": None, "minecraft:cave_air": None, "minecraft:void_air": None,
    "minecraft:oak_leaves": None, "minecraft:birch_leaves": None,
    "minecraft:spruce_leaves": None, "minecraft:jungle_leaves": None,
    "minecraft:acacia_leaves": None, "minecraft:dark_oak_leaves": None,
    "minecraft:cherry_leaves": None, "minecraft:mangrove_leaves": None,
    "minecraft:azalea_leaves": None, "minecraft:flowering_azalea_leaves": None,
    "minecraft:oak_log": None, "minecraft:birch_log": None,
    "minecraft:spruce_log": None, "minecraft:jungle_log": None,
    "minecraft:acacia_log": None, "minecraft:dark_oak_log": None,
    "minecraft:cherry_log": None, "minecraft:mangrove_log": None,
    "minecraft:bamboo_block": None,
    "minecraft:short_grass": None, "minecraft:tall_grass": None,
    "minecraft:fern": None, "minecraft:large_fern": None,
    "minecraft:dandelion": None, "minecraft:poppy": None,
    "minecraft:blue_orchid": None, "minecraft:allium": None,
    "minecraft:azure_bluet": None, "minecraft:oxeye_daisy": None,
    "minecraft:cornflower": None, "minecraft:lily_of_the_valley": None,
    "minecraft:sunflower": None, "minecraft:lilac": None,
    "minecraft:rose_bush": None, "minecraft:peony": None,
    "minecraft:pink_petals": None, "minecraft:wildflowers": None,
    "minecraft:leaf_litter": None, "minecraft:bush": None,
    "minecraft:cactus": None, "minecraft:sugar_cane": None,
    "minecraft:bamboo": None, "minecraft:dead_bush": None,
    "minecraft:lily_pad": None, "minecraft:seagrass": None,
    "minecraft:tall_seagrass": None,
    "minecraft:snow": None, "minecraft:snow_block": None,
    "minecraft:ice": None, "minecraft:packed_ice": None,
    "minecraft:blue_ice": None, "minecraft:powder_snow": None,
    "minecraft:coal_ore": None, "minecraft:iron_ore": None,
    "minecraft:copper_ore": None, "minecraft:gold_ore": None,
    "minecraft:amethyst_block": None, "minecraft:budding_amethyst": None,
    "minecraft:large_amethyst_bud": None, "minecraft:medium_amethyst_bud": None,
    "minecraft:small_amethyst_bud": None, "minecraft:amethyst_cluster": None,
    "minecraft:dripstone_block": None, "minecraft:pointed_dripstone": None,
    "minecraft:sculk": None, "minecraft:sculk_vein": None,
    "minecraft:basalt": None, "minecraft:smooth_basalt": None,
    "minecraft:terracotta": None, "minecraft:small_dripleaf": None,
    # Bloques de construcción → color hex
    "minecraft:oak_planks":       "#a07830", "minecraft:birch_planks":      "#c8b460",
    "minecraft:spruce_planks":    "#6c4a1c", "minecraft:jungle_planks":     "#9c6428",
    "minecraft:acacia_planks":    "#b05a28", "minecraft:dark_oak_planks":   "#3c2810",
    "minecraft:cherry_planks":    "#d4906c", "minecraft:mangrove_planks":   "#7a2218",
    "minecraft:bamboo_planks":    "#c0b030", "minecraft:crimson_planks":    "#6c2848",
    "minecraft:warped_planks":    "#206858",
    "minecraft:oak_slab":         "#a07830", "minecraft:oak_stairs":        "#a07830",
    "minecraft:oak_fence":        "#a07830", "minecraft:oak_fence_gate":    "#a07830",
    "minecraft:oak_door":         "#a07830", "minecraft:oak_trapdoor":      "#a07830",
    "minecraft:spruce_slab":      "#6c4a1c", "minecraft:spruce_stairs":     "#6c4a1c",
    "minecraft:spruce_fence":     "#6c4a1c", "minecraft:spruce_trapdoor":   "#6c4a1c",
    "minecraft:birch_slab":       "#c8b460", "minecraft:birch_fence":       "#c8b460",
    "minecraft:dark_oak_slab":    "#3c2810", "minecraft:dark_oak_stairs":   "#3c2810",
    "minecraft:dark_oak_fence":   "#3c2810", "minecraft:dark_oak_trapdoor": "#3c2810",
    "minecraft:cherry_slab":      "#d4906c", "minecraft:cherry_stairs":     "#d4906c",
    "minecraft:cherry_fence":     "#d4906c", "minecraft:cherry_trapdoor":   "#d4906c",
    "minecraft:jungle_slab":      "#9c6428", "minecraft:acacia_slab":       "#b05a28",
    "minecraft:mangrove_slab":    "#7a2218",
    "minecraft:cobblestone":      "#8a8a8a", "minecraft:mossy_cobblestone": "#6a8a6a",
    "minecraft:stone_bricks":     "#8a8a8a", "minecraft:mossy_stone_bricks":"#6a8a6a",
    "minecraft:cracked_stone_bricks": "#787878", "minecraft:chiseled_stone_bricks": "#8c8c8c",
    "minecraft:smooth_stone":     "#909090", "minecraft:stone_slab":        "#909090",
    "minecraft:stone_brick_slab": "#8a8a8a", "minecraft:stone_brick_stairs":"#8a8a8a",
    "minecraft:stone_brick_wall": "#8a8a8a",
    "minecraft:polished_andesite":"#848484", "minecraft:andesite_slab":     "#848484",
    "minecraft:polished_diorite": "#d0d0d0", "minecraft:diorite_slab":      "#d0d0d0",
    "minecraft:polished_granite": "#a07060", "minecraft:granite_slab":      "#a07060",
    "minecraft:polished_tuff":    "#70787c", "minecraft:tuff_bricks":       "#6c747c",
    "minecraft:tuff_brick_slab":  "#6c747c", "minecraft:tuff_brick_wall":   "#6c747c",
    "minecraft:deepslate_bricks": "#484848", "minecraft:deepslate_tiles":   "#3c3c3c",
    "minecraft:polished_deepslate":"#4c4c4c","minecraft:cobbled_deepslate": "#585858",
    "minecraft:bricks":           "#9c5840", "minecraft:brick_slab":        "#9c5840",
    "minecraft:brick_stairs":     "#9c5840", "minecraft:brick_wall":        "#9c5840",
    "minecraft:sandstone":        "#d8c880", "minecraft:smooth_sandstone":  "#d8c880",
    "minecraft:red_sandstone":    "#b05820", "minecraft:smooth_red_sandstone":"#b05820",
    "minecraft:quartz_block":     "#e0dcd8", "minecraft:smooth_quartz":     "#dedad6",
    "minecraft:quartz_bricks":    "#dedad6", "minecraft:quartz_slab":       "#dedad6",
    "minecraft:glass":            "#c0e8f8", "minecraft:glass_pane":        "#c0e8f8",
    "minecraft:white_stained_glass":      "#f0f0f0", "minecraft:light_gray_stained_glass":"#a0a0a0",
    "minecraft:gray_stained_glass":       "#606060", "minecraft:black_stained_glass":     "#202020",
    "minecraft:red_stained_glass":        "#c02020", "minecraft:orange_stained_glass":    "#e87020",
    "minecraft:yellow_stained_glass":     "#e8d020", "minecraft:lime_stained_glass":      "#50c030",
    "minecraft:green_stained_glass":      "#405020", "minecraft:cyan_stained_glass":      "#308090",
    "minecraft:light_blue_stained_glass": "#60a8e0", "minecraft:blue_stained_glass":      "#2040c0",
    "minecraft:purple_stained_glass":     "#7020a0", "minecraft:magenta_stained_glass":   "#c050c0",
    "minecraft:pink_stained_glass":       "#e890b0", "minecraft:brown_stained_glass":     "#604020",
    "minecraft:white_wool":        "#e0e0e0", "minecraft:light_gray_wool":   "#909090",
    "minecraft:gray_wool":         "#505050", "minecraft:black_wool":        "#1c1c1c",
    "minecraft:red_wool":          "#b02020", "minecraft:orange_wool":       "#d46020",
    "minecraft:yellow_wool":       "#e0c020", "minecraft:lime_wool":         "#40b020",
    "minecraft:green_wool":        "#405020", "minecraft:cyan_wool":         "#208070",
    "minecraft:light_blue_wool":   "#40a0d0", "minecraft:blue_wool":         "#2030a0",
    "minecraft:purple_wool":       "#6020a0", "minecraft:magenta_wool":      "#b040b0",
    "minecraft:pink_wool":         "#d07090", "minecraft:brown_wool":        "#604020",
    "minecraft:white_concrete":        "#dadada", "minecraft:light_gray_concrete": "#8c8c8c",
    "minecraft:gray_concrete":         "#404040", "minecraft:black_concrete":       "#0c0c0c",
    "minecraft:red_concrete":          "#8e2020", "minecraft:orange_concrete":      "#cc5500",
    "minecraft:yellow_concrete":       "#e0c020", "minecraft:lime_concrete":        "#30a818",
    "minecraft:green_concrete":        "#485018", "minecraft:cyan_concrete":        "#156070",
    "minecraft:light_blue_concrete":   "#3090c0", "minecraft:blue_concrete":        "#2c3498",
    "minecraft:purple_concrete":       "#641f9c", "minecraft:magenta_concrete":     "#b040b0",
    "minecraft:pink_concrete":         "#d05878", "minecraft:brown_concrete":       "#603410",
    "minecraft:prismarine":       "#6b9090", "minecraft:prismarine_bricks": "#68c0a8",
    "minecraft:dark_prismarine":  "#2c5050", "minecraft:dark_prismarine_stairs":"#2c5050",
    "minecraft:sea_lantern":      "#a0d8e0",
    "minecraft:iron_block":       "#d0d0d0", "minecraft:gold_block":        "#e0c020",
    "minecraft:diamond_block":    "#50e0d8", "minecraft:emerald_block":     "#10c040",
    "minecraft:copper_block":     "#c06040", "minecraft:oxidized_copper":   "#609c88",
    "minecraft:iron_bars":        "#b0b0b0", "minecraft:chain":             "#606060",
    "minecraft:crafting_table":   "#a07830", "minecraft:furnace":           "#909090",
    "minecraft:chest":            "#c89030", "minecraft:trapped_chest":     "#c89030",
    "minecraft:ender_chest":      "#204040", "minecraft:barrel":            "#8c6830",
    "minecraft:bookshelf":        "#a07830", "minecraft:enchanting_table":  "#781818",
    "minecraft:anvil":            "#505050", "minecraft:beacon":            "#90e8f0",
    "minecraft:white_bed":        "#e0e0e0", "minecraft:red_bed":           "#c02020",
    "minecraft:hay_block":        "#c8a820", "minecraft:pumpkin":           "#e87020",
    "minecraft:carved_pumpkin":   "#e87020", "minecraft:jack_o_lantern":    "#e87020",
    "minecraft:lantern":          "#c09030", "minecraft:soul_lantern":      "#30a0c0",
    "minecraft:campfire":         "#c06020", "minecraft:farmland":          "#8c6030",
    "minecraft:wheat":            "#c8a820", "minecraft:beetroots":         "#8c1818",
    "minecraft:carrots":          "#e87020", "minecraft:potatoes":          "#c8a040",
    "minecraft:nether_bricks":    "#2c1818", "minecraft:red_nether_bricks": "#5c1010",
    "minecraft:glowstone":        "#c0a840",
    "minecraft:purpur_block":     "#9c6898", "minecraft:purpur_pillar":     "#9c6898",
    "minecraft:end_stone_bricks": "#d0d060",
}

# ── NBT parser mínimo ─────────────────────────────────────────────────────────
_T_END=0;_T_BYTE=1;_T_SHORT=2;_T_INT=3;_T_LONG=4;_T_FLOAT=5
_T_DOUBLE=6;_T_BARR=7;_T_STR=8;_T_LIST=9;_T_COMP=10;_T_IARR=11;_T_LARR=12

def _rs(b, p):
    l=struct.unpack_from(">H",b,p)[0]; p+=2
    return b[p:p+l].decode("utf-8","replace"), p+l

def _rv(b, p, t):
    if t==_T_END:   return None, p
    if t==_T_BYTE:  return struct.unpack_from(">b",b,p)[0], p+1
    if t==_T_SHORT: return struct.unpack_from(">h",b,p)[0], p+2
    if t==_T_INT:   return struct.unpack_from(">i",b,p)[0], p+4
    if t==_T_LONG:  return struct.unpack_from(">q",b,p)[0], p+8
    if t==_T_FLOAT: return struct.unpack_from(">f",b,p)[0], p+4
    if t==_T_DOUBLE:return struct.unpack_from(">d",b,p)[0], p+8
    if t==_T_STR:   return _rs(b,p)
    if t==_T_BARR:
        n=struct.unpack_from(">i",b,p)[0]; p+=4; return list(b[p:p+n]), p+n
    if t==_T_IARR:
        n=struct.unpack_from(">i",b,p)[0]; p+=4
        return list(struct.unpack_from(f">{n}i",b,p)), p+n*4
    if t==_T_LARR:
        n=struct.unpack_from(">i",b,p)[0]; p+=4
        return list(struct.unpack_from(f">{n}q",b,p)), p+n*8
    if t==_T_LIST:
        et=b[p]; n=struct.unpack_from(">i",b,p+1)[0]; p+=5
        items=[]
        for _ in range(n): v,p=_rv(b,p,et); items.append(v)
        return items,p
    if t==_T_COMP:
        d={}
        while True:
            ct=b[p]; p+=1
            if ct==_T_END: break
            n,p=_rs(b,p); v,p=_rv(b,p,ct); d[n]=v
        return d,p
    raise ValueError(f"Unknown NBT tag {t}")

def _unpack_biome_indices(longs: list, pal_size: int, count: int = 64) -> list:
    if pal_size <= 1: return [0]*count
    bits = max(1, math.ceil(math.log2(pal_size)))
    vpl  = 64 // bits
    mask = (1 << bits) - 1
    out  = []
    for i in range(count):
        li = i // vpl; sh = (i % vpl) * bits
        raw = longs[li] & 0xFFFFFFFFFFFFFFFF if li < len(longs) else 0
        out.append((raw >> sh) & mask)
    return out

def _unpack_block_indices(longs: list, pal_size: int, count: int = 4096) -> list:
    if pal_size <= 1: return [0] * count
    bits = max(4, math.ceil(math.log2(pal_size)))
    vpl  = 64 // bits
    mask = (1 << bits) - 1
    out  = []
    for i in range(count):
        li = i // vpl; sh = (i % vpl) * bits
        raw = longs[li] & 0xFFFFFFFFFFFFFFFF if li < len(longs) else 0
        out.append((raw >> sh) & mask)
    return out

def _unpack_heightmap(longs: list, count: int = 256) -> list:
    """Unpack 9-bit heightmap values from array of longs.
    1.18+: 7 values per long (bits 0-62), bit 63 unused.
    Pre-1.16: continuous bit stream across 36 longs.
    Values are unsigned Y+64 offsets from world bottom."""
    if not longs:
        return [0] * count
    mask = 0x1FF
    if len(longs) == 36:
        # pre-1.16: uninterrupted 9-bit stream
        out = []
        for i in range(count):
            bit = i * 9
            li, sh = bit // 64, bit % 64
            raw = longs[li] & 0xFFFFFFFFFFFFFFFF if li < len(longs) else 0
            val = (raw >> sh) & mask
            if sh > 55 and li + 1 < len(longs):
                raw2 = longs[li + 1] & 0xFFFFFFFFFFFFFFFF
                val = ((raw2 << (64 - sh)) | val) & mask
            out.append(val)
        return out
    # 1.18+: 7 values per long
    vpl = 7
    out = []
    for i in range(count):
        li, sh = i // vpl, (i % vpl) * 9
        raw = longs[li] & 0xFFFFFFFFFFFFFFFF if li < len(longs) else 0
        out.append((raw >> sh) & mask)
    return out

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

def _top_block_4x4(sections: list, ws_grid: list) -> dict:
    """Devuelve {(x4,z4): block_name} para cada tile 4×4 del chunk.
    Solo llamar para chunks dentro de la zona activa."""
    sec_by_y = {sec.get("Y"): sec for sec in sections if "Y" in sec}
    result = {}
    for z4 in range(4):
        for x4 in range(4):
            x_loc = x4 * 4 + 1
            z_loc = z4 * 4 + 1
            raw_y = ws_grid[z_loc * 16 + x_loc]
            wy    = raw_y - 64 - 1  # WORLD_SURFACE apunta a Y+1 del bloque real
            sec   = sec_by_y.get(wy >> 4)
            block = "minecraft:air"
            if sec:
                bs      = sec.get("block_states", {})
                palette = bs.get("palette", [])
                if palette:
                    if len(palette) == 1:
                        block = palette[0].get("Name", "minecraft:air")
                    else:
                        data = bs.get("data", [])
                        if data:
                            y_loc = wy & 0xF
                            idx   = y_loc * 256 + z_loc * 16 + x_loc
                            idxs  = _unpack_block_indices(data, len(palette))
                            pi    = idxs[idx] if idx < len(idxs) else 0
                            block = palette[pi].get("Name", "minecraft:air") if pi < len(palette) else "minecraft:air"
            result[(x4, z4)] = block
    return result

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
