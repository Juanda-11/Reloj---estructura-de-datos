#!/usr/bin/env python3
"""Console clock built on circular doubly linked lists. NO imports at all.

Python cannot read the system time without importing a module, so this clock
keeps its own time: you type the current time once and the clock advances by
counting ticks (1 tick = 1/10 s). Each tick waits with a busy loop whose length
is calibrated against a real stopwatch (menu option 7).

Where the circular doubly linked list is used:
  * the dial is a ring of 60 ticks; each hand is a cursor that walks the ring
    with ``next`` / ``prev`` (always the shortest way round),
  * the time zones form a ring you can browse in both directions,
  * the alarms form a ring kept sorted by time,
  * the stopwatch laps form a ring you can browse in both directions.

Run:  python3 clock.py   (any terminal with ANSI colors; Ctrl+C leaves a screen)
"""


# =========================================================================
#  Circular doubly linked list
# =========================================================================
class Node:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class CircularDoublyLinkedList:
    """Every node has ``prev`` and ``next``; ``head.prev`` is always the tail."""

    def __init__(self):
        self.head = None
        self.size = 0

    def __len__(self):
        return self.size

    def __iter__(self):
        """Traverse forward (``next``) from the head."""
        node = self.head
        for _ in range(self.size):
            yield node.data
            node = node.next

    def __reversed__(self):
        """Traverse backward (``prev``) from the tail."""
        node = self.head.prev if self.head else None
        for _ in range(self.size):
            yield node.data
            node = node.prev

    def is_empty(self):
        return self.head is None

    def nodes(self):
        """Yield the nodes themselves (not only their data), head first."""
        node = self.head
        for _ in range(self.size):
            yield node
            node = node.next

    # ------------------------------------------------------------ insertion
    def _insert_before(self, ref, new_node):
        """Link ``new_node`` between ``ref.prev`` and ``ref`` (list not empty)."""
        last = ref.prev
        new_node.prev = last
        new_node.next = ref
        last.next = new_node
        ref.prev = new_node

    def _insert_first(self, new_node):
        """First node of the list: it points to itself in both directions."""
        self.head = new_node
        new_node.next = new_node
        new_node.prev = new_node

    def insert_at_beginning(self, data):
        new_node = Node(data)
        if self.head is None:
            self._insert_first(new_node)
        else:
            self._insert_before(self.head, new_node)
            self.head = new_node
        self.size += 1
        return new_node

    def insert_at_end(self, data):
        new_node = Node(data)
        if self.head is None:
            self._insert_first(new_node)
        else:
            self._insert_before(self.head, new_node)  # before head == at the end
        self.size += 1
        return new_node

    def insert_sorted(self, data, key=lambda value: value):
        """Insert keeping the list ordered by ``key`` (stable for equal keys)."""
        if self.head is None or key(data) < key(self.head.data):
            return self.insert_at_beginning(data)
        node = self.head.next
        while node is not self.head and key(node.data) <= key(data):
            node = node.next
        new_node = Node(data)
        self._insert_before(node, new_node)  # node == head means "at the end"
        self.size += 1
        return new_node

    # ------------------------------------------------------------- deletion
    def delete_node(self, node):
        """Unlink ``node`` in O(1): this is where the ``prev`` pointer pays off."""
        if self.size == 1:
            self.head = None
        else:
            node.prev.next = node.next
            node.next.prev = node.prev
            if node is self.head:
                self.head = node.next
        node.prev = node.next = None
        self.size -= 1

    def delete(self, data):
        """Delete the first node holding ``data``. Return True if it existed."""
        node = self.find(data)
        if node is None:
            return False
        self.delete_node(node)
        return True

    # --------------------------------------------------------------- search
    def find(self, data):
        return self.find_by(lambda value: value == data)

    def find_by(self, predicate):
        for node in self.nodes():
            if predicate(node.data):
                return node
        return None

    # ------------------------------------------------------------- printing
    def print_list(self, reverse=False):
        if self.head is None:
            print("The list is empty.")
            return
        items = reversed(self) if reverse else iter(self)
        print(" <-> ".join(str(item) for item in items) + " <-> (back to start)")


