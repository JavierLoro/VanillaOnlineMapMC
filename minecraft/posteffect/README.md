# Prueba del mapa a pantalla completa en Minecraft Java 26.3

El efecto toma el mapa del visor web y lo centra inicialmente en la cámara. La vista cenital combina colores de bioma con hillshading al 100 %, como la capa del visor web, sin topografía adicional ni desenfoque. Puedes desplazarte por el mapa con el ratón sin caminar. Un punto azul indica tu posición al apartar el mapa de la cruceta. Minecraft dibuja la cruceta y el resto del HUD encima.

La opción `--surface` añade un recorte de materiales y hillshading a resolución real 1 × 1 sobre el mapa completo. Fuera de ese recorte se conserva el fondo global. La vista continúa siendo cenital.

## Generar los packs

Con Python 3.11+ y Pillow instalados, ejecuta desde la raíz del repositorio cuando haya terminado el render del visor.

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

La carpeta de render debe contener `map_base.png`, `map_hillshade.png` y `tile_index.json.gz` de la misma generación terminada. El relieve se compone al exportar en una sola textura mediante multiplicación, conservando su transparencia y coordenadas. No utiliza `map_shade.png` ni añade pases o cálculos por fotograma al shader. Si falta la capa, el exportador lo indica; `--style biomes` permite generar la vista plana anterior usando solo la imagen base y el índice.

El encuadre inicial cubre 1024 bloques de alto por defecto y es el máximo acercamiento. `--view-height` fija ese encuadre mínimo; los otros niveles muestran el doble y el cuádruple de terreno. Al cambiar las escalas o actualizar el terreno, regenera e instala ambos packs.

Para comparar las dos vistas con el mismo render:

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-relief --style relief
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-biomes --style biomes
```

Las capas deben tener las mismas dimensiones que la base, no ser anteriores a ella y estar guardadas antes del índice. El exportador comprueba su coherencia y que no cambien durante la generación.

## Añadir detalle 1 × 1

Extrae primero un `surface.zip` con [el extractor de superficie](../../README.md#one-block-surface-crop). A continuación:

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --surface backend/map_images/surface-512/surface.zip --output post-detail-packs
```

El recorte debe estar dentro de los límites del render global y medir como máximo 2048 bloques de lado. Se conserva un texel por bloque, con el mismo hillshading y paleta aproximada de materiales de la comparación 1 × 1, escala vertical 1 y sin desenfoque. El exportador nunca reduce esta textura; las columnas transparentes y los materiales sin color mantienen visible el fondo, sin el magenta del diagnóstico local. `--style` controla el fondo global; el detalle siempre usa materiales y hillshading.

El resource pack contiene dos texturas: el fondo global y el detalle. El shader consulta el detalle únicamente dentro de sus límites y toma el texel del bloque correspondiente, sin filtrado entre bloques. Conserva la proyección, los límites globales, el marcador, los controles y las escalas 1024/2048/4096. Añade una consulta de textura por píxel dentro del recorte; los FPS y la legibilidad en el cliente siguen pendientes de validación. El borde entre colores de bioma y materiales puede ser visible, y la vegetación conserva el ruido de altura observado en la comparación.

Regenera e instala ambos packs de la misma revisión al incorporar este sampler y sus uniformes. El servidor debe distribuir el ZIP nuevo y actualizar su `resource-pack-sha1`; reconecta el cliente para descargarlo. La ampliación 1 × 1 al mundo completo requiere mosaicos/LOD y sigue pendiente.

## Instalar y probar

1. Pon `vanilla-map-post-datapack.zip` en `datapacks/` de un mundo de prueba y arráncalo.
2. Activa `vanilla-map-post-resources.zip` en el cliente o distribúyelo desde el servidor. Si usas `resource-pack-sha1`, actualízalo con el hash del ZIP.
3. En primera persona y en el Overworld, ejecuta **`/trigger vmp_map`** para abrir el mapa. Ciérralo con **Mayús** (la tecla que tengas asignada a agacharte) o repite el comando.
4. Sin caminar, mueve el ratón en horizontal y vertical. Comprueba que aparece el punto azul y que la vista vuelve a centrarse en tu posición al cerrar y abrir el mapa.
5. El mapa abre en el máximo acercamiento, con 1024 bloques de alto. Gira la rueda hacia abajo para ver 2048 y 4096 bloques, y hacia arriba para regresar hasta 1024. No permite acercarse más que la vista inicial. El zoom mantiene el centro de la vista y al reabrir el mapa vuelve a 1024.
6. Comprueba que las laderas y montañas se distinguen con el sombreado, que los biomas siguen siendo legibles y que el marcador permanece alineado en las tres escalas.

Un operador también puede probar la vista inicial del resource pack directamente con `/posteffect add @s vanilla_map_post:map_near` y quitarla con `/posteffect remove @s vanilla_map_post:map_near`.

El recorrido cubre toda la imagen exportada y se detiene en sus bordes. El datapack adapta el alcance y la sensibilidad al tamaño del mapa al generar los packs. Cada eje tiene hasta 65 535 posiciones disponibles; en un mapa de 8 192 bloques de lado, el paso transmitido es de aproximadamente un tercio de bloque.

El servidor sigue enviando el movimiento con sus ticks, normalmente 20 veces por segundo. El shader suaviza los pasos entre actualizaciones con un historial de dos píxeles. La latencia de red y la carga del servidor siguen influyendo en la respuesta. El encuadre parte de tu posición al reabrir el mapa.

Girar el ratón también cambia la dirección del personaje y el juego sigue permitiendo caminar. La rueda conserva su efecto normal sobre el objeto seleccionado y las teclas numéricas también pueden cambiar el zoom.
