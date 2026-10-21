# Reloj con Listas Circulares Dobles

Reloj analógico + digital para la terminal, hecho solo con Python y construido sobre **listas circulares dobles** (Estructura de Datos). No usa HTML, CSS ni librerías externas; el código está en inglés.

## Dónde se usa la lista circular doble
| Parte | Uso de la lista |
|-------|-----------------|
| **Carátula** | Anillo de 60 nodos (`Tick`). Cada manecilla (hora, minuto, segundo) es un cursor que recorre el anillo con `next`/`prev`, siempre por el camino más corto (pasar de 59 a 0 es un solo `next`). |
| **Zonas horarias** | Anillo de zonas; `,` va al nodo `prev` y `.` al nodo `next`. |
| **Alarmas** | Anillo ordenado por hora (`insert_sorted`); se elimina el nodo seleccionado en O(1) con `delete_node`. |
| **Vueltas del cronómetro** | Anillo de vueltas que se puede recorrer en ambos sentidos. |

`circular_list.py` contiene `Node` y `CircularDoublyLinkedList` con lo visto en clase (`insert_at_beginning`, `insert_at_end`, `delete`, `print_list`) más `insert_sorted`, `delete_node`, `find`, recorrido hacia adelante (`iter`) y hacia atrás (`reversed`).

## Funcionalidades
- Reloj analógico (números 1-12, manecillas `#` hora, `*` minuto, `.` segundo) y reloj digital con fecha, en formato 24 h o 12 h (`T`).
- **Funcionalidad extra: reloj mundial** (zonas horarias con desfase fijo, sin horario de verano).
- Alarmas múltiples (crear, eliminar, activar/desactivar); al sonar parpadea un aviso y suena la campana de la terminal.
- Cronómetro con vueltas.

## Ejecutar
```
python3 clock.py
```
Requiere Python 3.6+ y una terminal interactiva con ANSI (Linux/macOS, Windows Terminal).

Pruebas: `python3 -m unittest -v`

## Controles
| Tecla | Acción |
|-------|--------|
| `C` / `A` / `S` | Reloj / Alarmas / Cronómetro |
| `,` / `.` | Elemento anterior / siguiente de la lista del modo actual |
| `T` (reloj) | 12 h / 24 h |
| `N` / `D` / `E` (alarmas) | Nueva / eliminar la seleccionada / activar-desactivar |
| `X` | Silenciar alarma |
| `ESPACIO` / `L` / `R` (cronómetro) | Iniciar-pausar / vuelta / reiniciar |
| `Q` o `Ctrl+C` | Salir |

## Sobre los imports
Python no puede leer la hora del sistema ni el teclado sin importar módulos de su biblioteca estándar (`time`, `select`, `termios`/`tty`), así que son los únicos imports. Seno y coseno se calculan a mano (serie de Taylor), sin `math`.

## Estructura
- `circular_list.py`: lista circular doble.
- `clock.py`: carátula, estado, alarmas, cronómetro e interfaz de terminal.
- `test_clock.py`: pruebas unitarias.
