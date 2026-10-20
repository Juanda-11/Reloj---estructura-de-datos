#!/usr/bin/env python3
"""Analog + digital terminal clock built on circular doubly linked lists.

Where the circular doubly linked list is used:
  * the dial is a ring of 60 ticks; each clock hand is a cursor that walks the
    ring with ``next`` / ``prev`` (always taking the shortest direction),
  * the world-time zones form a ring you can browse in both directions,
  * the alarms form a ring kept sorted by time,
  * the stopwatch laps form a ring you can browse in both directions.

The only imports are the standard-library modules needed to read the system
time and the keyboard. All the math (sine / cosine) is done by hand.
"""

import select
import sys
import time

try:
    import termios
    import tty
except ImportError:  # Windows
    termios = None
    import msvcrt

from circular_list import CircularDoublyLinkedList

# ---------------------------------------------------------------- constants
RADIUS = 10                  # dial radius in rows
X_SCALE = 2                  # terminal cells are ~2x taller than wide
CANVAS_H = 2 * RADIUS + 5
CANVAS_W = 2 * RADIUS * X_SCALE + 15
CENTER = (CANVAS_H // 2, CANVAS_W // 2)  # (row, col)
FRAME_DELAY = 0.05           # seconds between frames (key polling timeout)
ALARM_RING_SECONDS = 30
TICKS = 60
PI = 3.141592653589793

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
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "reverse": "\033[7m",
    "reset": "\033[0m",
}

# name -> offset from UTC in minutes (None = the computer's local time).
# Fixed offsets: daylight saving time is not taken into account.
ZONES = [
    ("Local", None),
    ("UTC", 0),
    ("UTC-05 Bogota", -300),
    ("UTC-06 Mexico City", -360),
    ("UTC-03 Buenos Aires", -180),
    ("UTC+01 Madrid", 60),
    ("UTC+03 Moscow", 180),
    ("UTC+05:30 New Delhi", 330),
    ("UTC+08 Beijing", 480),
    ("UTC+09 Tokyo", 540),
    ("UTC+10 Sydney", 600),
]


# ------------------------------------------------------------ math by hand
def sin(x):
    """Sine using its Taylor series (no ``math`` module)."""
    x = x % (2 * PI)
    if x > PI:
        x -= 2 * PI
    term, total = x, x
    for n in range(1, 12):
        term *= -x * x / ((2 * n) * (2 * n + 1))
        total += term
    return total


def cos(x):
    return sin(x + PI / 2)


# ------------------------------------------------------------ dial and hands
class Tick:
    """One of the 60 positions of the dial (one per second / minute)."""

    def __init__(self, index):
        angle = index * 2 * PI / TICKS  # 0 = 12 o'clock, clockwise
        self.index = index
        self.ux = sin(angle)            # unit vector: x to the right
        self.uy = cos(angle)            # unit vector: y upwards
        self.is_hour = index % 5 == 0


def build_dial():
    ring = CircularDoublyLinkedList()
    for index in range(TICKS):
        ring.insert_at_end(Tick(index))
    return ring


class Hand:
    """A clock hand: a cursor over the dial ring."""

    def __init__(self, dial, length_ratio, char, style):
        self.node = dial.head
        self.length = RADIUS * length_ratio
        self.char = char
        self.style = style

    def move_to(self, index):
        """Walk the ring to ``index`` through the shortest direction."""
        forward = (index - self.node.data.index) % TICKS
        if forward <= TICKS // 2:
            for _ in range(forward):
                self.node = self.node.next
        else:
            for _ in range(TICKS - forward):
                self.node = self.node.prev


def new_canvas():
    return [[" "] * CANVAS_W for _ in range(CANVAS_H)]


def put(canvas, row, col, char, style=""):
    if 0 <= row < CANVAS_H and 0 <= col < CANVAS_W:
        canvas[row][col] = f"{style}{char}{ANSI['reset']}" if style else char


def tick_cell(tick, radius):
    row = CENTER[0] - round(tick.uy * radius)
    col = CENTER[1] + round(tick.ux * radius * X_SCALE)
    return row, col


def draw_line(canvas, start, end, char, style):
    """Bresenham line between two (row, col) cells."""
    (r0, c0), (r1, c1) = start, end
    dr, dc = abs(r1 - r0), abs(c1 - c0)
    sr = 1 if r0 < r1 else -1
    sc = 1 if c0 < c1 else -1
    err = dc - dr
    while True:
        put(canvas, r0, c0, char, style)
        if (r0, c0) == (r1, c1):
            return
        e2 = 2 * err
        if e2 > -dr:
            err -= dr
            c0 += sc
        if e2 < dc:
            err += dc
            r0 += sr


