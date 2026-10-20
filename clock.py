#!/usr/bin/env python3
"""Interactive ASCII analog + digital clock with alarms and a stopwatch.

Only the Python standard library is used. Rendering is done with ANSI escape
sequences; the analog dial is drawn onto a matrix (list of lists) of characters.
"""

import math
import select
import sys
import time

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    import msvcrt

# ---------------------------------------------------------------- constants
RADIUS = 10                 # dial radius in rows
X_SCALE = 2                 # terminal cells are ~2x taller than wide
CANVAS_H = 2 * RADIUS + 5
CANVAS_W = 2 * RADIUS * X_SCALE + 9
CENTER = (CANVAS_H // 2, CANVAS_W // 2)  # (row, col)
FRAME_DELAY = 0.05          # seconds between frames (key polling timeout)
ALARM_RING_SECONDS = 30

# Hand definitions: name -> (length ratio, character)
HANDS = {
    "hour": (0.5, "H"),
    "minute": (0.75, "M"),
    "second": (0.9, "."),
}

ANSI = {
    "clear": "\033[2J",
    "home": "\033[H",
    "clear_eol": "\033[K",
    "clear_below": "\033[J",
    "hide_cursor": "\033[?25l",
    "show_cursor": "\033[?25h",
    "alt_on": "\033[?1049h",
    "alt_off": "\033[?1049l",
    "bold": "\033[1m",
    "red": "\033[31m",
    "reverse": "\033[7m",
    "reset": "\033[0m",
}


# ------------------------------------------------------------ analog canvas
def new_canvas():
    """Create an empty canvas as a matrix of single-character strings."""
    return [[" "] * CANVAS_W for _ in range(CANVAS_H)]


def polar_to_cell(angle, radius):
    """Convert a clock angle (radians, 0 = 12 o'clock, clockwise) to (row, col)."""
    row = CENTER[0] - round(math.cos(angle) * radius)
    col = CENTER[1] + round(math.sin(angle) * radius * X_SCALE)
    return row, col


def put(canvas, row, col, char):
    if 0 <= row < CANVAS_H and 0 <= col < CANVAS_W:
        canvas[row][col] = char


def draw_hand(canvas, angle, length, char):
    """Draw a hand by sampling points along the ray from the center."""
    steps = int(length) * 2
    for i in range(1, steps + 1):
        row, col = polar_to_cell(angle, length * i / steps)
        put(canvas, row, col, char)


def draw_dial(canvas):
    """Draw the circle outline and the numbers 1..12."""
    for deg in range(0, 360, 3):
        row, col = polar_to_cell(math.radians(deg), RADIUS)
        put(canvas, row, col, "o" if deg % 30 == 0 else "·")
    for hour in range(1, 13):
        row, col = polar_to_cell(math.radians(hour * 30), RADIUS + 2)
        label = str(hour)
        start = col - len(label) // 2
        for i, ch in enumerate(label):
            put(canvas, row, start + i, ch)


def hand_angles(hours, minutes, seconds):
    """Return a dict of hand name -> angle in radians."""
    return {
        "second": math.radians(seconds * 6),
        "minute": math.radians((minutes + seconds / 60) * 6),
        "hour": math.radians(((hours % 12) + minutes / 60) * 30),
    }


def render_analog(now):
    canvas = new_canvas()
    draw_dial(canvas)
    angles = hand_angles(now.tm_hour, now.tm_min, now.tm_sec)
    for name in ("hour", "minute", "second"):  # later hands overwrite earlier
        ratio, char = HANDS[name]
        draw_hand(canvas, angles[name], RADIUS * ratio, char)
    put(canvas, CENTER[0], CENTER[1], "@")
    return ["".join(row) for row in canvas]


# ----------------------------------------------------------- application state
class State:
    """All mutable application state lives here."""

    def __init__(self):
        self.mode = "clock"                 # clock | alarm | stopwatch
        self.alarms = {}                    # "HH:MM" -> label
        self.ringing = None                 # "HH:MM" while ringing
        self.ring_started = 0.0
        self.last_bell = 0
        self.last_fired = None              # (key, yday) to avoid re-firing
        self.sw_running = False
        self.sw_elapsed = 0.0               # accumulated seconds
        self.sw_started_at = 0.0            # monotonic start of current run
        self.message = ""
        self.running = True

    # stopwatch ---------------------------------------------------------
    def stopwatch_value(self):
        if self.sw_running:
            return self.sw_elapsed + time.monotonic() - self.sw_started_at
        return self.sw_elapsed

    def stopwatch_toggle(self):
        if self.sw_running:
            self.sw_elapsed = self.stopwatch_value()
            self.sw_running = False
        else:
            self.sw_started_at = time.monotonic()
            self.sw_running = True

    def stopwatch_reset(self):
        self.sw_running = False
        self.sw_elapsed = 0.0

    # alarms ------------------------------------------------------------
    def add_alarm(self, text, label=""):
        key = parse_alarm_time(text)
        if key is None:
            self.message = "Invalid time. Use HH:MM (24h)."
            return
        self.alarms[key] = label or "Alarm"
        self.message = f"Alarm set for {key}."

    def remove_alarm(self, text):
        key = parse_alarm_time(text)
        if key in self.alarms:
            del self.alarms[key]
            self.message = f"Alarm {key} removed."
        else:
            self.message = "No such alarm."

    def check_alarms(self, now):
        key = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        stamp = (key, now.tm_yday)
        if key in self.alarms and self.last_fired != stamp:
            self.last_fired = stamp
            self.ringing = key
            self.ring_started = time.monotonic()
            self.last_bell = 0
        if self.ringing and time.monotonic() - self.ring_started > ALARM_RING_SECONDS:
            self.ringing = None


def parse_alarm_time(text):
    """Parse 'H:MM' / 'HH:MM' into a normalized 'HH:MM' string or None."""
    try:
        hh, mm = text.strip().split(":")
        hh, mm = int(hh), int(mm)
    except ValueError:
        return None
    if 0 <= hh < 24 and 0 <= mm < 60:
        return f"{hh:02d}:{mm:02d}"
    return None


def format_stopwatch(seconds):
    millis = int(seconds * 1000)
    h, rem = divmod(millis, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms // 10:02d}"


# ------------------------------------------------------------------ rendering
def build_frame(state, now):
    """Return the whole screen as a list of lines."""
    lines = render_analog(now)
    digital = time.strftime("%H:%M:%S", now)
    date = time.strftime("%A, %d %B %Y", now)

    lines.append("")
    lines.append(f"{ANSI['bold']}{digital:^{CANVAS_W}}{ANSI['reset']}")
    lines.append(f"{date:^{CANVAS_W}}")
    lines.append("")

    tabs = []
    for mode, key, name in (("clock", "C", "Clock"), ("alarm", "A", "Alarms"),
                            ("stopwatch", "S", "Stopwatch")):
        tab = f"[{key}] {name}"
        if state.mode == mode:
            tab = f"{ANSI['reverse']}{tab}{ANSI['reset']}"
        tabs.append(tab)
    lines.append("  ".join(tabs) + "  [Q] Quit")
    lines.append("-" * CANVAS_W)

    if state.mode == "alarm":
        lines.append("N: new alarm   D: delete alarm   X: silence")
        if state.alarms:
            for key in sorted(state.alarms):
                lines.append(f"  {key}  {state.alarms[key]}")
        else:
            lines.append("  (no alarms set)")
    elif state.mode == "stopwatch":
        lines.append("SPACE: start/pause   R: reset")
        status = "RUNNING" if state.sw_running else "PAUSED"
        lines.append(f"  {format_stopwatch(state.stopwatch_value())}  [{status}]")
    else:
        lines.append(f"Alarms set: {len(state.alarms)}")

    if state.ringing:
        blink = int(time.monotonic() * 2) % 2 == 0
        text = f"*** ALARM {state.ringing}: {state.alarms.get(state.ringing, '')} (press X) ***"
        style = ANSI["reverse"] + ANSI["red"] if blink else ANSI["bold"]
        lines.append(f"{style}{text}{ANSI['reset']}")
    elif state.message:
        lines.append(state.message)
    return lines


def draw(lines):
    """Overwrite the screen in place (no clear => no flicker)."""
    out = [ANSI["home"]]
    out.extend(line + ANSI["clear_eol"] + "\n" for line in lines)
    out.append(ANSI["clear_below"])
    sys.stdout.write("".join(out))
    sys.stdout.flush()


# ---------------------------------------------------------------------- input
class Terminal:
    """Context manager for raw-ish single-key input and the alternate screen."""

    def __enter__(self):
        if termios:
            self.saved = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        sys.stdout.write(ANSI["alt_on"] + ANSI["hide_cursor"] + ANSI["clear"])
        sys.stdout.flush()
        return self

    def __exit__(self, *exc):
        sys.stdout.write(ANSI["show_cursor"] + ANSI["alt_off"] + ANSI["reset"])
        sys.stdout.flush()
        if termios:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.saved)

    def read_key(self, timeout):
        """Return one lowercase key or None if nothing arrives in time."""
        if termios:
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            return sys.stdin.read(1).lower() if ready else None
        time.sleep(timeout)
        return msvcrt.getwch().lower() if msvcrt.kbhit() else None

    def prompt(self, text):
        """Temporarily restore normal line input to read a string."""
        sys.stdout.write(f"\033[{CANVAS_H + 14};1H{ANSI['show_cursor']}{text}")
        sys.stdout.flush()
        if termios:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.saved)
        try:
            answer = input()
        except EOFError:
            answer = ""
        if termios:
            tty.setcbreak(sys.stdin.fileno())
        sys.stdout.write(ANSI["hide_cursor"] + ANSI["clear"])
        return answer


