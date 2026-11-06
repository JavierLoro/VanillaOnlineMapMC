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
- Consulta `ROADMAP.md` para las fases, prioridades y pruebas pendientes del mapa dentro del juego. Mantén sincronizado su estado con este archivo cuando cambie una validación o se implemente una función.

## Desarrollo actual del mapa dentro del juego

La rama activa para esta prueba es `feature/posteffect-world-map`. La integración en la rama por defecto debe seguir la tarea que indique el usuario.

- La plataforma de la prueba es Minecraft Java 26.3, con datapack y resource pack.
- La vista ocupa la pantalla, mantiene la cruceta y conserva visible la interfaz habitual, incluida la barra rápida.
- El modo de render web del exportador compone biomas y hillshading al 100 %, sin topografía adicional ni desenfoque; `--style biomes` conserva la vista plana. La prueba actual usa `--world-tiles`: mundo completo a 1 × 1 con materiales y hillshading a escala vertical 1, en mosaicos sin LOD. La vista sigue siendo cenital.
- `/trigger vmp_map` abre o cierra el mapa. La acción de agacharse, Mayús por defecto, también lo cierra. Si se abre con esa acción ya pulsada, el atajo se activa después de soltarla.
- El ratón desplaza el mapa. La rueda cambia entre cuatro escalas: 512, 1024, 2048 y 4096 bloques de alto por defecto. El mapa abre en 1024 y permite acercarse un nivel a 512. `--view-height` configura el encuadre inicial; los otros niveles muestran la mitad, el doble y el cuádruple. El cambio de ranura de la barra rápida sigue ocurriendo y las teclas numéricas pueden cambiar el zoom.
- El punto azul muestra la posición del jugador al desplazar la vista. Girar el ratón también gira al personaje y las teclas de movimiento siguen disponibles.
- El recorrido está calculado para cubrir la imagen exportada y detenerse en sus bordes. El shader suaviza las actualizaciones mediante un historial de dos píxeles.
- El servidor proporciona la entrada mediante sus ticks. La respuesta depende también de la latencia de red y de la carga del servidor.

Las ramas `feature/floating-world-map` y `feature/dialog-world-map` conservan experimentos anteriores. La implementación a pantalla completa de esta prueba está en `minecraft/posteffect/`.

## Estado de validación y próximos controles

El usuario validó la pantalla completa, el zoom, el desplazamiento con el ratón y el cierre con Mayús en las versiones anteriores de esta prueba.

El usuario también validó el recorrido completo, la respuesta en los bordes y la fluidez el 5 de noviembre de 2026, cerrando la fase 2 del roadmap. Las pruebas locales de servidor cubrieron movimiento fino, recorrido superior al antiguo límite, bordes y cambio de dirección, zoom, vistas independientes y limpieza al cerrar. El formato del efecto y la compilación de los shaders se comprobaron con las bibliotecas de Minecraft 26.3. La petición posterior de un zoom adicional incorpora 512 bloques de alto, manteniendo la apertura en 1024 y las escalas 2048/4096 para alejarse. La rueda se detiene en los extremos, y el nuevo efecto se limpia al cerrar. Su validación visual queda pendiente.

El clic derecho para recentrar y el clic izquierdo para seleccionar están pendientes de implementación. Los waypoints personales son una ampliación futura. La interfaz acordada conserva la barra rápida visible y los controles del mapa funcionan sin pulsar F1.

## Generación y comprobación de los packs

Desde la raíz del repositorio, con Python 3.11+ y Pillow:

```bash
python backend/export_posteffect_map.py --render-dir backend/map_images --output post-packs
```

- El render de entrada debe estar terminado. `map_base.png` y `tile_index.json.gz` deben corresponder a la misma generación.
- El estilo `relief` también requiere `map_hillshade.png` de esa generación. Se verifican dimensiones y fechas antes y después de exportar. `map_shade.png` no se utiliza. El estilo `biomes` solo requiere la base y el índice.
- El exportador incorpora al datapack las funciones `pan_config.mcfunction` y `limit_pan.mcfunction`, calculadas a partir de los límites del render.
- Cuando cambien el protocolo de píxeles, los shaders o los límites generados, regenera e instala ambos packs de la misma revisión.
- Comprueba que el zoom conserva el centro, que los bordes responden al invertir el ratón y que el marcador sigue alineado.
- Comprueba la limpieza de todos los efectos del mapa al cerrar y la independencia entre dos jugadores. Conserva los efectos que pertenezcan a otros sistemas.
- Distingue las pruebas de compilación, las pruebas del servidor y la validación visual del cliente al comunicar resultados.
- Prueba las invariantes del exportador con `python -B -m unittest discover -s tests -v`. El relieve cenital tiene comprobación de exportación y comparación de la imagen real; su validación visual dentro del juego sigue pendiente del usuario.

