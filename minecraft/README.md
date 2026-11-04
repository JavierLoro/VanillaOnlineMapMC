# Mapa flotante para Minecraft Java 26.3

El panel usa el mapa de biomas del Overworld que genera VanillaOnlineMapMC. Floating UI lo coloca frente al jugador. Otros jugadores pueden verlo y solo su propietario puede manejarlo. El datapack guarda los puntos por UUID en los datos del mundo.

## Generar los packs

Espera a que el visor web termine de renderizar el terreno. Desde la raíz del repo, con Python y Pillow instalados, ejecuta:

```bash
git clone https://github.com/Alumopper/Floating-UI.git /tmp/floating-ui
git -C /tmp/floating-ui checkout c4e53176bf3babdce089371173569378eb5f590a
python backend/export_minecraft.py \
  --floating-ui /tmp/floating-ui \
  --render-dir backend/map_images \
  --output /tmp/vanilla-map-packs
```

El exportador lee `map_base.png` y `tile_index.json.gz`. Si el backend corre en un contenedor o en otro equipo, copia los dos archivos del mismo render terminado, conservando sus fechas de modificación. La compilación local de Floating UI incluye ajustes de compatibilidad con 26.3.

## Instalar y abrir

1. En una **copia del mundo**, pon `floating-ui-datapack.zip` y `vanilla-map-datapack.zip` en `datapacks/`.
2. Activa `vanilla-map-resources.zip` en el cliente o sírvelo como el *resource pack* del servidor. Incluye las texturas de Floating UI.
3. Arranca el servidor o vuelve a abrir el mundo. En el Overworld, mira hacia una zona despejada y pulsa **G → Open map**. También puedes usar `/trigger vm_open set 1`. Si otro datapack usa G, elige primero **World map**.
4. Para actualizar el terreno, genera los packs de nuevo, reemplaza ambos paquetes de VanillaOnlineMapMC de la misma exportación y vuelve a abrir el mundo. Los puntos se conservan.

## Controles

| Control | Acción |
|---|---|
| Rueda o `+` / `-` | Cambia entre ×1, ×2 y ×4. Con la rueda, la siguiente vista se elige a partir del punto al que miras. |
| Mirar hacia un borde del panel | Cambia a la vista vecina en ×2 o ×4. |
| Clic izquierdo en el mapa | Selecciona un punto. |
| Clic derecho o `Home` | Recentra el zoom actual en tu posición. |
| `Here` / `Pin` | Guarda tu ubicación actual o el punto seleccionado. |
| `List` / `Del` | Recorre hasta 16 puntos guardados o borra el punto guardado activo. |
| Agacharse o `Exit` | Cierra el panel. |

El blanco indica tu posición, el azul la selección y el dorado los puntos guardados. El mapa abre en la vista general y navega entre vistas prerenderizadas. Floating UI interpreta la rueda a partir de los cambios de ranura de la barra rápida, así que las teclas numéricas también pueden cambiar el zoom. El panel se dibuja en el mundo y el terreno cercano puede taparlo. Prueba el campo de visión, los clics y la rueda con dos jugadores antes de instalarlo en el mundo principal.

Floating UI mantiene cuatro chunks cargados alrededor del origen del Overworld para sus entidades auxiliares. La integración retira sus propios paneles al cerrarlos, desconectarse o alejarse.