def handle_key(state, term, key):
    if key == "q":
        state.running = False
    elif key == "x":
        state.ringing = None
    elif key == "c":
        state.mode = "clock"
    elif key == "a":
        state.mode = "alarm"
    elif key == "s":
        state.mode = "stopwatch"
    elif state.mode == "alarm" and key == "n":
        text = term.prompt("New alarm time (HH:MM): ")
        label = term.prompt("Label (optional): ") if parse_alarm_time(text) else ""
        state.add_alarm(text, label)
    elif state.mode == "alarm" and key == "d":
        state.remove_alarm(term.prompt("Alarm to delete (HH:MM): "))
    elif state.mode == "stopwatch" and key == " ":
        state.stopwatch_toggle()
    elif state.mode == "stopwatch" and key == "r":
        state.stopwatch_reset()


def main():
    if not sys.stdin.isatty():
        sys.exit("This program must be run in an interactive terminal.")
    state = State()
    with Terminal() as term:
        while state.running:
            now = time.localtime()
            state.check_alarms(now)
            if state.ringing and time.monotonic() - state.last_bell >= 1:
                sys.stdout.write("\a")
                state.last_bell = time.monotonic()
            draw(build_frame(state, now))
            key = term.read_key(FRAME_DELAY)
            if key:
                state.message = ""
                handle_key(state, term, key)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
