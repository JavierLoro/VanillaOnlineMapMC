# mc-chunk-map

Visor de mapa de biomas para mundos Minecraft Java Edition. Lee los archivos `.mca` directamente del servidor —sin plugins, sin modificar nada— y renderiza un mapa interactivo en el navegador con colores por bioma a resolución de **4×4 bloques por píxel** (la máxima que permite el formato Anvil).

```
mc-chunk-map/
├── setup.sh                  ← script de instalación (genera .env y .service)
├── docker-compose.yml        ← despliegue alternativo con Docker
├── README.md
├── backend/
│   ├── main.py               ← FastAPI + parser NBT/MCA propio (sin deps externas)
│   ├── chunk_cache.json      ← caché persistente por chunk (generado automáticamente)
│   └── Dockerfile
├── frontend/
│   └── index.html            ← Leaflet.js, sin build step
└── nginx/
    └── mc-chunk-map.conf     ← bloque para Nginx Proxy Manager
```

---

## Requisitos

- Python 3.11+ con `python3-pip` y `python3-venv`
- Acceso de lectura al directorio del mundo Minecraft
- Puerto 8200 libre (configurable)

---

## WORLD_PATH — ruta correcta

El `WORLD_PATH` debe apuntar al directorio que contiene la carpeta `region/`. Esto varía según la versión del servidor:

| Versión / tipo | WORLD_PATH |
|---|---|
| Java 1.18+ (Paper, Vanilla, Fabric…) | `<raíz_mundo>/dimensions/minecraft/overworld` |
| Java < 1.18 o mundos legados | `<raíz_mundo>` |

El archivo `level.dat` (spawn, semilla…) se busca automáticamente subiendo desde `WORLD_PATH` hasta encontrarlo.

**Ejemplo con Paper 1.21 en `/opt/minecraft/`:**
```
WORLD_PATH=/opt/minecraft/world/dimensions/minecraft/overworld
```

---

## Despliegue rápido (systemd)

```bash
# 1. Extraer el zip
cd /opt && unzip mc-chunk-map.zip

# 2. Instalar python3-pip y python3-venv si no están (Debian/Ubuntu)
apt-get install -y python3-pip python3-venv

# 3. Ejecutar setup (ajusta la ruta al mundo)
cd mc-chunk-map
bash setup.sh /opt/minecraft/world/dimensions/minecraft/overworld

# 4. Instalar y activar el servicio
cp mc-chunk-map.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mc-chunk-map

# 5. Verificar
curl http://localhost:8200/api/stats
```

Abre `http://IP_SERVIDOR:8200` en el navegador.

---

## Despliegue con Docker

```bash
# Ajusta WORLD_PATH en docker-compose.yml si es necesario
docker compose up -d
```

---

## Nginx Proxy Manager

1. Nuevo Proxy Host: `map.tudominio.com` → `localhost:8200`
2. En "Advanced" pega el contenido de `nginx/mc-chunk-map.conf`
3. Activa SSL con Let's Encrypt

---

## API

| Endpoint | Método | Descripción |
|---|---|---|
| `/` | GET | Frontend HTML |
| `/api/chunks` | GET | Lista de tiles 4×4 con bioma y color |
| `/api/stats` | GET | Estadísticas del mundo |
| `/api/spawn` | GET | Coordenadas del spawn (lee `level.dat`) |
| `/api/biomes` | GET | Paleta de biomas conocidos con colores |
| `/api/refresh` | POST | Invalida caché y fuerza re-scan |

### Parámetros `/api/chunks`

```
?biome=minecraft:forest
?bx4_min=-100&bx4_max=100&bz4_min=-100&bz4_max=100
```

Las coordenadas `bx4`/`bz4` son unidades de 4 bloques. Para convertir a bloques: `bx4 * 4`.

### Respuesta `/api/stats`

```json
{
  "total_tiles": 10400,
  "total_full_chunks": 650,
  "total_regions": 4,
  "biome_distribution": { "minecraft:snowy_plains": 5342, ... }
}
```

### Respuesta `/api/spawn`

```json
{ "x": 0, "y": 117, "z": 0, "bx4": 0, "bz4": 0, "chunk_x": 0, "chunk_z": 0, "dimension": "minecraft:overworld" }
```

---

## Variables de entorno (`.env`)

