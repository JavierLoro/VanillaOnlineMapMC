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

**Estado: investigación y prueba propuesta.**

- [ ] Incorporar y comprobar la compatibilidad del lector de materiales con los estados compactos de Java 26.3; existe una corrección en la rama del mapa flotante.
- [ ] Elegir un recorte de 512 × 512 bloques con un camino estrecho, una construcción y desnivel.
- [ ] Comparar representaciones 4 × 4 y 1 × 1 con el mismo encuadre y tratamiento visual.
- [ ] Medir generación, tamaño del pack y respuesta dentro del juego.
- [ ] Comprobar la alineación del marcador en distintas alturas.
- [ ] Valorar el detalle cercano y la vista inclinada según el resultado.

Diorama, BlueMap y los demás renderizadores investigados sirven como referencias para el proceso que convierte los datos del mundo en imágenes. Esta fase todavía requiere una decisión de implementación.

## Próxima comprobación

Regenerar e instalar ambos packs con relieve cenital y validarlo dentro del juego junto con el rango 1024/2048/4096. La fase 2 ya está validada. Después, implementar el clic derecho para recentrar.

Mantener sincronizados este roadmap y el estado de validación de `AGENTS.md` cuando se implemente una función o el usuario confirme una prueba.
