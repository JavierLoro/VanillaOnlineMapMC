# Roadmap del mapa dentro de Minecraft

Actualizado el 6 de noviembre de 2026. Rama de trabajo: `feature/posteffect-world-map`.

El objetivo es un mapa a pantalla completa para clientes vanilla de Minecraft Java 26.3, distribuido mediante datapack y resource pack, con posición del jugador, navegación, zoom y puntos personales. La barra rápida y la interfaz habitual permanecen visibles.

Las instrucciones para agentes están en [AGENTS.md](AGENTS.md). La generación e instalación de los packs se explica en [minecraft/posteffect/README.md](minecraft/posteffect/README.md).

## 1. Navegación básica

**Estado: validada por el usuario en las revisiones anteriores.**

- [x] Mapa a pantalla completa con cruceta.
- [x] Apertura y cierre mediante `/trigger vmp_map`.
- [x] Desplazamiento horizontal y vertical con el ratón.
- [x] Tres niveles de zoom mediante la rueda.
- [x] Marcador de posición del jugador al desplazar la vista.
- [x] Cierre con la acción de agacharse, Mayús por defecto.

## 2. Alcance, precisión y fluidez

**Estado: validada por el usuario el 5 de noviembre de 2026.**

- [x] Adaptar el alcance al tamaño de la imagen exportada.
- [x] Transmitir posiciones con mayor precisión.
- [x] Detener el recorrido en los bordes y responder al invertir el ratón.
- [x] Suavizar visualmente los pasos entre actualizaciones del servidor.
- [x] Comprobar en el servidor local recorrido, bordes, zoom, vistas independientes y cierre.
- [x] Validar en el cliente del usuario el recorrido completo, la respuesta en los bordes y la sensación de fluidez.

El servidor sigue proporcionando la entrada mediante sus ticks. La latencia de red y la carga del servidor forman parte de la comprobación de respuesta.

## 3. Completar los controles

**Estado: rango de zoom y flecha con orientación de apertura implementados; pendiente de validación visual. Después, clic derecho para recentrar.**

- [x] Conservar la apertura en 1024 y las escalas 2048/4096; añadir un cuarto nivel de 512 para acercarse, por petición posterior del usuario.
- [ ] Validar el rango nuevo, el centro al cambiar de escala y el regreso a 1024 al reabrir.
- [x] Sustituir el punto por una flecha visible al abrir y al navegar, conservando la dirección de apertura de cada jugador.
- [ ] Validar orientación, legibilidad bajo la cruceta, zoom, limpieza y rumbo nuevo al reabrir con dos jugadores.
- [ ] Clic derecho para volver a centrar el mapa en el jugador conservando el zoom.
- [ ] Clic izquierdo para seleccionar un punto o chunk y consultar sus coordenadas.
- [ ] Limpiar la selección al volver a pulsar sobre ella.
- [ ] Mostrar una leyenda de controles encima del mapa.
- [ ] Comprobar que los clics de la interfaz se capturan sin colocar bloques ni atacar.

## 4. Waypoints personales

**Estado: pendiente.**

- [ ] Guardar un punto seleccionado y darle un nombre.
- [ ] Listar, localizar y borrar los puntos guardados.
- [ ] Conservar los puntos de cada jugador entre sesiones.
- [ ] Mostrar a cada jugador sus propios marcadores.
- [ ] Validar el aislamiento entre jugadores.

## 5. Relieve cenital

**Estado: implementado; pendiente de validación visual en el cliente del usuario.**

- [x] Combinar colores de bioma con hillshading al 100 %, como en el visor web, sin topografía adicional ni desenfoque.
- [x] Conservar las coordenadas y la transparencia del terreno.
- [x] Generar una sola textura sin añadir trabajo por fotograma ni cambiar zoom o controles.
- [x] Mantener `--style biomes` para comparar con la vista plana.
- [x] Comprobar capas incoherentes y verificar que solo cambia la textura de los packs.
- [ ] Validar dentro del juego legibilidad, sensación de relieve y alineación del marcador en las cuatro escalas.