| Variable | Default | Descripción |
|---|---|---|
| `WORLD_PATH` | `/opt/minecraft/world` | Ruta al directorio que contiene `region/` |
| `HOST` | `0.0.0.0` | IP de escucha |
| `PORT` | `8200` | Puerto |
| `CACHE_TTL` | `120` | Segundos entre comprobaciones de mtime (no re-scan completo) |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` |

---

## Proxmox / LXC multi-contenedor

Si el servidor Minecraft corre en un LXC diferente, monta el mundo como bind mount de solo lectura:

```ini
# /etc/pve/lxc/<ID_LXC_MAPA>.conf
mp0: /ruta/al/mundo,mp=/opt/minecraft/world,ro=1
```

Ajusta `WORLD_PATH` según la estructura del mundo montado.

---

## Versiones Minecraft soportadas

- Java Edition **1.18 – 1.21+** — soporte completo (biomas por sección, resolución 4×4)
- Java Edition **1.16 – 1.17** — chunks mostrados, biomas a nivel de chunk (sin `data` array)
- Java Edition **< 1.16** — chunks en gris (`unknown`), biomas almacenados como integers

---

## Notas técnicas

- El parser NBT es propio, sin dependencias externas.
- Solo se renderizan chunks con `Status: minecraft:full` (terrain completamente generado).
- Los biomas de cueva (`deep_dark`, `dripstone_caves`, `lush_caves`) se excluyen del mapa superficial.
- **Caché persistente por chunk**: los chunks procesados se guardan en `backend/chunk_cache.json`. Al reiniciar el servicio se carga del disco — cero re-parseo.
- Cuando el servidor Minecraft genera chunks nuevos, el `.mca` cambia su `mtime`. Solo se reparsean los chunks nuevos de ese archivo; los ya conocidos se reusan directamente.
- `CACHE_TTL` controla cada cuántos segundos se comprueban los `mtime` de los `.mca`, no cuándo se re-lee todo.
- Uso de memoria: ~50 MB en reposo. Solo lectura sobre el mundo, `chunk_cache.json` es la única escritura.

---

## Despliegue con agente IA (Claude u otro)

Esta sección documenta los pasos exactos para que un agente de IA instale el servicio de forma autónoma.

### Información que el agente necesita antes de empezar

Proporciona estos datos al agente:

1. **Sistema operativo** del host (Debian, Ubuntu, etc.) y versión
2. **Ruta raíz del mundo Minecraft** (el directorio que contiene `level.dat`)
3. **ID o IP del contenedor/servidor** donde se va a instalar
4. **Puerto deseado** (por defecto 8200)
5. Si usa Proxmox LXC: si el Minecraft está en otro CT y hay que hacer bind mount

### Prompt sugerido para el agente

```
Instala el servicio mc-chunk-map en [CT ID / IP].
El zip está en [ruta del zip].
La raíz del mundo Minecraft está en [ruta, ej: /opt/minecraft/world].
El sistema operativo es [Debian 13 / Ubuntu 24.04 / etc.].
```

### Pasos que debe ejecutar el agente (en orden)

```bash
# PASO 1 — Verificar Python 3.11+
python3 --version
# Si < 3.11: apt-get install -y python3.11

# PASO 2 — Instalar pip y venv (Debian/Ubuntu no los incluyen por defecto)
apt-get update -qq
apt-get install -y python3-pip python3-venv

# PASO 3 — Extraer el zip
cd /opt && unzip <zip> -d .
cd mc-chunk-map

# PASO 4 — Determinar WORLD_PATH correcto
# El agente debe buscar la carpeta region/ dentro del mundo:
#   Opción A (Java 1.18+): <raíz>/dimensions/minecraft/overworld/region/  ← más común
#   Opción B (legacy):     <raíz>/region/
# WORLD_PATH es el directorio PADRE de region/, no region/ en sí.
find <raíz_mundo> -name "r.*.*.mca" | head -3
# La ruta hasta el directorio que contiene esos .mca es el WORLD_PATH

# PASO 5 — Ejecutar setup.sh con el WORLD_PATH correcto
bash setup.sh <WORLD_PATH>

# PASO 6 — Instalar el servicio systemd
cp mc-chunk-map.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mc-chunk-map

# PASO 7 — Verificar que el servicio está activo
systemctl status mc-chunk-map
curl -s http://localhost:8200/api/stats
curl -s http://localhost:8200/api/spawn

# PASO 8 — Confirmar que hay chunks
# Si total_full_chunks > 0 en /api/stats: instalación correcta.
# Si total_full_chunks = 0: el WORLD_PATH apunta al lugar incorrecto.
#   Revisar con: ls <WORLD_PATH>/region/
```

### Errores comunes que el agente debe saber resolver

| Error | Causa | Solución |
|---|---|---|
| `pip3 no encontrado` en setup.sh | pip3 no instalado | `apt-get install -y python3-pip python3-venv` |
| `total_full_chunks: 0` en stats | WORLD_PATH incorrecto | Buscar `r.*.*.mca` con `find` y ajustar la ruta |
| `level.dat no encontrado` en `/api/spawn` | WORLD_PATH muy profundo | `level.dat` debe estar 3 niveles arriba de WORLD_PATH; verificar estructura |
| Puerto 8200 ocupado | Otro proceso en el puerto | Cambiar `PORT` en `backend/.env` y reiniciar el servicio |
| Chunks se muestran todos grises | Mundo pre-1.16 | Versión no soportada para colores; chunks visibles pero sin bioma |
