# Prueba del mapa a pantalla completa en Minecraft Java 26.3

El efecto toma el mapa del visor web y lo centra inicialmente en la cámara. La vista cenital combina colores de bioma con hillshading al 100 %, como la capa del visor web, sin topografía adicional ni desenfoque. Puedes desplazarte por el mapa con el ratón sin caminar. Una flecha azul marca tu posición actual y conserva la dirección en la que mirabas al abrir el mapa. Minecraft dibuja la cruceta y el resto del HUD encima; la flecha tiene contorno oscuro y se extiende más allá del centro para que se distinga con la cruceta visible.

La opción `--surface` añade un recorte de materiales y hillshading a resolución real 1 × 1 sobre el mapa completo. Fuera de ese recorte se conserva el fondo global. La vista continúa siendo cenital.

## Generar los packs

Con Python 3.11+ y Pillow instalados, ejecuta desde la raíz del repositorio cuando haya terminado el render del visor.

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

La carpeta de render debe contener `map_base.png`, `map_hillshade.png` y `tile_index.json.gz` de la misma generación terminada. El relieve se compone al exportar en una sola textura mediante multiplicación, conservando su transparencia y coordenadas. No utiliza `map_shade.png` ni añade pases o cálculos por fotograma al shader. Si falta la capa, el exportador lo indica; `--style biomes` permite generar la vista plana anterior usando solo la imagen base y el índice.

El encuadre inicial cubre 1024 bloques de alto por defecto. Un nivel adicional permite acercarse a 512 bloques; los otros niveles muestran 2048 y 4096. `--view-height` fija el encuadre inicial; las cuatro escalas muestran la mitad, el mismo, el doble y el cuádruple de terreno. Al cambiar las escalas o actualizar el terreno, regenera e instala ambos packs.

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

El resource pack contiene dos texturas: el fondo global y el detalle. El shader consulta el detalle únicamente dentro de sus límites y toma el texel del bloque correspondiente, sin filtrado entre bloques. Conserva la proyección, los límites globales, el marcador y los controles. Las escalas son 512/1024/2048/4096, con apertura en 1024. Añade una consulta de textura por píxel dentro del recorte; los FPS y la legibilidad en el cliente siguen pendientes de validación. El borde entre colores de bioma y materiales puede ser visible, y la vegetación conserva el ruido de altura observado en la comparación.

Regenera e instala ambos packs de la misma revisión al incorporar este sampler y sus uniformes. El servidor debe distribuir el ZIP nuevo y actualizar su `resource-pack-sha1`; reconecta el cliente para descargarlo. Para cubrir todo el mundo a 1 × 1, utiliza el modo de mosaicos descrito a continuación.

## Mundo completo a 1 × 1

Genera desde una copia estable del directorio que contiene `region/`, con Pillow y las dependencias del proyecto:

```bash
python -B backend/render_world_map.py --world /path/to/stable/overworld --output backend/map_images/world-1x1
python -B backend/export_posteffect_map.py --world-tiles backend/map_images/world-1x1 --output post-world-packs
```

`--world-tiles` sustituye el fondo y el recorte por el terreno completo, con materiales y hillshading a escala vertical 1. No utiliza LOD ni reduce imágenes al alejarse. Conserva los cuatro zooms, el marcador y los controles. Los huecos sin superficie y los chunks que no estén completos permanecen transparentes; los materiales sin color usan gris neutro. Las fronteras se calculan desde los chunks asignados en las cabeceras de las regiones, de modo que pueden incluir un margen de generación incompleta.

El renderizador procesa mosaicos de hasta 4096 bloques por lado, leyendo un halo de un bloque para mantener el mismo sombreado a ambos lados de cada unión. Recorta las texturas de los bordes a sus dimensiones reales. No mantiene el mundo entero como diccionarios ni como una imagen gigante. Guarda PNGs y `world-map.json`, con límites, tamaños, hashes y estadísticas; el manifiesto completo solo se publica al terminar y comprobar que la fuente no ha cambiado. Usa una carpeta de salida nueva en cada generación. Los datos e imágenes del mundo deben permanecer fuera de Git.