## 6. Detalle por bloque y vista inclinada

**Estado: mundo completo a 1 × 1 instalado en ct111, sin LOD. Descarga y arranque comprobados; validación en el cliente e isométrica pendientes.**

- [x] Normalizar estados antiguos, compactos y envueltos de Java 26.3, conservando propiedades y decodificando cada sección una sola vez por chunk.
- [x] Convertir alturas a Y real en el extractor 1 × 1, con mínimo de dimensión explícito y máscara independiente para columnas ausentes. El contrato y la caché web 4 × 4 se conservan.
- [x] Extraer un recorte 512 × 512 de un mundo real con caminos, construcciones y desnivel; conservar sus datos e informes fuera de Git.
- [x] Guardar alturas, estados y máscara en arrays compactos con formato versionado, origen y resolución explícitos; generar una previsualización de materiales.
- [x] Comparar representaciones 4 × 4 y 1 × 1 con el mismo encuadre, paleta de materiales y hillshading calculado con separación física en bloques.
- [x] Integrar el recorte 1 × 1 sobre el mapa global, sin reducirlo ni alterar controles, límites o zoom.
- [x] Generar y empaquetar el mundo completo a 1 × 1 en mosaicos, sin LOD, por petición del usuario.
- [x] Verificar continuidad del sombreado entre mosaicos y limitar la selección a una lectura de terreno por píxel.
- [x] Comprobar exportación, compilación gráfica y arranque del servidor con el pack instalado.
- [x] Medir el tamaño de los packs generados.
- [ ] Validar respuesta, legibilidad y transición al fondo global dentro del juego.
- [ ] Comprobar la alineación del marcador en distintas alturas.
- [ ] Valorar el detalle cercano y la vista inclinada según el resultado.

`backend/extract_surface.py` lee los chunks seleccionados de nuevo en cada ejecución, separado de la caché web. Se validó con una copia autorizada de cuatro regiones de un mundo real, incluyendo formatos antiguos y de Java 26.3, y un recorte completo de 512 × 512 con caminos, construcciones y desnivel. Los arrays ocupan 1,25 MiB sin comprimir. Las coordenadas, el contenido del mundo y los informes detallados permanecen fuera de Git. El lector web también procesó las cuatro regiones completas sin errores.

`backend/compare_surface.py` genera vistas nativas de 128 × 128 y 512 × 512, una comparación del encuadre completo y un detalle de 128 bloques ampliado por igual, elegido por máxima presencia de caminos en una malla fija de 32 bloques. Mantiene los mismos colores y coeficientes de luz en ambas vistas; el gradiente usa la distancia real entre muestras y escala vertical 1 por defecto, sin desenfoque. La fórmula web actual exagera pendientes por cuatro en la malla 4 × 4; `--vertical-scale 4` permite usar esa exageración en ambas vistas. Esta comparación de materiales no reproduce la base de biomas del pack instalado.

La comparación real muestra caminos y construcciones más definidos a 1 × 1 y más ruido de altura de la vegetación. El usuario aceptó el resultado y pidió instalarlo. Los informes locales conservan métricas de solapamiento de caminos, tamaños de PNG y tiempos; no miden FPS ni RAM máxima. La validación inicial de la comparación cubrió 23 tests.

El modo anterior `--surface surface.zip` se conserva para comparar un recorte con el fondo global. La prueba completa usa `backend/render_world_map.py` y `backend/export_posteffect_map.py --world-tiles <directorio>`. Procesa una copia estable por ventanas, con un halo de altura de un bloque, y guarda mosaicos de hasta 4096 píxeles sin reducción ni LOD. El manifiesto completo registra hashes y dimensiones. Los bordes se recortan a su tamaño real; huecos y chunks incompletos son transparentes y los materiales sin color usan gris neutro. El shader selecciona un solo sampler mediante un árbol equilibrado, con un máximo de 15 mosaicos más el estado. Si se supera el presupuesto, la generación falla expresamente.