## Resolución del terreno e investigación pendiente

El visor web agrupa el terreno en celdas de 4 × 4 bloques. Su exportación global se reduce a 2048 píxeles por lado. El modo completo 1 × 1 genera mosaicos de hasta 4096 píxeles por lado sin reducirlos.

`backend/world_reader.py` comparte entre el backend y el extractor la lectura NBT, la normalización de estados antiguos y compactos de Java 26.3 (incluidas las envolturas con clave vacía) y la decodificación de índices una vez por sección y chunk. Conserva las propiedades de bloque. La paleta compartida del visor está en `backend/map_colors.py`.

`backend/extract_surface.py` extrae superficie 1 × 1 con formato versionado y arrays de Y real, índices de estado y validez: 5 bytes por columna. Cada ejecución vuelve a leer los chunks y rechaza archivos cambiados durante la lectura. El PNG diagnóstico muestra materiales sin color en magenta; el exportador de packs los deja transparentes para conservar el fondo global.

Se comprobó un recorte 512 × 512 completo de un mundo real, con caminos, construcciones y desnivel, a partir de una copia local autorizada. El lector web también procesó cuatro regiones completas sin errores, con datos antiguos y de Java 26.3. Fuente, coordenadas, informes e imágenes del mundo están en `backend/map_images/`, ignorados por Git; no publicarlos.

`backend/compare_surface.py` compara 4 × 4/1 × 1 desde el ZIP local: mismo encuadre, paleta de materiales, coeficientes de luz y escala vertical, con gradientes calculados en bloques físicos y sin desenfoque. La malla 4 × 4 promedia alturas y toma material en +1,+1, como el lector web. No reproduce la base de biomas instalada. La fórmula web exagera pendientes por cuatro al no corregir su espaciado; el comparador usa escala 1 por defecto y admite `--vertical-scale 4` para exagerar ambas vistas por igual. Genera vistas nativas, comparación completa y un detalle ampliado elegido por máxima cobertura de caminos en una malla fija; la selección queda registrada.

La comparación local muestra más detalle de caminos y construcciones a 1 × 1, con más ruido de sombreado de la vegetación. El informe incluye precisión y cobertura de caminos, tamaños de PNG y tiempos locales; no mide packs ni cliente. Los resultados permanecen en `backend/map_images/surface-comparison/`, ignorados por Git. El usuario aceptó la comparación visual y pidió instalarla.

`backend/export_posteffect_map.py --surface surface.zip` conserva el modo anterior de recorte 1 × 1 sobre un fondo global. El usuario pidió después probar el mundo completo a 1 × 1, sin LOD. `backend/render_world_map.py` lo genera desde una copia estable por ventanas, con un halo de altura de un bloque para evitar costuras de sombreado. Guarda mosaicos recortados en los bordes y un manifiesto versionado con hashes; este solo aparece al terminar y comprobar la fuente.

`backend/export_posteffect_map.py --world-tiles <directorio>` empaqueta el terreno completo sin fondo reducido ni recorte local. Valida hashes, dimensiones y cuadrícula; conserva los zooms 512/1024/2048/4096 y genera los límites desde el manifiesto. `minecraft/posteffect/world_map.fsh` es una plantilla: se genera una selección mediante árbol equilibrado y samplers con nombres constantes. Solo se consulta una textura de terreno por píxel, sin recorrer todos los mosaicos. Máximo 15 mosaicos más el sampler de estado; si se supera, falla sin reducir detalle. No se usa LOD. Los huecos y chunks incompletos quedan transparentes; los materiales sin color usan gris neutro. Actualizaciones del mundo requieren regeneración. El backend web instalado se conserva separado.

Prueba completa generada en ct111 desde una copia privada estable: seis mosaicos, un texel por bloque, 24,4 MB de resource pack y unos 339 MiB de pico de memoria del renderizador. Pasan 33 tests, incluidos costuras, bordes parciales, huecos, coordenadas negativas, hashes, zoom y presupuesto de samplers. El shader compiló y enlazó con los includes oficiales 26.3; se verificaron 256 píxeles reales con seis mosaicos y otros 256 con quince, recorriendo todas las texturas, transparencia, bordes y un origen negativo. Los uniformes int se contrastaron con el codec oficial. La prueba del servidor y la descarga del pack se verifican por separado; los FPS, la legibilidad y la memoria gráfica real del cliente siguen pendientes del usuario.

El siguiente paso es validar el mapa completo en el juego, incluidas las uniones y las cuatro escalas. Después sigue planificada la isométrica fija, tratando vegetación y copas antes de comprobar la proyección del marcador. La isométrica y el suelo bajo copas siguen pendientes; el LOD queda aplazado a una medición que lo justifique. Diorama y BlueMap son referencias. Mantén separadas extracción, compilación, prueba del servidor y validación visual.
