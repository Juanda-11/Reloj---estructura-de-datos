# Reloj con Listas Circulares Dobles

Reloj analógico + digital para la consola, hecho solo con Python y construido sobre **listas circulares dobles** (Estructura de Datos). **No tiene ningún `import`**, no usa HTML ni CSS, y el código está en inglés. Todo está en un solo archivo: `clock.py`.

## Dónde se usa la lista circular doble
| Parte | Uso de la lista |
|-------|-----------------|
| **Carátula** | Anillo de 60 nodos (`Tick`). Cada manecilla (hora, minuto, segundo) es un cursor que recorre el anillo con `next`/`prev`, siempre por el camino más corto (pasar de 59 a 0 es un solo `next`). |
| **Zonas horarias** | Anillo de zonas; `N` va al nodo `next` y `P` al nodo `prev`. |
| **Alarmas** | Anillo ordenado por hora (`insert_sorted`); se elimina el nodo seleccionado en O(1) con `delete_node`. |
| **Vueltas del cronómetro** | Anillo de vueltas que se recorre en ambos sentidos. |

`CircularDoublyLinkedList` incluye lo visto en clase (`insert_at_beginning`, `insert_at_end`, `delete`, `print_list`) más `insert_sorted`, `delete_node`, `find`, recorrido hacia adelante (`iter`) y hacia atrás (`reversed`).

## Funcionalidades
- Reloj analógico a color (números 1-12, manecillas de hora, minuto y segundo), dígitos grandes y formato 24 h / 12 h.
- **Funcionalidad extra: reloj mundial** (zonas horarias con desfase fijo, sin horario de verano).
- Alarmas múltiples (crear, eliminar, activar/desactivar); al sonar parpadea un aviso y suena la campana de la terminal.
- Cronómetro con décimas de segundo y vueltas.
- Pruebas automáticas internas (opción 8 del menú).

## Ejecutar
```
python3 clock.py
```
Requiere Python 3.6+ y una terminal con colores ANSI (macOS/Linux, Windows Terminal). Tamaño de ventana recomendado: al menos 80 columnas × 30 filas.

## Cómo funciona sin `import`
Python no puede leer la hora del sistema ni pausar el programa sin importar un módulo, así que:
1. **Hora:** se escribe una vez (opción 2) y el reloj avanza contando *ticks* de 0,1 s.
2. **Espera:** cada tick espera con un bucle ocupado. Su duración depende del computador, por eso la opción 7 calibra la velocidad con un cronómetro real (por ejemplo, el de un celular) y guarda el resultado en `clock_calibration.txt`.
3. **Teclado:** con `input()` solo se lee cuando se pulsa Enter. El reloj corre en vivo y `Ctrl+C` (una excepción de Python, sin import) vuelve al menú.
4. **Matemáticas:** seno y coseno se calculan con la serie de Taylor, sin `math`.

Limitaciones: el tiempo solo avanza mientras el reloj o el cronómetro están abiertos (en los menús se detiene), por lo que la hora se ajusta justo antes de abrir el reloj; y la precisión depende de la calibración.

## Menú
| Opción | Acción |
|--------|--------|
| 1 | Abrir el reloj en vivo (`Ctrl+C` para volver) |
| 2 | Ajustar la hora actual y el desfase UTC |
| 3 | Zonas horarias (`N` siguiente, `P` anterior) |
| 4 | Alarmas (`A` añadir, `D` borrar, `E` activar/desactivar, `N`/`P` seleccionar) |
| 5 | Cronómetro (`S` iniciar/reanudar, `L` vuelta, `R` reiniciar, `N`/`P` recorrer vueltas) |
| 6 | Cambiar 12 h / 24 h |
| 7 | Calibrar velocidad |
| 8 | Ejecutar pruebas internas |
