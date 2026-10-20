"""Tests: run with ``python3 -m unittest -v``."""

import time
import unittest

import clock
from circular_list import CircularDoublyLinkedList


def assert_ring_is_consistent(test, lst):
    """Every node must be the ``prev`` of its ``next`` and the list must close."""
    if lst.head is None:
        test.assertEqual(len(lst), 0)
        return
    node = lst.head
    for _ in range(len(lst)):
        test.assertIs(node.next.prev, node)
        test.assertIs(node.prev.next, node)
        node = node.next
    test.assertIs(node, lst.head)


class CircularListTests(unittest.TestCase):
    def make(self, *values):
        lst = CircularDoublyLinkedList()
        for value in values:
            lst.insert_at_end(value)
        return lst

    def test_insert_and_traverse_both_ways(self):
        lst = self.make(1, 2, 3)
        lst.insert_at_beginning(0)
        self.assertEqual(list(lst), [0, 1, 2, 3])
        self.assertEqual(list(reversed(lst)), [3, 2, 1, 0])
        assert_ring_is_consistent(self, lst)

    def test_single_node_points_to_itself(self):
        lst = self.make(7)
        self.assertIs(lst.head.next, lst.head)
        self.assertIs(lst.head.prev, lst.head)

    def test_delete_head_middle_tail_and_last(self):
        lst = self.make(1, 2, 3, 4)
        self.assertTrue(lst.delete(1))
        self.assertTrue(lst.delete(3))
        self.assertTrue(lst.delete(4))
        self.assertEqual(list(lst), [2])
        assert_ring_is_consistent(self, lst)
        self.assertTrue(lst.delete(2))
        self.assertTrue(lst.is_empty())
        self.assertFalse(lst.delete(2))

    def test_insert_sorted(self):
        lst = CircularDoublyLinkedList()
        for value in (5, 1, 3, 9, 0, 3):
            lst.insert_sorted(value)
            assert_ring_is_consistent(self, lst)
        self.assertEqual(list(lst), [0, 1, 3, 3, 5, 9])

    def test_print_list(self):
        self.make(1, 2).print_list()
        self.make(1, 2).print_list(reverse=True)
        CircularDoublyLinkedList().print_list()


class ClockTests(unittest.TestCase):
    def test_trigonometry(self):
        self.assertAlmostEqual(clock.sin(clock.PI / 6), 0.5, places=9)
        self.assertAlmostEqual(clock.cos(0), 1.0, places=9)
        self.assertAlmostEqual(clock.cos(clock.PI), -1.0, places=9)

    def test_dial_ring(self):
        dial = clock.build_dial()
        self.assertEqual(len(dial), 60)
        self.assertAlmostEqual(dial.head.data.uy, 1.0)              # 12 o'clock
        self.assertAlmostEqual(dial.head.next.next.data.ux, 0.2079, places=3)
        three = list(dial.nodes())[15].data                          # 3 o'clock
        self.assertAlmostEqual(three.ux, 1.0)
        self.assertAlmostEqual(three.uy, 0.0, places=9)

    def test_hand_takes_shortest_direction(self):
        dial = clock.build_dial()
        hand = clock.Hand(dial, 0.9, ".", "")
        hand.move_to(58)
        self.assertEqual(hand.node.data.index, 58)
        hand.move_to(2)
        self.assertEqual(hand.node.data.index, 2)
        hand.move_to(30)
        self.assertEqual(hand.node.data.index, 30)

    def test_hand_indexes(self):
        now = time.struct_time((2026, 10, 20, 15, 30, 45, 1, 293, 0))
        self.assertEqual(clock.hand_indexes(now), (3 * 5 + 2, 30, 45))

    def test_render_all_modes(self):
        state = clock.State()
        for mode in ("clock", "alarm", "stopwatch"):
            state.mode = mode
            lines = clock.build_frame(state)
            self.assertGreater(len(lines), clock.CANVAS_H)

    def test_zone_ring_wraps(self):
        state = clock.State()
        for _ in range(len(clock.ZONES)):
            state.zone = clock.browse(state.zone, ".")
        self.assertEqual(state.zone.data, clock.ZONES[0])
        state.zone = clock.browse(state.zone, ",")
        self.assertEqual(state.zone.data, clock.ZONES[-1])

    def test_alarms_sorted_edit_delete(self):
        state = clock.State()
        for text in ("07:30", "06:00", "22:15"):
            state.add_alarm(text, "x")
        self.assertEqual([a.key for a in state.alarms], ["06:00", "07:30", "22:15"])
        state.add_alarm("7:30", "renamed")
        self.assertEqual(len(state.alarms), 3)
        self.assertEqual(state.alarm_cursor.data.label, "renamed")
        state.delete_selected_alarm()
        self.assertEqual([a.key for a in state.alarms], ["06:00", "22:15"])
        state.add_alarm("99:99")
        self.assertIn("Invalid", state.message)

    def test_alarm_fires_once_per_minute(self):
        state = clock.State()
        state.add_alarm("08:15", "wake up")
        now = time.struct_time((2026, 10, 20, 8, 15, 5, 1, 293, 0))
        state.check_alarms(now)
        self.assertEqual(state.ringing.label, "wake up")
        state.ringing = None
        state.check_alarms(now)
        self.assertIsNone(state.ringing)

    def test_disabled_alarm_does_not_fire(self):
        state = clock.State()
        state.add_alarm("08:15")
        state.toggle_selected_alarm()
        state.check_alarms(time.struct_time((2026, 10, 20, 8, 15, 0, 1, 293, 0)))
        self.assertIsNone(state.ringing)

    def test_laps(self):
        state = clock.State()
        state.sw_elapsed = 5.0
        state.stopwatch_lap()
        state.sw_elapsed = 8.0
        state.stopwatch_lap()
        self.assertEqual([lap[0] for lap in state.laps], [1, 2])
        self.assertAlmostEqual(state.lap_cursor.data[2], 3.0)
        state.stopwatch_reset()
        self.assertTrue(state.laps.is_empty())

    def test_12h_format(self):
        now = time.struct_time((2026, 10, 20, 0, 5, 9, 1, 293, 0))
        self.assertEqual(clock.format_digital(now, True), "12:05:09 AM")
        self.assertEqual(clock.format_digital(now, False), "00:05:09")


if __name__ == "__main__":
    unittest.main()
