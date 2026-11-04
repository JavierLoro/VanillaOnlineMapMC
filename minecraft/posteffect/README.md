# Prueba del mapa a pantalla completa en Minecraft Java 26.3

El efecto toma el mapa del visor web y lo centra en la cámara. En primera persona, la cruceta indica tu posición mientras caminas. El mapa mantiene su proporción cuando cambia el tamaño de la ventana y muestra un fondo oscuro donde termina el render. Minecraft dibuja la cruceta y el resto del HUD encima.

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
4. Camina en dirección norte y este y comprueba que la cruceta queda centrada en tu posición. Cambia el tamaño de la ventana para comprobar que el mapa cubre la vista y mantiene su proporción.
5. Gira la rueda hacia arriba para acercar y hacia abajo para alejar. Con la configuración por defecto, los tres niveles muestran 512, 1024 y 2048 bloques de alto. Al reabrir el mapa vuelves al nivel intermedio.

Un operador también puede probar el resource pack directamente con `/posteffect add @s vanilla_map_post:map` y quitarlo con `/posteffect remove @s vanilla_map_post:map`.

El encuadre sigue la posición de la cámara. El datapack detecta el cambio de ranura de la barra rápida. La rueda conserva su efecto normal sobre el objeto seleccionado y las teclas numéricas también pueden cambiar el zoom.
