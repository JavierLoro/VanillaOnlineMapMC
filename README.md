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
- **Persistent cache** — processed chunks stored in `chunk_cache.json`; only new/changed chunks are re-parsed on restart
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

The optional in-game dialog prototype targets **Minecraft Java 26.3**. [Build and test the dialog packs](minecraft/dialog/README.md).

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
- **Persistent cache**: processed chunks are stored in `backend/chunk_cache.json`. On restart, only new or changed `.mca` files trigger re-parsing — unchanged chunks load from disk instantly.
- **Performance**: the backend generates server-side PNGs (≈3 MB total) instead of sending raw JSON. The map appears in ~1s on a 20 Mbps connection vs 80s+ with raw chunk data.
- **Memory at rest**: ~50 MB. Read-only on the world; `chunk_cache.json` is the only write.
- **GPU compositing**: the frontend stacks PNG layers on an HTML5 canvas using multiply blend mode for shade/hillshading. No per-tile DOM elements.
