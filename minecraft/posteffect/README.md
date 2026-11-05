# Prueba del mapa a pantalla completa en Minecraft Java 26.3

El efecto toma el mapa del visor web y lo centra inicialmente en la cámara. Puedes desplazarte por el mapa con el ratón sin caminar. Un punto azul indica tu posición al apartar el mapa de la cruceta. Minecraft dibuja la cruceta y el resto del HUD encima.

## Generar los packs

Con Python 3.11+ y Pillow instalados, ejecuta desde la raíz del repositorio cuando haya terminado el render del visor.

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

La carpeta de render debe contener `map_base.png` y `tile_index.json.gz` de la misma generación. El encuadre inicial cubre 1024 bloques de alto por defecto. Usa `--view-height 512` para empezar con un recorte más cercano. Para cambiar la escala inicial o actualizar el terreno, regenera el resource pack.

## Instalar y probar

1. Pon `vanilla-map-post-datapack.zip` en `datapacks/` de un mundo de prueba y arráncalo.
2. Activa `vanilla-map-post-resources.zip` en el cliente o distribúyelo desde el servidor. Si usas `resource-pack-sha1`, actualízalo con el hash del ZIP.
3. En primera persona y en el Overworld, ejecuta **`/trigger vmp_map`** para abrir el mapa. Repite el comando para cerrarlo.
4. Sin caminar, mueve el ratón en horizontal y vertical. Comprueba que aparece el punto azul y que la vista vuelve a centrarse en tu posición al cerrar y abrir el mapa.
5. Gira la rueda hacia arriba para acercar y hacia abajo para alejar. Con la configuración por defecto, los tres niveles muestran 512, 1024 y 2048 bloques de alto. El zoom mantiene el centro de la vista y al reabrir el mapa vuelve al nivel intermedio.

Un operador también puede probar el resource pack directamente con `/posteffect add @s vanilla_map_post:map` y quitarlo con `/posteffect remove @s vanilla_map_post:map`.

El desplazamiento se actualiza con los ticks del servidor y en esta prueba está limitado a aproximadamente 1 000 bloques por eje con la escala inicial por defecto. Girar el ratón también cambia la dirección del personaje y el juego sigue permitiendo caminar. La rueda conserva su efecto normal sobre el objeto seleccionado y las teclas numéricas también pueden cambiar el zoom.
