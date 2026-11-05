# Instrucciones para agentes

## Idioma y forma de trabajo

- Explica el trabajo al usuario en español. Escribe el código y los comentarios internos nuevos en inglés.
- Realiza cambios pequeños y centrados en la tarea. Actualiza la documentación afectada cuando cambie una decisión de diseño.
- Comprueba la rama, el estado de Git y las instrucciones de los subdirectorios antes de editar. Conserva los cambios locales ajenos a la tarea.
- Contrasta la documentación con el código y comunica las discrepancias relevantes cuando afecten al trabajo solicitado.

## Proyecto y archivos de entrada

El visor web lee archivos de mundos Java y genera imágenes del terreno. El mapa dentro del juego se distribuye mediante datapack y resource pack para clientes vanilla.

- `backend/main.py` contiene el lector NBT/MCA, la caché por chunk y la generación de PNG e índice del terreno.
- `frontend/` contiene el visor web con Leaflet.
- `backend/export_posteffect_map.py` genera los packs del mapa a pantalla completa.
- `minecraft/posteffect/` contiene los shaders, las funciones del datapack y las instrucciones de instalación.
- Consulta `README.md` para el visor web y `minecraft/posteffect/README.md` para generar y probar los packs.

## Desarrollo actual del mapa dentro del juego

La rama activa para esta prueba es `feature/posteffect-world-map`. La integración en la rama por defecto debe seguir la tarea que indique el usuario.

- La plataforma de la prueba es Minecraft Java 26.3, con datapack y resource pack.
- La vista ocupa la pantalla, mantiene la cruceta y conserva visible la interfaz habitual, incluida la barra rápida.
- `/trigger vmp_map` abre o cierra el mapa. La acción de agacharse, Mayús por defecto, también lo cierra. Si se abre con esa acción ya pulsada, el atajo se activa después de soltarla.
- El ratón desplaza el mapa. La rueda cambia entre tres escalas. El cambio de ranura de la barra rápida sigue ocurriendo y las teclas numéricas pueden cambiar el zoom.
- El punto azul muestra la posición del jugador al desplazar la vista. Girar el ratón también gira al personaje y las teclas de movimiento siguen disponibles.
- El recorrido está calculado para cubrir la imagen exportada y detenerse en sus bordes. El shader suaviza las actualizaciones mediante un historial de dos píxeles.
- El servidor proporciona la entrada mediante sus ticks. La respuesta depende también de la latencia de red y de la carga del servidor.

Las ramas `feature/floating-world-map` y `feature/dialog-world-map` conservan experimentos anteriores. La implementación a pantalla completa de esta prueba está en `minecraft/posteffect/`.

## Estado de validación y próximos controles

El usuario validó la pantalla completa, el zoom, el desplazamiento con el ratón y el cierre con Mayús en las versiones anteriores de esta prueba.

La ampliación del recorrido, la mayor precisión y el suavizado se publicaron después de que el usuario indicara límites laterales y sensación de lag. Las pruebas locales de servidor cubrieron movimiento fino, recorrido superior al antiguo límite, bordes y cambio de dirección, zoom, vistas independientes y limpieza al cerrar. El formato del efecto y la compilación de los shaders se comprobaron con las bibliotecas de Minecraft 26.3. La fluidez visual de esta última revisión sigue pendiente de validación en el cliente del usuario.

El clic derecho para recentrar y el clic izquierdo para seleccionar están pendientes de implementación. Los waypoints personales son una ampliación futura. La interfaz acordada conserva la barra rápida visible y los controles del mapa funcionan sin pulsar F1.

## Generación y comprobación de los packs

Desde la raíz del repositorio, con Python 3.11+ y Pillow:

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

- El render de entrada debe estar terminado. `map_base.png` y `tile_index.json.gz` deben corresponder a la misma generación.
- El exportador incorpora al datapack las funciones `pan_config.mcfunction` y `limit_pan.mcfunction`, calculadas a partir de los límites del render.
- Cuando cambien el protocolo de píxeles, los shaders o los límites generados, regenera e instala ambos packs de la misma revisión.
- Comprueba que el zoom conserva el centro, que los bordes responden al invertir el ratón y que el marcador sigue alineado.
- Comprueba la limpieza de todos los efectos del mapa al cerrar y la independencia entre dos jugadores. Conserva los efectos que pertenezcan a otros sistemas.
- Distingue las pruebas de compilación, las pruebas del servidor y la validación visual del cliente al comunicar resultados.

## Resolución del terreno e investigación pendiente

El lector actual agrupa el terreno en celdas de 4 × 4 bloques y genera una imagen por capa. El exportador del juego limita la textura a 2048 píxeles por lado.

La resolución 1 × 1, los distintos niveles de detalle y la vista inclinada o isométrica están en evaluación. Su primera prueba propuesta es un recorte de 512 × 512 bloques, comparando detalle, alineación del marcador y coste. Los repositorios Diorama, BlueMap y otros renderizadores son referencias sobre lectura y representación del mundo. La prueba de navegación y controles es la prioridad actual.

Al trabajar en la lectura de materiales, comprueba los estados de bloque compactos de Java 26.3 y la corrección existente en la rama del mapa flotante. Verifica su presencia en la rama de destino antes de dar por resuelta esa compatibilidad.