Generación real en ct111: seis mosaicos, 229,9 segundos y unos 339 MiB de memoria máxima del renderizador. Imágenes PNG: 24833526 bytes; texturas RGBA: 223008768 bytes sin otros buffers del cliente. Packs con la flecha: datapack 6475 bytes y resource pack 24442804 bytes. Las texturas del terreno no cambian. Se conserva el zoom 512/1024/2048/4096 y se actualiza `resource-pack-sha1`. Las regiones, coordenadas, imágenes y manifiestos del mundo permanecen privados fuera de Git. Los cambios posteriores del mundo requieren otra generación.

La validación inicial del mundo completo cubrió 33 tests, incluidos continuidad entre mosaicos, bordes parciales, máscaras, corrupción, límites de samplers y las cuatro escalas. El shader compiló y enlazó con los includes oficiales 26.3 en OpenGL; se comprobaron bloques std140 y 256 píxeles renderizados para seis mosaicos y otros 256 para quince, visitando todos los samplers con coordenadas negativas, transparencia y bordes. Los valores int se contrastaron con el codec oficial. Esto no mide los FPS ni la memoria gráfica real del cliente. La invocación nueva del servidor y la descarga del pack se verifican por separado.

La flecha usa 64 rumbos capturados al abrir, independientes del yaw que mueve el mapa. Se transmite en un píxel de señal y se conserva en el alfa del píxel de tiempo, manteniendo el historial de dos píxeles. Se limpia al cerrar y se actualiza al reabrir. Pasan 36 tests; se comprobaron los 64 rumbos y la recuperación desde el historial mediante OpenGL y 266240 píxeles contrastados con una referencia (tolerancia 2/255), además de los mosaicos. Su legibilidad se revisó con una cruceta escalada en una previsualización.

El siguiente paso es validar en el cliente el mundo completo, la orientación fija y la reapertura de la flecha, las uniones y los cuatro zooms. Después sigue planificada la isométrica fija, tratando vegetación y copas; Diorama y BlueMap continúan como referencias. El LOD se aplaza hasta que una medición lo justifique. La interfaz web instalada conserva su backend anterior.

## Próxima comprobación

### Prueba solicitada de actualización dinámica

Implementado el modo optativo `--live-chunk-probe`: `/trigger vmp_live` transmite la superficie del chunk cargado donde se activa, con una ampliación en pantalla; `set 2` prueba un damero y `set 3` lo desactiva. Cuatro columnas por lote, cuatro ticks entre lotes, 64 lotes por vuelta (12,8 segundos a 20 TPS). Solo colores de material, sin hillshading dinámico. No descarga ni regenera packs durante las actualizaciones, no fuerza chunks y no detecta aún nuevas regiones automáticamente.

El receptor usa dos historiales alternos para sobrevivir al reordenamiento de efectos; comprueba Fletcher-16 y reconstruye grupos ausentes al repetir. La prueba añade 20 escritores y un sampler al mapa (máximo 14 mosaicos); se mantiene separada del modo normal. La generación inicial y su instalación requieren los dos packs de la misma revisión.

Pasan 40 tests, incluyendo el emisor generado, dos jugadores y la paleta. La comprobación OpenGL cubre 35360 píxeles de caché y 4096 de superposición, además de compilación de ambos shaders completos. En el servidor aislado 26.3 se verificaron la carga sin errores, el origen negativo, la lectura de superficie, el paquete nuevo tras cambiar un bloque y el damero, contrastados con el codificador de referencia. Pendientes: validación real con cliente, cambio de bloques, cuatro zooms, cierre, dos jugadores, FPS y tráfico. La prueba funcional no acredita rendimiento ni escalabilidad; la detección incremental y el hillshading dependen de ese resultado.

Reconectar para descargar el pack completo 1 × 1 y validar la flecha al abrir, su orientación fija al navegar, el rumbo nuevo al reabrir y la respuesta en las cuatro escalas. La fase 2 ya está validada. La isométrica y el clic derecho para recentrar siguen pendientes.

Mantener sincronizados este roadmap y el estado de validación de `AGENTS.md` cuando se implemente una función o el usuario confirme una prueba.
