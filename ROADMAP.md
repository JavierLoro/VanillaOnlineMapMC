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

**Estado: ajuste del rango de zoom implementado; pendiente de validación visual. Después, clic derecho para recentrar.**

- [x] Conservar la vista inicial de 1024 bloques como máximo acercamiento y ofrecer 2048 y 4096 para alejarse.
- [ ] Validar el rango nuevo, el centro al cambiar de escala y el regreso a 1024 al reabrir.
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
- [ ] Validar dentro del juego legibilidad, sensación de relieve y alineación del marcador en las tres escalas.

## 6. Detalle por bloque y vista inclinada

**Estado: comparación aceptada por el usuario; detalle cenital 1 × 1 integrado e instalado en ct111. Validación en el juego e isométrica pendientes.**

- [x] Normalizar estados antiguos, compactos y envueltos de Java 26.3, conservando propiedades y decodificando cada sección una sola vez por chunk.
- [x] Convertir alturas a Y real en el extractor 1 × 1, con mínimo de dimensión explícito y máscara independiente para columnas ausentes. El contrato y la caché web 4 × 4 se conservan.
- [x] Extraer un recorte 512 × 512 de un mundo real con caminos, construcciones y desnivel; conservar sus datos e informes fuera de Git.
- [x] Guardar alturas, estados y máscara en arrays compactos con formato versionado, origen y resolución explícitos; generar una previsualización de materiales.
- [x] Comparar representaciones 4 × 4 y 1 × 1 con el mismo encuadre, paleta de materiales y hillshading calculado con separación física en bloques.
- [x] Integrar el recorte 1 × 1 sobre el mapa global, sin reducirlo ni alterar controles, límites o zoom.
- [x] Comprobar exportación, compilación gráfica y arranque del servidor con el pack instalado.
- [x] Medir el tamaño de los packs generados.
- [ ] Validar respuesta, legibilidad y transición al fondo global dentro del juego.
- [ ] Comprobar la alineación del marcador en distintas alturas.
- [ ] Valorar el detalle cercano y la vista inclinada según el resultado.

`backend/extract_surface.py` lee los chunks seleccionados de nuevo en cada ejecución, separado de la caché web. Se validó con una copia autorizada de cuatro regiones de un mundo real, incluyendo formatos antiguos y de Java 26.3, y un recorte completo de 512 × 512 con caminos, construcciones y desnivel. Los arrays ocupan 1,25 MiB sin comprimir. Las coordenadas, el contenido del mundo y los informes detallados permanecen fuera de Git. El lector web también procesó las cuatro regiones completas sin errores.

`backend/compare_surface.py` genera vistas nativas de 128 × 128 y 512 × 512, una comparación del encuadre completo y un detalle de 128 bloques ampliado por igual, elegido por máxima presencia de caminos en una malla fija de 32 bloques. Mantiene los mismos colores y coeficientes de luz en ambas vistas; el gradiente usa la distancia real entre muestras y escala vertical 1 por defecto, sin desenfoque. La fórmula web actual exagera pendientes por cuatro en la malla 4 × 4; `--vertical-scale 4` permite usar esa exageración en ambas vistas. Esta comparación de materiales no reproduce la base de biomas del pack instalado.

La comparación real muestra caminos y construcciones más definidos a 1 × 1 y más ruido de altura de la vegetación. El usuario aceptó el resultado y pidió instalarlo. Los informes locales conservan métricas de solapamiento de caminos, tamaños de PNG y tiempos; no miden FPS ni RAM máxima. La validación inicial de la comparación cubrió 23 tests.

`backend/export_posteffect_map.py --surface surface.zip` conserva el fondo global y añade una textura de detalle con un texel por bloque, materiales y hillshading a escala vertical 1, sin desenfoque. Fuera del recorte y en columnas ausentes o materiales sin color se mantiene el fondo. La prueba instalada en ct111 usa un recorte de 512 × 512; la conversión del mundo completo requiere mosaicos/LOD. Packs finales: datapack 5991 bytes y resource pack 1726440 bytes. Se actualiza `resource-pack-sha1`, conservando la URL del pack y los permisos.

Pasan 26 tests. El shader se compiló y enlazó con los includes oficiales de Minecraft 26.3 en OpenGL; se comprobaron bloques std140 y ocho píxeles de coordenadas, bordes y transparencia mediante render real. La prueba del servidor comprueba la invocación nueva y la descarga del pack; la validación visual del cliente está pendiente.

El siguiente paso es validar en el cliente el detalle, el marcador, los bordes del recorte y el zoom. Después sigue planificada la isométrica fija del mismo recorte, tratando vegetación y copas; Diorama y BlueMap continúan como referencias. La interfaz web instalada conserva su backend anterior.

## Próxima comprobación

Reconectar para descargar el pack actualizado y validar el detalle 1 × 1 dentro del mapa global, junto con el rango 1024/2048/4096. La fase 2 ya está validada. La isométrica y el clic derecho para recentrar siguen pendientes.

Mantener sincronizados este roadmap y el estado de validación de `AGENTS.md` cuando se implemente una función o el usuario confirme una prueba.
