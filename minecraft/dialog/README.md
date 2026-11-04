# Prueba del mapa como diálogo en Minecraft Java 26.3

La prueba usa el render del visor web y un diálogo nativo. La imagen tiene 288 × 162 píxeles y la cuadrícula tiene 18 sectores clicables. El marcador blanco representa la posición del jugador cuando se abre o actualiza el diálogo.

## Generar los packs

Desde la raíz del repositorio, con Python 3.11+ y Pillow instalados, ejecuta este comando cuando el visor haya terminado su render.

```bash
python backend/export_dialog_map.py --render-dir backend/map_images --output dialog-packs
```

`--render-dir` apunta a la carpeta que contiene `map_base.png` y `tile_index.json.gz`. Si copias esos archivos desde otro equipo, usa los del mismo render y conserva sus fechas de modificación.

## Instalar y probar

1. Coloca `vanilla-map-dialog-datapack.zip` en `datapacks/` de un mundo de prueba y arráncalo.
2. Activa `vanilla-map-dialog-resources.zip` en el cliente. También puedes distribuirlo como pack del servidor. Si usas `resource-pack-sha1`, actualízalo con el hash del ZIP.
3. Pulsa **G → Open map**. Si hay otros diálogos registrados en G, elige primero **World map**. También puedes abrirlo con `/trigger vmd_action set 99`.
4. Haz clic en las esquinas y el centro de la imagen. Las columnas van de A a F de izquierda a derecha y las filas de 1 a 3 de arriba abajo. El sector aparece en la cabecera. Usa **Refresh position** para actualizar el marcador y **Clear selection** para limpiar la selección.
5. Repite la comprobación con dos escalas de interfaz. Anota cuánto espacio ocupa el mapa, qué parte se recorta y si la zona clicable coincide con lo que se dibuja.

El mapa cubre el Overworld. La posición se aproxima a una cuadrícula de 6 × 9 píxeles del mapa y se omite si el jugador queda fuera de la imagen exportada o está en otra dimensión. El sector seleccionado es individual. Esta prueba se centra en el encuadre, los clics y el marcador de posición.