# =========================================================================
#  Constants
# =========================================================================
TPS = 10                           # ticks per second (1 tick = 0.1 s)
TICKS_PER_DAY = 86400 * TPS
DIAL_TICKS = 60
PI = 3.141592653589793
RADIUS = 8                         # dial radius in rows
X_SCALE = 2                        # terminal cells are ~2x taller than wide
CANVAS_H = 2 * (RADIUS + 2) + 1
CANVAS_W = 2 * (RADIUS + 2) * X_SCALE + 3
CENTER = (CANVAS_H // 2, CANVAS_W // 2)  # (row, col)
SIDE_W = 33                        # width of the right-hand panel
INNER_W = CANVAS_W + 1 + SIDE_W    # width inside the outer frame
ALARM_RING_TICKS = 30 * TPS
DEFAULT_LOOPS_PER_SECOND = 40_000_000
CALIBRATION_FILE = "clock_calibration.txt"

CLEAR = "\033[2J\033[H"
HOME = "\033[H"
CLEAR_EOL = "\033[K"
CLEAR_BELOW = "\033[J"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
REVERSE = "\033[7m"


def fg(code):
    return f"\033[38;5;{code}m"


ORANGE, CYAN, RED, GREEN, YELLOW, GREY, WHITE, PURPLE = (
    fg(208), fg(45), fg(203), fg(78), fg(221), fg(244), fg(255), fg(141))

# name -> offset from UTC in minutes (None = the "Local" zone you configure).
# Fixed offsets: daylight saving time is not taken into account.
ZONES = [
    ("Local", None),
    ("UTC", 0),
    ("Bogota", -300),
    ("Mexico City", -360),
    ("Buenos Aires", -180),
    ("Madrid", 60),
    ("Moscow", 180),
    ("New Delhi", 330),
    ("Beijing", 480),
    ("Tokyo", 540),
    ("Sydney", 600),
]

BIG_DIGITS = {
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", "###", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    ":": [" ", "#", " ", "#", " "],
}


# =========================================================================
#  Math by hand (no ``math`` module)
# =========================================================================
def sin(x):
    """Sine using its Taylor series."""
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


# =========================================================================
#  Dial and hands
# =========================================================================
class Tick:
    """One of the 60 positions of the dial (one per second / minute)."""

    def __init__(self, index):
        angle = index * 2 * PI / DIAL_TICKS  # 0 = 12 o'clock, clockwise
        self.index = index
        self.ux = sin(angle)                 # unit vector: x to the right
        self.uy = cos(angle)                 # unit vector: y upwards
        self.is_hour = index % 5 == 0


def build_dial():
    ring = CircularDoublyLinkedList()
    for index in range(DIAL_TICKS):
        ring.insert_at_end(Tick(index))
    return ring


class Hand:
    """A clock hand: a cursor over the dial ring."""

    def __init__(self, dial, length_ratio, char, style):
        self.node = dial.head
        self.length = (RADIUS + 0.5) * length_ratio
        self.char = char
        self.style = style

    def move_to(self, index):
        """Walk the ring to ``index`` through the shortest direction."""
        forward = (index - self.node.data.index) % DIAL_TICKS
        if forward <= DIAL_TICKS // 2:
            for _ in range(forward):
                self.node = self.node.next
        else:
            for _ in range(DIAL_TICKS - forward):
                self.node = self.node.prev


def new_canvas():
    return [[" "] * CANVAS_W for _ in range(CANVAS_H)]


def put(canvas, row, col, char, style=""):
    if 0 <= row < CANVAS_H and 0 <= col < CANVAS_W:
        canvas[row][col] = f"{style}{char}{RESET}" if style else char


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
            put(canvas, row, col, "●", BOLD + WHITE)
        else:
            put(canvas, row, col, "·", GREY)
    for node in dial.nodes():
        tick = node.data
        if tick.is_hour:
            text = str(tick.index // 5 or 12)
            row, col = tick_cell(tick, RADIUS + 2)
            for i, ch in enumerate(text):
                put(canvas, row, col - len(text) // 2 + i, ch, BOLD + YELLOW)


def draw_hand(canvas, hand):
    tick = hand.node.data
    end = (CENTER[0] - round(tick.uy * hand.length),
           CENTER[1] + round(tick.ux * hand.length * X_SCALE))
    draw_line(canvas, CENTER, end, hand.char, hand.style)


def hand_indexes(hours, minutes, seconds):
    """Return (hour, minute, second) positions on the 60-tick dial."""
    return (hours % 12) * 5 + minutes // 12, minutes, seconds


# =========================================================================
#  Application state
# =========================================================================
class Alarm:
    def __init__(self, minutes, label):
        self.minutes = minutes      # minutes since midnight
        self.label = label
        self.enabled = True

    @property
    def key(self):
        return f"{self.minutes // 60:02d}:{self.minutes % 60:02d}"

    def __str__(self):
        mark = "ON " if self.enabled else "off"
        return f"{self.key}  [{mark}]  {self.label}"


class State:
    """All mutable application state lives here."""

    def __init__(self):
        self.ticks = 12 * 3600 * TPS        # local time, in ticks since midnight
        self.day = 0                        # days elapsed since the program started
        self.local_offset = -300            # minutes from UTC of the "Local" zone
        self.use_12h = False
        self.loops_per_second = DEFAULT_LOOPS_PER_SECOND
        self.dial = build_dial()
        self.hands = {
            "hour": Hand(self.dial, 0.5, "█", BOLD + ORANGE),
            "minute": Hand(self.dial, 0.78, "█", BOLD + CYAN),
            "second": Hand(self.dial, 0.92, "•", BOLD + RED),
        }
        self.zones = CircularDoublyLinkedList()
        for zone in ZONES:
            self.zones.insert_at_end(zone)
        self.zone = self.zones.head         # cursor on the zones ring
        self.alarms = CircularDoublyLinkedList()
        self.alarm_cursor = None            # cursor on the alarms ring
        self.ringing = None                 # Alarm currently ringing
        self.ring_left = 0
        self.last_fired = None              # (day, minute) to avoid re-firing
        self.laps = CircularDoublyLinkedList()
        self.lap_cursor = None
        self.sw_ticks = 0
        self.message = ""

    # time ----------------------------------------------------------------
    def set_time(self, seconds):
        self.ticks = seconds * TPS
        self.last_fired = None

    def advance(self, mode):
        """Advance the clock by one tick (and the stopwatch when it runs)."""
        self.ticks += 1
        if self.ticks >= TICKS_PER_DAY:
            self.ticks -= TICKS_PER_DAY
            self.day += 1
        if mode == "stopwatch":
            self.sw_ticks += 1

    def zone_offset(self, node=None):
        offset = (node or self.zone).data[1]
        return self.local_offset if offset is None else offset

    def zone_name(self, node=None):
        name, offset = (node or self.zone).data
        if offset is None:
            return f"Local (UTC{format_offset(self.local_offset)})"
        return f"{name} (UTC{format_offset(offset)})"

    def zone_ticks(self, node=None):
        """Return (ticks since midnight in that zone, day shift vs local)."""
        raw = self.ticks + (self.zone_offset(node) - self.local_offset) * 60 * TPS
        return raw % TICKS_PER_DAY, raw // TICKS_PER_DAY

    # alarms --------------------------------------------------------------
    def add_alarm(self, minutes, label):
        label = label or "Alarm"
        existing = self.alarms.find_by(lambda alarm: alarm.minutes == minutes)
        if existing:
            existing.data.label = label
            existing.data.enabled = True
            self.alarm_cursor = existing
        else:
            self.alarm_cursor = self.alarms.insert_sorted(
                Alarm(minutes, label), key=lambda alarm: alarm.minutes)
        self.message = f"Alarm set for {self.alarm_cursor.data.key}."

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
        self.alarm_cursor.data.enabled = not self.alarm_cursor.data.enabled

    def check_alarms(self):
        minute = self.ticks // (60 * TPS)
        if self.last_fired != (self.day, minute):
            node = self.alarms.find_by(lambda a: a.enabled and a.minutes == minute)
            if node:
                self.last_fired = (self.day, minute)
                self.ringing = node.data
                self.ring_left = ALARM_RING_TICKS
        if self.ringing:
            self.ring_left -= 1
            if self.ring_left <= 0:
                self.ringing = None

    # stopwatch -----------------------------------------------------------
    def add_lap(self):
        if self.sw_ticks <= 0:
            self.message = "Start the stopwatch first."
            return
        previous = self.laps.head.prev.data[1] if self.laps.head else 0
        number = len(self.laps) + 1
        self.lap_cursor = self.laps.insert_at_end(
            (number, self.sw_ticks, self.sw_ticks - previous))
        self.message = f"Lap {number} saved."

    def reset_stopwatch(self):
        self.sw_ticks = 0
        self.laps = CircularDoublyLinkedList()
        self.lap_cursor = None


# =========================================================================
#  Parsing and formatting
# =========================================================================
def parse_clock(text, allow_seconds):
    """Parse 'H:MM[:SS]' into seconds since midnight, or None."""
    parts = text.strip().split(":")
    if len(parts) not in ((2, 3) if allow_seconds else (2,)):
        return None
    try:
        values = [int(part) for part in parts]
    except ValueError:
        return None
    hours, minutes = values[0], values[1]
    seconds = values[2] if len(values) == 3 else 0
    if 0 <= hours < 24 and 0 <= minutes < 60 and 0 <= seconds < 60:
        return hours * 3600 + minutes * 60 + seconds
    return None


def parse_offset(text):
    """Parse a UTC offset in hours ('-5', '+5.5', '5:30') into minutes, or None."""
    text = text.strip().replace("+", "")
    try:
        if ":" in text:
            hours, minutes = text.split(":")
            sign = -1 if hours.strip().startswith("-") else 1
            total = int(hours) * 60 + sign * int(minutes)
        else:
            total = round(float(text) * 60)
    except ValueError:
        return None
    return total if -12 * 60 <= total <= 14 * 60 else None


def format_offset(minutes):
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    return f"{sign}{hours:02d}" + (f":{rest:02d}" if rest else "")


def split_ticks(ticks):
    seconds = ticks // TPS
    return seconds // 3600, seconds // 60 % 60, seconds % 60, ticks % TPS


def format_digital(hours, minutes, seconds, use_12h):
    if not use_12h:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    suffix = "AM" if hours < 12 else "PM"
    return f"{hours % 12 or 12:02d}:{minutes:02d}:{seconds:02d} {suffix}"


def format_stopwatch(ticks):
    hours, minutes, seconds, tenths = split_ticks(ticks)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{tenths}"


# =========================================================================
#  Rendering
# =========================================================================
def visible_len(text):
    """Length of ``text`` ignoring ANSI escape sequences."""
    length, in_escape = 0, False
    for ch in text:
        if in_escape:
            in_escape = ch != "m"
        elif ch == "\033":
            in_escape = True
        else:
            length += 1
    return length


def pad(text, width):
    return text + " " * (width - visible_len(text))


def center(text, width, style=""):
    left = (width - visible_len(text)) // 2
    body = " " * left + text + " " * (width - visible_len(text) - left)
    return f"{style}{body}{RESET}" if style else body


def big_digits(text, style):
    """Render ``text`` (digits and colons) as 5 lines of block characters."""
    rows = []
    for row in range(5):
        pieces = [BIG_DIGITS[ch][row] for ch in text]
        rows.append(style + " ".join(pieces).replace("#", "█") + RESET)
    return rows


def render_dial(state, hours, minutes, seconds):
    canvas = new_canvas()
    draw_dial(canvas, state.dial)
    hour, minute, second = hand_indexes(hours, minutes, seconds)
    for name, index in (("hour", hour), ("minute", minute), ("second", second)):
        state.hands[name].move_to(index)
        draw_hand(canvas, state.hands[name])
    put(canvas, CENTER[0], CENTER[1], "◉", BOLD + WHITE)
    return ["".join(row) for row in canvas]


def render_side(state, mode):
    """Right-hand panel: time zone ring, big digits and a few status lines."""
    z_ticks, shift = state.zone_ticks()
    hours, minutes, seconds, _ = split_ticks(z_ticks)
    node = state.zone
    lines = [""]
    lines.append(center("WORLD TIME", SIDE_W, DIM))
    lines.append(center("  " + state.zone_name(node.prev), SIDE_W, GREY))
    lines.append(center("▸ " + state.zone_name(node), SIDE_W, BOLD + YELLOW))
    lines.append(center("  " + state.zone_name(node.next), SIDE_W, GREY))
    lines.append("")

    if mode == "stopwatch":
        h, m, s, _ = split_ticks(state.sw_ticks)
        digits = big_digits(f"{h:02d}:{m:02d}:{s:02d}", BOLD + CYAN)
        caption = "STOPWATCH RUNNING"
        caption_style = BOLD + CYAN
    else:
        digits = big_digits(f"{hours % 12 or 12:02d}:{minutes:02d}:{seconds:02d}"
                            if state.use_12h else
                            f"{hours:02d}:{minutes:02d}:{seconds:02d}", BOLD + GREEN)
        suffix = ("AM" if hours < 12 else "PM") if state.use_12h else ""
        day_tag = {1: "next day", -1: "previous day"}.get(shift, "")
        caption = "  ".join(part for part in (suffix, day_tag) if part)
        caption_style = DIM
    lines.extend(center(row, SIDE_W) for row in digits)
    lines.append(center(caption, SIDE_W, caption_style))
    lines.append("")
    set_alarms = sum(1 for alarm in state.alarms if alarm.enabled)
    lines.append(f" {DIM}Alarms{RESET}     {set_alarms} active / {len(state.alarms)} total")
    lines.append(f" {DIM}Stopwatch{RESET}  {format_stopwatch(state.sw_ticks)}")
    lines.append(f" {DIM}Format{RESET}     {'12 h' if state.use_12h else '24 h'}")
    return lines


def frame_box(top, body, bottom):
    out = ["╭" + "─" * INNER_W + "╮"]
    for line in top:
        out.append("│" + pad(line, INNER_W) + "│")
    out.append("├" + "─" * CANVAS_W + "┬" + "─" * SIDE_W + "┤")
    out.extend(body)
    out.append("├" + "─" * CANVAS_W + "┴" + "─" * SIDE_W + "┤")
    for line in bottom:
        out.append("│" + pad(line, INNER_W) + "│")
    out.append("╰" + "─" * INNER_W + "╯")
    return out


TITLE = "CIRCULAR DOUBLY LINKED LIST CLOCK"


def build_frame(state, mode):
    """Return the live screen as a list of lines."""
    z_ticks, _ = state.zone_ticks()
    hours, minutes, seconds, _ = split_ticks(z_ticks)
    left = render_dial(state, hours, minutes, seconds)
    side = render_side(state, mode)
    side += [""] * (CANVAS_H - len(side))
    body = ["│" + pad(a, CANVAS_W) + "│" + pad(b, SIDE_W) + "│"
            for a, b in zip(left, side)]

    if state.ringing:
        blink = (state.ring_left // (TPS // 2)) % 2 == 0
        text = f"*** ALARM {state.ringing.key}: {state.ringing.label} ***"
        style = REVERSE + RED if blink else BOLD + RED
        status = center(text, INNER_W, style)
    else:
        status = center("Ctrl+C: back to the menu", INNER_W, DIM)
    return frame_box([center(TITLE, INNER_W, BOLD + ORANGE)], body, [status])


def screen(title, rows, footer=""):
    """Full-width framed static screen (menus, lists)."""
    out = [CLEAR + "╭" + "─" * INNER_W + "╮",
           "│" + center(title, INNER_W, BOLD + ORANGE) + "│",
           "├" + "─" * INNER_W + "┤"]
    out.extend("│" + pad(row, INNER_W) + "│" for row in rows)
    if footer:
        out.append("├" + "─" * INNER_W + "┤")
        out.append("│" + pad(" " + footer, INNER_W) + "│")
    out.append("╰" + "─" * INNER_W + "╯")
    print("\n".join(out))


# =========================================================================
#  Live view (the clock running)
# =========================================================================
def delay(state):
    """Wait one tick with a busy loop (there is no sleep without imports)."""
    for _ in range(state.loops_per_second // TPS):
        pass


def run_live(state, mode):
    """Run the clock until Ctrl+C. ``mode`` is 'clock' or 'stopwatch'."""
    print(CLEAR + HIDE_CURSOR, end="")
    try:
        while True:
            state.check_alarms()
            lines = build_frame(state, mode)
            print(HOME + "\n".join(line + CLEAR_EOL for line in lines) + CLEAR_BELOW,
                  flush=True)
            if state.ringing and state.ticks % TPS == 0:
                print("\a", end="", flush=True)
            delay(state)
            state.advance(mode)
    except KeyboardInterrupt:
        pass
    finally:
        if state.ringing:
            state.ringing = None
            state.message = "Alarm silenced."
        print(SHOW_CURSOR + RESET + CLEAR, end="")


# =========================================================================
#  Menus
# =========================================================================
def ask(prompt):
    """Read a line; Ctrl+D / Ctrl+C are treated as an empty answer."""
    try:
        return input(f"{BOLD}{prompt}{RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def take_message(state):
    message, state.message = state.message, ""
    return [""] + ([f" {YELLOW}{message}{RESET}"] if message else [])


def action_set_time(state):
    screen("SET TIME", [
        "",
        " This clock cannot read the system time (no imports), so tell it",
        " what time it is now. It starts running when you open the clock.",
        "",
    ])
    seconds = parse_clock(ask(" Current local time (HH:MM or HH:MM:SS): "), True)
    if seconds is None:
        state.message = "Invalid time. Nothing changed."
        return
    offset = parse_offset(ask(
        f" Your UTC offset in hours [{state.local_offset / 60:g}]: ") or
        f"{state.local_offset / 60:g}")
    if offset is None:
        state.message = "Invalid UTC offset. Nothing changed."
        return
    state.set_time(seconds)
    state.local_offset = offset
    state.message = "Time set. Open the clock (1) right away."


def action_zones(state):
    while True:
        node = state.zone
        screen("TIME ZONES  (circular doubly linked list)", [
            "",
            center("  " + state.zone_name(node.prev), INNER_W, GREY),
            center("▸ " + state.zone_name(node), INNER_W, BOLD + YELLOW),
            center("  " + state.zone_name(node.next), INNER_W, GREY),
            "",
        ], "[N] next (node.next)   [P] previous (node.prev)   [B] back")
        choice = ask(" > ").lower()
        if choice == "n":
            state.zone = state.zone.next
        elif choice == "p":
            state.zone = state.zone.prev
        elif choice in ("b", ""):
            return


def alarm_rows(state):
    rows = [""]
    if state.alarms:
        for node in state.alarms.nodes():
            selected = node is state.alarm_cursor
            text = f" {'▸' if selected else ' '} {node.data}"
            rows.append(f"{REVERSE}{pad(text, INNER_W)}{RESET}" if selected else text)
    else:
        rows.append(f" {DIM}(no alarms set){RESET}")
    return rows


def action_alarms(state):
    while True:
        screen("ALARMS  (sorted circular doubly linked list)",
               alarm_rows(state) + take_message(state),
               "[A] add  [D] delete  [E] on/off  [N] next  [P] previous  [B] back")
        choice = ask(" > ").lower()
        if choice == "a":
            seconds = parse_clock(ask(" Alarm time (HH:MM, 24 h): "), False)
            if seconds is None:
                state.message = "Invalid time. Use HH:MM (24 h)."
            else:
                state.add_alarm(seconds // 60, ask(" Label (optional): "))
        elif choice == "d":
            state.delete_selected_alarm()
        elif choice == "e":
            state.toggle_selected_alarm()
        elif choice == "n" and state.alarm_cursor:
            state.alarm_cursor = state.alarm_cursor.next
        elif choice == "p" and state.alarm_cursor:
            state.alarm_cursor = state.alarm_cursor.prev
        elif choice in ("b", ""):
            return


def action_stopwatch(state):
    while True:
        rows = ["", center(format_stopwatch(state.sw_ticks), INNER_W, BOLD + CYAN), ""]
        if state.lap_cursor:
            number, total, split = state.lap_cursor.data
            rows.append(f" Lap {number}/{len(state.laps)}   total "
                        f"{format_stopwatch(total)}   split +{format_stopwatch(split)}")
        else:
            rows.append(f" {DIM}(no laps yet){RESET}")
        screen("STOPWATCH", rows + take_message(state),
               "[S] start/resume (Ctrl+C pauses)  [L] lap  [R] reset  "
               "[N]/[P] browse laps  [B] back")
        choice = ask(" > ").lower()
        if choice == "s":
            run_live(state, "stopwatch")
        elif choice == "l":
            state.add_lap()
        elif choice == "r":
            state.reset_stopwatch()
        elif choice == "n" and state.lap_cursor:
            state.lap_cursor = state.lap_cursor.next
        elif choice == "p" and state.lap_cursor:
            state.lap_cursor = state.lap_cursor.prev
        elif choice in ("b", ""):
            return


def action_calibrate(state):
    screen("CALIBRATE SPEED", [
        "",
        " The clock counts time with a busy loop, so its speed depends on your",
        " computer. To calibrate: start a stopwatch (e.g. on your phone) when",
        " you press Enter and stop it when DONE appears (about 10 seconds).",
        "",
    ])
    ask(" Press Enter to start... ")
    for second in range(1, 11):
        print(f" {second}/10", end="\r", flush=True)
        for _ in range(state.loops_per_second):
            pass
    print(f" {GREEN}DONE{RESET}  ")
    try:
        real = float(ask(" Seconds shown by your stopwatch: "))
    except ValueError:
        real = 0
    if real <= 0:
        state.message = "Calibration cancelled."
        return
    state.loops_per_second = max(1000, int(state.loops_per_second * 10 / real))
    save_calibration(state)
    state.message = f"Calibrated: {state.loops_per_second:,} loops per second."


def load_calibration(state):
    try:
        with open(CALIBRATION_FILE) as file:
            value = int(file.read().strip())
        if value > 0:
            state.loops_per_second = value
    except (OSError, ValueError):
        pass


def save_calibration(state):
    try:
        with open(CALIBRATION_FILE, "w") as file:
            file.write(str(state.loops_per_second))
    except OSError:
        state.message += " (could not save it to disk)"


def main_menu(state):
    z_ticks, _ = state.zone_ticks()
    hours, minutes, seconds, _ = split_ticks(z_ticks)
    rows = [
        "",
        f"  {BOLD}1{RESET}  Open the clock (live analog + digital)",
        f"  {BOLD}2{RESET}  Set the current time",
        f"  {BOLD}3{RESET}  Time zones",
        f"  {BOLD}4{RESET}  Alarms",
        f"  {BOLD}5{RESET}  Stopwatch and laps",
        f"  {BOLD}6{RESET}  Switch 12 h / 24 h",
        f"  {BOLD}7{RESET}  Calibrate speed",
        f"  {BOLD}8{RESET}  Run self-tests",
        f"  {BOLD}0{RESET}  Exit",
        "",
        f"  {DIM}Clock time ({state.zone_name()}):{RESET} "
        f"{format_digital(hours, minutes, seconds, state.use_12h)}",
        f"  {DIM}The time only advances while the clock or stopwatch is open.{RESET}",
    ]
    screen("MENU", rows + take_message(state))
    return ask(" Choose an option: ")


def main():
    state = State()
    load_calibration(state)
    while True:
        choice = main_menu(state)
        if choice == "1":
            run_live(state, "clock")
        elif choice == "2":
            action_set_time(state)
        elif choice == "3":
            action_zones(state)
        elif choice == "4":
            action_alarms(state)
        elif choice == "5":
            action_stopwatch(state)
        elif choice == "6":
            state.use_12h = not state.use_12h
        elif choice == "7":
            action_calibrate(state)
        elif choice == "8":
            run_self_tests()
            ask(" Press Enter to continue... ")
        elif choice in ("0", "q"):
            print(CLEAR + "Bye!")
            return


# =========================================================================
#  Self-tests (plain asserts: no unittest, because that needs an import)
# =========================================================================
def ring_is_consistent(lst):
    if lst.head is None:
        return len(lst) == 0
    node = lst.head
    for _ in range(len(lst)):
        if node.next.prev is not node or node.prev.next is not node:
            return False
        node = node.next
    return node is lst.head


def run_self_tests():
    lst = CircularDoublyLinkedList()
    for value in (1, 2, 3):
        lst.insert_at_end(value)
    lst.insert_at_beginning(0)
    assert list(lst) == [0, 1, 2, 3] and list(reversed(lst)) == [3, 2, 1, 0]
    assert ring_is_consistent(lst)
    for value in (0, 2, 3):
        assert lst.delete(value)
        assert ring_is_consistent(lst)
    assert list(lst) == [1] and lst.head.next is lst.head and lst.head.prev is lst.head
    assert lst.delete(1) and lst.is_empty() and not lst.delete(1)

    ordered = CircularDoublyLinkedList()
    for value in (5, 1, 3, 9, 0, 3):
        ordered.insert_sorted(value)
        assert ring_is_consistent(ordered)
    assert list(ordered) == [0, 1, 3, 3, 5, 9]

    assert abs(sin(PI / 6) - 0.5) < 1e-9 and abs(cos(PI) + 1) < 1e-9

    state = State()
    assert len(state.dial) == 60
    hand = state.hands["second"]
    for target in (58, 2, 30, 0):
        hand.move_to(target)
        assert hand.node.data.index == target
    assert hand_indexes(15, 30, 45) == (17, 30, 45)

    for text in ("07:30", "06:00", "22:15"):
        state.add_alarm(parse_clock(text, False) // 60, "x")
    assert [a.key for a in state.alarms] == ["06:00", "07:30", "22:15"]
    state.delete_selected_alarm()
    assert len(state.alarms) == 2 and ring_is_consistent(state.alarms)
    state.add_alarm(8 * 60 + 15, "wake up")
    state.set_time(8 * 3600 + 15 * 60)
    state.check_alarms()
    assert state.ringing and state.ringing.label == "wake up"
    state.ringing = None
    state.check_alarms()
    assert state.ringing is None

    state.set_time(23 * 3600 + 59 * 60 + 59)
    state.advance("clock")
    for _ in range(TPS - 1):
        state.advance("clock")
    assert state.ticks == 0 and state.day == 1

    state.set_time(22 * 3600)
    state.zone = state.zones.find_by(lambda z: z[0] == "Tokyo")
    ticks, shift = state.zone_ticks()
    assert shift == 1 and split_ticks(ticks)[:2] == (12, 0)  # UTC-5 -> UTC+9

    state.sw_ticks = 50
    state.add_lap()
    state.sw_ticks = 80
    state.add_lap()
    assert [lap[0] for lap in state.laps] == [1, 2] and state.lap_cursor.data[2] == 30

    assert parse_clock("8:05", False) == 8 * 3600 + 5 * 60
    assert parse_clock("25:00", False) is None and parse_clock("1:2:3", False) is None
    assert parse_offset("-5") == -300 and parse_offset("5:30") == 330
    assert format_digital(0, 5, 9, True) == "12:05:09 AM"

    for mode in ("clock", "stopwatch"):
        frame = build_frame(state, mode)
        assert len(frame) == CANVAS_H + 6
        assert all(visible_len(line) == INNER_W + 2 for line in frame)
    print(f"{GREEN}All self-tests passed.{RESET}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(SHOW_CURSOR + RESET)