El exportador verifica cada imagen contra su hash y sus dimensiones antes de incorporarla. El shader calcula directamente el índice del mosaico y lo selecciona con un árbol de decisiones, con una sola lectura de terreno por píxel. Se admiten hasta 15 texturas de terreno, más la textura de estado, dentro del mínimo de 16 samplers de fragmento de OpenGL 3.3. Si el mundo supera ese presupuesto, la generación falla expresamente; no reduce la resolución ni omite terreno. Las texturas y los datos del pack siguen siendo estáticos: los cambios posteriores del mundo necesitan regeneración.

Instala ambos packs y actualiza `resource-pack-sha1`. Prueba las uniones, los bordes exteriores, el marcador y la fluidez en las cuatro escalas. El tamaño del ZIP, la generación y la memoria del servidor se miden aparte de la memoria gráfica y los FPS del cliente.

## Instalar y probar

1. Pon `vanilla-map-post-datapack.zip` en `datapacks/` de un mundo de prueba y arráncalo.
2. Activa `vanilla-map-post-resources.zip` en el cliente o distribúyelo desde el servidor. Si usas `resource-pack-sha1`, actualízalo con el hash del ZIP.
3. En primera persona y en el Overworld, ejecuta **`/trigger vmp_map`** para abrir el mapa. Ciérralo con **Mayús** (la tecla que tengas asignada a agacharte) o repite el comando.
4. Abre el mapa mirando en una dirección conocida. Comprueba la flecha antes de desplazar la vista, mueve el ratón y cambia de zoom: debe mantener la orientación de apertura. Cierra, mira en otra dirección y vuelve a abrir: la flecha debe actualizarse y la vista volver a centrarse en tu posición. Cada jugador conserva su propia orientación.
5. El mapa abre con 1024 bloques de alto. Gira la rueda hacia arriba para acercarte a 512 y hacia abajo para volver a 1024, 2048 y 4096. El zoom mantiene el centro de la vista y al reabrir el mapa vuelve a 1024. Comprueba que se detiene en 512 y 4096 y que el nivel nuevo desaparece al cerrar con Mayús.
6. Comprueba que las laderas y montañas se distinguen con el sombreado, que los biomas siguen siendo legibles y que el marcador permanece alineado en las cuatro escalas.

Un operador también puede probar la vista inicial del resource pack directamente con `/posteffect add @s vanilla_map_post:map_near` y quitarla con `/posteffect remove @s vanilla_map_post:map_near`.

El recorrido cubre toda la imagen exportada y se detiene en sus bordes. El datapack adapta el alcance y la sensibilidad al tamaño del mapa al generar los packs. Cada eje tiene hasta 65 535 posiciones disponibles; en un mapa de 8 192 bloques de lado, el paso transmitido es de aproximadamente un tercio de bloque.

El servidor sigue enviando el movimiento con sus ticks, normalmente 20 veces por segundo. El shader suaviza los pasos entre actualizaciones con un historial de dos píxeles. La latencia de red y la carga del servidor siguen influyendo en la respuesta. El encuadre parte de tu posición al reabrir el mapa.

Girar el ratón también cambia la dirección del personaje y el juego sigue permitiendo caminar. La rueda conserva su efecto normal sobre el objeto seleccionado y las teclas numéricas también pueden cambiar el zoom.

## Orientación del marcador

El datapack captura el yaw de cada jugador al abrir y lo redondea a 64 rumbos (pasos de 5,625 grados). El norte continúa arriba; yaw 0 apunta al sur, 90 al oeste, 180 al norte y −90 al este. Al desplazar la vista, la flecha sigue marcando la posición actual, con la orientación de apertura fija. Al cerrar se retira también su efecto de señal y al reabrir se captura el rumbo nuevo.

La señal de orientación usa el píxel 8 de la misma fila que los ocho dígitos de desplazamiento. `navigation.fsh` la conserva en el canal alfa del píxel de tiempo (128..191), manteniendo dos píxeles de historial y el mismo presupuesto de samplers. `player_marker.glsl` se incorpora a los dos shaders de mapa durante la exportación. El cálculo del marcador queda limitado a su pequeño rectángulo de pantalla. Este cambio de protocolo requiere regenerar e instalar ambos packs de la misma revisión.
