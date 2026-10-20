# ASCII Analog & Digital Clock

An interactive terminal clock written in pure Python (standard library only, no GUI or web technologies).

## Features
- **Analog clock**: circular dial with numbers 1-12 and hour (`H`), minute (`M`) and second (`.`) hands.
- **Digital clock**: `HH:MM:SS` plus the current date.
- **Alarm mode**: store several `HH:MM` alarms; when one fires, a flashing banner is shown and the terminal bell (`\a`) rings every second until silenced (`X`) or 30 seconds pass.
- **Stopwatch mode**: start/pause and reset, with centisecond precision.
- Flicker-free refresh: the cursor is moved home with ANSI escapes and each line is overwritten in place, on the alternate screen buffer.

## Run
```
python3 clock.py
```
Requires Python 3.6+ and an interactive terminal with ANSI support (Linux/macOS terminals, Windows Terminal).

## Controls
| Key | Action |
|-----|--------|
| `C` / `A` / `S` | Clock / Alarms / Stopwatch mode |
| `N` / `D` (alarm mode) | New alarm / delete alarm (asks for `HH:MM`) |
| `X` | Silence a ringing alarm |
| `SPACE` / `R` (stopwatch mode) | Start-pause / reset |
| `Q` or `Ctrl+C` | Quit |

## Architecture
- **Canvas**: a `list` of `list`s of single characters (`new_canvas`). `polar_to_cell` maps a clock angle and radius to a `(row, col)` tuple, stretching columns by 2 to compensate for tall terminal cells.
- **Hands**: the `HANDS` dictionary maps each hand to a `(length ratio, character)` tuple; `hand_angles` returns a dictionary of angles; `draw_hand` samples points along the ray.
- **State**: the `State` class holds the mode, an `alarms` dictionary (`"HH:MM"` -> label), ringing status and stopwatch counters.
- **Rendering**: `build_frame` composes the screen as a list of lines; `draw` writes it in a single pass.
- **Input**: `Terminal` is a context manager that enables single-key (cbreak) input with `select` for non-blocking polling, and restores the terminal on exit.
