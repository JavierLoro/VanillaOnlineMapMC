# Prueba del mapa a pantalla completa en Minecraft Java 26.3

El efecto toma el mapa del visor web y lo centra inicialmente en la cámara. La vista cenital combina colores de bioma con sombreado suave de altura y pendientes para mostrar el relieve. Puedes desplazarte por el mapa con el ratón sin caminar. Un punto azul indica tu posición al apartar el mapa de la cruceta. Minecraft dibuja la cruceta y el resto del HUD encima.

## Generar los packs

Con Python 3.11+ y Pillow instalados, ejecuta desde la raíz del repositorio cuando haya terminado el render del visor.

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

La carpeta de render debe contener `map_base.png`, `map_shade.png`, `map_hillshade.png` y `tile_index.json.gz` de la misma generación terminada. El relieve se compone al exportar en una sola textura, conservando su transparencia y coordenadas. No añade pases ni cálculos por fotograma al shader. Si faltan las capas, el exportador lo indica; `--style biomes` permite generar la vista plana anterior usando solo la imagen base y el índice.

El encuadre inicial cubre 1024 bloques de alto por defecto y es el máximo acercamiento. `--view-height` fija ese encuadre mínimo; los otros niveles muestran el doble y el cuádruple de terreno. Al cambiar las escalas o actualizar el terreno, regenera e instala ambos packs.

Para comparar las dos vistas con el mismo render:

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-relief --style relief
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-biomes --style biomes
```

Las capas deben tener las mismas dimensiones que la base, no ser anteriores a ella y estar guardadas antes del índice. El exportador comprueba su coherencia y que no cambien durante la generación.

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
