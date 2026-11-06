"""Shared NBT, packed-state and surface readers for Java worlds."""

import math
import struct

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
    Values are unsigned offsets of the first free block above the surface, from minY."""
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


def normalize_block_state(value) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Normalize legacy, compact and heterogeneous-list palette entries."""
    if isinstance(value, dict) and set(value) == {""}:
        value = value[""]
    if isinstance(value, str):
        name, properties = value, {}
    elif isinstance(value, dict):
        name = value.get("id", value.get("Name"))
        properties = value.get("properties", value.get("Properties", {}))
    else:
        raise ValueError(f"Unsupported block state: {value!r}")
    if not isinstance(name, str) or not name or not isinstance(properties, dict):
        raise ValueError(f"Invalid block state: {value!r}")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in properties.items()):
        raise ValueError(f"Invalid block properties: {properties!r}")
    if ":" not in name:
        name = "minecraft:" + name
    return name, tuple(sorted(properties.items()))


AIR = ("minecraft:air", ())
AIR_IDS = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}


def surface_y(raw_height: int, min_y: int = -64) -> int | None:
    """Heightmaps store first-free Y relative to the dimension minimum."""
    return min_y + raw_height - 1 if raw_height > 0 else None


class BlockStateReader:
    """Decode each visited section once; discard this reader after the chunk."""

    def __init__(self, sections: list):
        self.sections = {sec["Y"]: sec for sec in sections if "Y" in sec}
        self.decoded = {}

    def state_at(self, x: int, y: int, z: int):
        section_y = y // 16
        if section_y not in self.decoded:
            states = self.sections.get(section_y, {}).get("block_states", {})
            palette = tuple(normalize_block_state(v) for v in states.get("palette", []))
            data = states.get("data", [])
            if len(palette) > 1 and not data:
                raise ValueError(f"Missing block data in section {section_y}")
            if len(palette) > 1:
                bits = max(4, (len(palette) - 1).bit_length())
                required = math.ceil(4096 / (64 // bits))
                if len(data) != required:
                    raise ValueError(f"Invalid block data length in section {section_y}: "
                                     f"expected {required}, got {len(data)}")
            indices = _unpack_block_indices(data, len(palette)) if len(palette) > 1 else None
            self.decoded[section_y] = palette, indices
        palette, indices = self.decoded[section_y]
        if not palette:
            return AIR
        index = ((y & 15) * 256) + (z & 15) * 16 + (x & 15)
        palette_index = indices[index] if indices is not None else 0
        if palette_index >= len(palette):
            raise ValueError(f"Block palette index {palette_index} outside section {section_y}")
        return palette[palette_index]


def _top_block_4x4(sections: list, ws_grid: list, min_y: int = -64) -> dict:
    """Keep the existing one-sample-per-cell interface for the web map."""
    reader = BlockStateReader(sections)
    result = {}
    for z4 in range(4):
        for x4 in range(4):
            x, z = x4 * 4 + 1, z4 * 4 + 1
            y = surface_y(ws_grid[z * 16 + x], min_y)
            result[x4, z4] = reader.state_at(x, y, z)[0] if y is not None else AIR[0]
    return result