def draw_dial(canvas, dial):
    for node in dial.nodes():
        tick = node.data
        row, col = tick_cell(tick, RADIUS)
        if tick.is_hour:
            put(canvas, row, col, "o", ANSI["bold"])
        else:
            put(canvas, row, col, ".", ANSI["dim"])
    for node in dial.nodes():
        tick = node.data
        if tick.is_hour:
            hour = tick.index // 5 or 12
            row, col = tick_cell(tick, RADIUS + 2)
            for i, ch in enumerate(str(hour)):
                put(canvas, row, col - len(str(hour)) // 2 + i, ch)


def draw_hand(canvas, hand):
    tick = hand.node.data
    end = (CENTER[0] - round(tick.uy * hand.length),
           CENTER[1] + round(tick.ux * hand.length * X_SCALE))
    draw_line(canvas, CENTER, end, hand.char, hand.style)


def hand_indexes(now):
    """Return (hour, minute, second) positions on the 60-tick dial."""
    return ((now.tm_hour % 12) * 5 + now.tm_min // 12, now.tm_min,
            min(now.tm_sec, 59))


# ----------------------------------------------------------- application state
class Alarm:
    def __init__(self, key, label):
        self.key = key              # "HH:MM"
        self.label = label
        self.enabled = True

    def __str__(self):
        mark = "ON " if self.enabled else "off"
        return f"{self.key} [{mark}] {self.label}"


class State:
    """All mutable application state lives here."""

    def __init__(self):
        self.mode = "clock"                 # clock | alarm | stopwatch
        self.use_12h = False
        self.dial = build_dial()
        self.hands = {
            "hour": Hand(self.dial, 0.5, "#", ANSI["bold"]),
            "minute": Hand(self.dial, 0.75, "*", ANSI["cyan"]),
            "second": Hand(self.dial, 0.9, ".", ANSI["red"] + ANSI["bold"]),
        }
        self.zones = CircularDoublyLinkedList()
        for zone in ZONES:
            self.zones.insert_at_end(zone)
        self.zone = self.zones.head         # cursor on the zones ring
        self.alarms = CircularDoublyLinkedList()
        self.alarm_cursor = None            # cursor on the alarms ring
        self.ringing = None                 # Alarm currently ringing
        self.ring_started = 0.0
        self.last_bell = 0
        self.last_fired = None              # (key, yday) to avoid re-firing
        self.laps = CircularDoublyLinkedList()
        self.lap_cursor = None
        self.sw_running = False
        self.sw_elapsed = 0.0               # accumulated seconds
        self.sw_started_at = 0.0            # monotonic start of current run
        self.message = ""
        self.running = True

    # time zones --------------------------------------------------------
    def zone_time(self, node=None):
        name, offset = (node or self.zone).data
        if offset is None:
            return time.localtime()
        return time.gmtime(time.time() + offset * 60)

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
        self.laps = CircularDoublyLinkedList()
        self.lap_cursor = None

    def stopwatch_lap(self):
        total = self.stopwatch_value()
        if total <= 0:
            return
        previous = self.laps.head.prev.data[1] if self.laps.head else 0.0
        number = len(self.laps) + 1
        self.lap_cursor = self.laps.insert_at_end((number, total, total - previous))

    # alarms ------------------------------------------------------------
    def add_alarm(self, text, label=""):
        key = parse_alarm_time(text)
        if key is None:
            self.message = "Invalid time. Use HH:MM (24h)."
            return
        label = label or "Alarm"
        existing = self.alarms.find_by(lambda alarm: alarm.key == key)
        if existing:
            existing.data.label = label
            existing.data.enabled = True
            self.alarm_cursor = existing
        else:
            self.alarm_cursor = self.alarms.insert_sorted(
                Alarm(key, label), key=lambda alarm: alarm.key)
        self.message = f"Alarm set for {key}."

    def delete_selected_alarm(self):
        node = self.alarm_cursor
        if node is None:
            self.message = "No alarm selected."
            return
        self.alarm_cursor = node.next if len(self.alarms) > 1 else None
        self.alarms.delete_node(node)
        self.message = f"Alarm {node.data.key} removed."

    def toggle_selected_alarm(self):
        if self.alarm_cursor is None:
            self.message = "No alarm selected."
            return
        alarm = self.alarm_cursor.data
        alarm.enabled = not alarm.enabled

    def check_alarms(self, now):
        key = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        stamp = (key, now.tm_yday)
        if self.last_fired != stamp:
            alarm = self.alarms.find_by(lambda a: a.enabled and a.key == key)
            if alarm:
                self.last_fired = stamp
                self.ringing = alarm.data
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


def format_digital(now, use_12h):
    if not use_12h:
        return f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
    suffix = "AM" if now.tm_hour < 12 else "PM"
    return f"{now.tm_hour % 12 or 12:02d}:{now.tm_min:02d}:{now.tm_sec:02d} {suffix}"


# ------------------------------------------------------------------ rendering
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def format_date(now):
    return (f"{DAYS[now.tm_wday]}, {now.tm_mday:02d} "
            f"{MONTHS[now.tm_mon - 1]} {now.tm_year}")


def centered(text, style=""):
    """Center ``text`` and apply ``style`` (padding is computed without escapes)."""
    padded = f"{text:^{CANVAS_W}}"
    return f"{style}{padded}{ANSI['reset']}" if style else padded


def render_analog(state, now):
    canvas = new_canvas()
    draw_dial(canvas, state.dial)
    hour, minute, second = hand_indexes(now)
    for name, index in (("hour", hour), ("minute", minute), ("second", second)):
        state.hands[name].move_to(index)
        draw_hand(canvas, state.hands[name])
    put(canvas, CENTER[0], CENTER[1], "@", ANSI["bold"])
    return ["".join(row) for row in canvas]


def zone_carousel(state):
    node = state.zone
    return (f"< {node.prev.data[0]}   "
            f"[ {node.data[0]} ]   "
            f"{node.next.data[0]} >")


def mode_lines(state):
    lines = []
    if state.mode == "alarm":
        lines.append("N: new   D: delete   E: on/off   , .: select   X: silence")
        if state.alarms:
            for node in state.alarms.nodes():
                pointer = ">" if node is state.alarm_cursor else " "
                style = ANSI["reverse"] if node is state.alarm_cursor else ""
                lines.append(f"{style}{pointer} {node.data}{ANSI['reset']}")
        else:
            lines.append("  (no alarms set)")
    elif state.mode == "stopwatch":
        lines.append("SPACE: start/pause   L: lap   R: reset   , .: browse laps")
        status = "RUNNING" if state.sw_running else "PAUSED"
        lines.append(centered(f"{format_stopwatch(state.stopwatch_value())}  [{status}]",
                              ANSI["bold"]))
        if state.lap_cursor:
            number, total, split = state.lap_cursor.data
            lines.append(f"Lap {number}/{len(state.laps)}: "
                         f"{format_stopwatch(total)} (+{format_stopwatch(split)})")
    else:
        lines.append("T: 12h/24h   , .: previous / next time zone")
        lines.append(centered(zone_carousel(state), ANSI["yellow"]))
        lines.append(f"Alarms set: {len(state.alarms)}")
    return lines


def build_frame(state):
    """Return the whole screen as a list of lines."""
    shown = state.zone_time()
    lines = render_analog(state, shown)
    lines.append("")
    lines.append(centered(format_digital(shown, state.use_12h), ANSI["bold"] + ANSI["green"]))
    lines.append(centered(format_date(shown)))
    lines.append(centered(state.zone.data[0], ANSI["dim"]))
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
    lines.extend(mode_lines(state))

    if state.ringing:
        blink = int(time.monotonic() * 2) % 2 == 0
        text = f"*** ALARM {state.ringing.key}: {state.ringing.label} (press X) ***"
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

    def prompt(self, text, row):
        """Temporarily restore normal line input to read a string."""
        sys.stdout.write(f"\033[{row};1H{ANSI['show_cursor']}{text}")
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


def browse(cursor, key):
    """Move a ring cursor: ``,`` goes to ``prev`` and ``.`` goes to ``next``."""
    if cursor is None:
        return None
    return cursor.prev if key == "," else cursor.next


def handle_key(state, term, key, prompt_row):
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
    elif state.mode == "clock" and key in ",.":
        state.zone = browse(state.zone, key)
    elif state.mode == "clock" and key == "t":
        state.use_12h = not state.use_12h
    elif state.mode == "alarm" and key in ",.":
        state.alarm_cursor = browse(state.alarm_cursor, key)
    elif state.mode == "alarm" and key == "n":
        text = term.prompt("New alarm time (HH:MM): ", prompt_row)
        label = term.prompt("Label (optional): ", prompt_row) if parse_alarm_time(text) else ""
        state.add_alarm(text, label)
    elif state.mode == "alarm" and key == "d":
        state.delete_selected_alarm()
    elif state.mode == "alarm" and key == "e":
        state.toggle_selected_alarm()
    elif state.mode == "stopwatch" and key in ",.":
        state.lap_cursor = browse(state.lap_cursor, key)
    elif state.mode == "stopwatch" and key == " ":
        state.stopwatch_toggle()
    elif state.mode == "stopwatch" and key == "l":
        state.stopwatch_lap()
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
            lines = build_frame(state)
            draw(lines)
            key = term.read_key(FRAME_DELAY)
            if key:
                state.message = ""
                handle_key(state, term, key, len(lines) + 2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
