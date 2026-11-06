# mc-chunk-map

Interactive biome and terrain map viewer for Minecraft Java Edition worlds. Reads `.mca` files directly — no plugins, no server modifications — and renders a fast, progressive map in the browser with biome colors, topography, hillshading, and player structure detection.

---

## Features

- **Biome colors** — 60+ biomes, each with a distinct color
- **Topography** — height-based shading showing terrain elevation
- **Hillshading** — simulated directional lighting from the NW
- **Contour lines** — isoline marks at height discontinuities > 20 blocks
- **Block layer** — shows player-built structures (planks, stone bricks, glass, wool…) over natural terrain using actual top-block data
- **Active zone** — configurable radius that refreshes top-block data periodically to detect new constructions without a full world re-scan
- **Progressive loading** — map image appears in ~1s; tile index loads in background enabling tooltips and biome toggles
- **Biome legend** — toggle visibility, click to highlight individual biomes
- **Tooltips** — biome, coordinates, height, and top block name on hover
- **Spawn marker** — reads `level.dat` to place the world spawn
- **Persistent cache** — processed chunks stored in `chunk_cache.json`; new chunks are added when regions change, while tracked blocks in the active zone refresh periodically
- **Zero server interference** — read-only access to world files

---

## Architecture

```
.mca files (Anvil format)
        │
        ▼
  Python parser (NBT, no external deps)
        │
        ▼
  Persistent chunk cache (chunk_cache.json)
        │
        ▼
  FastAPI backend ──→ Server-side PNG rendering (Pillow)
        │                    map_base.png       ← biome colors
        │                    map_shade.png      ← topography
        │                    map_hillshade.png  ← hillshading
        │                    map_isolines.png   ← contour lines
        │                    map_blocks.png     ← player structures
        │                    tile_index.json.gz ← tile metadata
        ▼
  Leaflet.js frontend (canvas GPU compositing)
```

---

## Requirements

