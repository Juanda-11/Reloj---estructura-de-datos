"""Circular doubly linked list (no imports needed).

Every node has two pointers, ``prev`` and ``next``. The list is circular: the
last node points to the first one and the first node points back to the last,
so ``head.prev`` is always the tail.
"""


class Node:
    def __init__(self, data):
        self.data = data
        self.prev = None
        self.next = None


class CircularDoublyLinkedList:
    def __init__(self):
        self.head = None
        self.size = 0

    def __len__(self):
        return self.size

    def __iter__(self):
        """Traverse forward (``next``) starting at the head."""
        node = self.head
        for _ in range(self.size):
            yield node.data
            node = node.next

    def __reversed__(self):
        """Traverse backward (``prev``) starting at the tail."""
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

    # --------------------------------------------------------------- insertion
    def _insert_before(self, ref, new_node):
        """Link ``new_node`` between ``ref.prev`` and ``ref`` (list not empty)."""
        last = ref.prev
        new_node.prev = last
        new_node.next = ref
        last.next = new_node
        ref.prev = new_node

    def _insert_first(self, new_node):
        """Insert into an empty list: the node points to itself both ways."""
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

    # ---------------------------------------------------------------- deletion
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

    # ------------------------------------------------------------------ search
    def find(self, data):
        for node in self.nodes():
            if node.data == data:
                return node
        return None

    def find_by(self, predicate):
        for node in self.nodes():
            if predicate(node.data):
                return node
        return None

    # ---------------------------------------------------------------- printing
    def print_list(self, reverse=False):
        if self.head is None:
            print("The list is empty.")
            return
        items = reversed(self) if reverse else iter(self)
        print(" <-> ".join(str(item) for item in items) + " <-> (back to start)")