- Python 3.11+
- `python3-pip`, `python3-venv`
- [Pillow](https://pillow.readthedocs.io/) (installed automatically by `setup.sh`)
- Read access to the Minecraft world directory
- Port 8200 free (configurable)
- Minecraft Java Edition **1.18+** (see [version support](#minecraft-version-support))

The optional fullscreen map prototype uses post-processing effects in **Minecraft Java 26.3**. [Build and test the map packs](minecraft/posteffect/README.md).

## One-block surface crop

The offline extractor reads a bounded area at **one column per block**, independently of the web map's 4×4 cache. It shares the NBT and block-state reader with the backend, including legacy `Name`/`Properties`, 26.3 compact strings and `id`/`properties`, and heterogeneous-list wrappers. Each section's packed indices are decoded once per chunk. Block properties are preserved.

```bash
python -B backend/extract_surface.py --world /path/to/world/dimensions/minecraft/overworld --origin-x -256 --origin-z -256 --size 512 --min-y -64 --output backend/map_images/surface-512
```

Use a stable copy of the world's region files. `--world` contains `region/`; the origin is the inclusive minimum X/Z and the crop extends towards positive X/Z. Set `--min-y` to the dimension's actual minimum Y (Overworld: -64). Output must be outside the world directory. This prototype supports fully generated 1.18+ chunks with padded heightmaps and gzip/zlib/uncompressed MCA chunks; external `.mcc` chunks and LZ4 are rejected explicitly.

The output contains:

- `surface.zip`: versioned `metadata.json`, `height.i16le` (surface block world Y), `state.u16le` (state palette indices), and `valid.u8` (1 = surface present). Arrays are row-major, with X increasing across the image and Z downwards. The palette retains each block ID and its properties. The source chunk coordinates, timestamps, payload hashes and data versions are recorded.
- `surface.png`: a 1:1 diagnostic material image, with a separate color for dirt paths. Colors approximate materials; they do not render vanilla block models or biome tint. Unhandled materials appear magenta and are counted in the report. Missing or empty columns are transparent.
- `report.json`: coverage, array and ZIP sizes, unknown material counts and elapsed extraction/export time.

Heights use `raw + min_y - 1`, rather than the existing cache's averaged raw heightmap offsets. Validity is separate, so a real surface at Y=0 is preserved. The three arrays use **5 bytes per column**, or **1.25 MiB for 512×512**, before compression and excluding the palette, NBT and preview buffers. Each run reads the selected chunks afresh; it does not reuse or modify `chunk_cache.json`. Changed regions are rejected during extraction. The pack exporter accepts `--surface surface.zip` to overlay this one-block detail over the global map, preserving its coordinates, controls and zoom. [Build the detailed map packs](minecraft/posteffect/README.md#añadir-detalle-1--1).

This is the extraction stage for the resolution comparison and planned fixed isometric surface. It stores only the top surface, without ground beneath canopies, interiors or overhangs. Those representations, tile/LOD support and in-game marker projection remain pending. See [ROADMAP.md](ROADMAP.md).

### Compare 4×4 and 1×1

```bash
python -B backend/compare_surface.py --surface backend/map_images/surface-512/surface.zip --output backend/map_images/surface-comparison
```

The comparison reads the saved archive, uses the same material palette at both resolutions, and generates native material/hillshade PNGs, `comparison.png` (full extent), `detail.png` (a 128-block window enlarged equally), and `comparison.json`. The 4×4 view averages the 16 heights and samples the material at offset +1,+1, matching the web reader's sampling position. A coarse cell with any missing column stays transparent. The whole extent and origin are identical, and enlargement uses nearest-neighbor sampling.

Both views use the web hillshading light coefficients and 0.3 minimum, multiplied into the material color at 100%, without blur or additional topography. Gradients divide by the physical spacing in blocks; `--vertical-scale` defaults to 1 and applies equally to both views. This intentionally differs from the production web formula, which divides by cell count and exaggerates slopes fourfold at 4×4. Set `--vertical-scale 4` to compare both views with that exaggeration. These images use material colors rather than the installed map's biome base, so this is a controlled resolution comparison, not a screenshot of the existing game map.

The detail window is selected by maximum dirt-path coverage on a fixed 32-block grid. Its bounds and selection rule are recorded, alongside the full image for context. The report measures exact path overlap, recall and precision against the 1×1 surface, distinguishing omitted blocks from paths widened by coarse sampling. Render times exclude world extraction and do not measure client FPS, peak memory or resource-pack size. Diagnostic PNG sizes are recorded separately.

The real crop shows sharper paths and structures at 1×1, together with noisier height gradients from vegetation. Ground beneath plants/canopies is not reconstructed in this comparison; that treatment remains a prerequisite for improving the isometric surface.

### Full world at one block per texel

`backend/render_world_map.py` reads a stable world copy and renders bounded tiles at 1×1, with a one-block height halo to avoid shading seams. `backend/export_posteffect_map.py --world-tiles <directory>` packages the completed tiles without a coarse overview or LOD. Edge tiles retain their actual dimensions. Terrain remains static until regenerated. See [full-world build and limits](minecraft/posteffect/README.md#mundo-completo-a-1--1).

Run the reader, crop and pack regression tests after installing `requirements.txt`:

```bash
python -B -m unittest discover -s tests -v
```

---

## Quick start (systemd)

```bash
# 1. Clone the project
cd /opt && git clone https://github.com/YOUR_USER/mc-chunk-map.git

# 2. Run setup (adjust path to your world)
cd mc-chunk-map
bash setup.sh /opt/minecraft/world/dimensions/minecraft/overworld

# 3. Install and start the service
cp mc-chunk-map.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mc-chunk-map

# 4. Verify
curl http://localhost:8200/api/stats
```

Open `http://SERVER_IP:8200` in your browser.

---

## Quick start (Docker)

```bash
# Edit WORLD_PATH in docker-compose.yml if needed, then:
docker compose up -d
```

---

## WORLD_PATH — getting it right

`WORLD_PATH` must point to the directory that **contains** `region/`. This varies by server type:

| Server type | WORLD_PATH |
|---|---|
| Java 1.18+ (Vanilla, Paper, Fabric…) | `<world_root>/dimensions/minecraft/overworld` |
| Java < 1.18 or legacy worlds | `<world_root>` |

**Example with Paper 1.21 at `/opt/minecraft/`:**
```
WORLD_PATH=/opt/minecraft/world/dimensions/minecraft/overworld
```

To find the correct path: `find <world_root> -name "r.*.*.mca" | head -3` — `WORLD_PATH` is the parent directory of those `.mca` files.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `WORLD_PATH` | `/opt/minecraft/world` | Path to the directory containing `region/` |
| `HOST` | `0.0.0.0` | Listen address |
| `PORT` | `8200` | Listen port |
| `CACHE_TTL` | `120` | Seconds between mtime checks (not a full re-scan) |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` |
| `ACTIVE_ZONE_CENTER_X` | `0` | Block X coordinate of the active zone center |
| `ACTIVE_ZONE_CENTER_Z` | `0` | Block Z coordinate of the active zone center |
| `ACTIVE_ZONE_RADIUS` | `32` | Radius in chunks for top-block tracking |
| `ACTIVE_ZONE_TTL` | `3600` | Seconds between active zone refreshes |

### Active zone

The active zone is a configurable area (default: 32-chunk / 512-block radius around 0,0) where the top block of every tile is tracked. This enables the **Structures** layer and detects player-built buildings without scanning the entire world.

Set the center to your main base coordinates:

```env
ACTIVE_ZONE_CENTER_X=512
ACTIVE_ZONE_CENTER_Z=-256
```

---

## Nginx Proxy Manager

1. New Proxy Host: `map.yourdomain.com` → `localhost:8200`
2. In "Advanced" paste the contents of `nginx/mc-chunk-map.conf`
3. Enable SSL with Let's Encrypt

---

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Frontend HTML |
| `/api/map.png?layer=<layer>` | GET | Pre-rendered PNG layer (`base`, `shade`, `hillshade`, `isolines`, `blocks`) |
| `/api/tile-index` | GET | Gzipped JSON with tile metadata (biome palette, block palette, per-tile data) |
| `/api/stats` | GET | World statistics |
| `/api/spawn` | GET | Spawn coordinates from `level.dat` |
| `/api/biomes` | GET | Known biome palette with colors |
| `/api/chunks` | GET | Full tile list (large — prefer tile-index for frontend use) |
| `/api/refresh` | POST | Force re-scan of the active zone |

---

## Proxmox / LXC multi-container

If Minecraft runs in a different LXC container, bind-mount the world read-only:

```ini
# /etc/pve/lxc/<MAP_CT_ID>.conf
mp0: /path/to/minecraft/world,mp=/opt/minecraft/world,ro=1
```

Then set `WORLD_PATH` accordingly.

---

## Minecraft version support

| Version | Biomes | Heightmap | Top block (Structures layer) |
|---|---|---|---|
| Java 1.18 – 1.21+ | ✅ Full (per-section, 4×4 resolution) | ✅ | ✅ |
| Java 1.16 – 1.17 | ⚠️ Chunk-level only | ✅ | ❌ |
| Java < 1.16 | ❌ Shown as `unknown` | ❌ | ❌ |

---

## Technical notes

- **NBT parser** is custom — zero external dependencies beyond Pillow and FastAPI.
- Only chunks with `Status: minecraft:full` are rendered (fully generated terrain).
- Cave biomes (`deep_dark`, `dripstone_caves`, `lush_caves`) are excluded from the surface map.
- **Persistent cache**: processed chunks are stored in `backend/chunk_cache.json`. Changed `.mca` files trigger a scan for new chunks; already known chunks are reused. Top blocks in the active zone refresh on its TTL or `/api/refresh`; changes outside it are not tracked per chunk. The offline 1×1 extractor always reads its selected chunks afresh.
- **Performance**: the backend generates server-side PNGs (≈3 MB total) instead of sending raw JSON. The map appears in ~1s on a 20 Mbps connection vs 80s+ with raw chunk data.
- **Memory** grows with the loaded world, derived tile dictionaries and PNG buffers. The backend reads the world without modifying it and writes its own cache and render files. The bounded 1×1 extractor uses separate compact arrays.
- **GPU compositing**: the frontend stacks PNG layers on an HTML5 canvas using multiply blend mode for shade/hillshading. No per-tile DOM elements.
