"""Explicit data structures and algorithms used by LIVRE's DSA workbench."""
from typing import Any, Callable, Iterable


def normalize_isbn(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def resolve_book_lookup_key(raw_key: str) -> str:
    value = str(raw_key or "").strip()
    lower = value.casefold()
    if lower.startswith("id:"):
        return "id:" + str(int(value.split(":", 1)[1].strip()))
    if lower.startswith("isbn:"):
        return "isbn:" + normalize_isbn(value.split(":", 1)[1])
    if value.isdigit() and len(value) < 10:
        return "id:" + str(int(value))
    return "isbn:" + normalize_isbn(value)


class _ChainNode:
    __slots__ = ("key", "value", "next")
    def __init__(self, key: str, value: Any, next_node=None):
        self.key, self.value, self.next = key, value, next_node


class ChainedHashTable:
    """Separate-chaining hash table with a polynomial string hash."""
    def __init__(self, capacity: int = 67):
        self.capacity = max(3, int(capacity))
        self._buckets = [None] * self.capacity
        self.size = 0
        self.collisions = 0

    @staticmethod
    def _normalize(key: Any) -> str:
        return str(key).strip().casefold()

    def _index(self, key: str) -> int:
        value = 0
        for char in key:
            value = (value * 31 + ord(char)) % self.capacity
        return value

    def insert(self, key: Any, value: Any) -> None:
        normalized = self._normalize(key)
        if not normalized:
            raise ValueError("A non-empty hash-table key is required.")
        index = self._index(normalized)
        node = self._buckets[index]
        had_node = node is not None
        while node is not None:
            if node.key == normalized:
                node.value = value
                return
            node = node.next
        if had_node:
            self.collisions += 1
        self._buckets[index] = _ChainNode(normalized, value, self._buckets[index])
        self.size += 1

    def get_with_comparisons(self, key: Any):
        normalized = self._normalize(key)
        if not normalized:
            return None, 0
        node = self._buckets[self._index(normalized)]
        comparisons = 0
        while node is not None:
            comparisons += 1
            if node.key == normalized:
                return node.value, comparisons
            node = node.next
        return None, comparisons

    def get(self, key: Any, default=None):
        value, _ = self.get_with_comparisons(key)
        return default if value is None else value

    def __len__(self):
        return self.size


def build_book_hash_index(book_rows: Iterable[dict]) -> ChainedHashTable:
    rows = [dict(row) for row in book_rows]
    table = ChainedHashTable(max(67, len(rows) * 4 + 1))
    for book in rows:
        table.insert("id:" + str(int(book["id"])), book)
        isbn = normalize_isbn(book.get("isbn", ""))
        if isbn:
            table.insert("isbn:" + isbn, book)
    return table


class _BSTNode:
    __slots__ = ("key", "value", "left", "right")
    def __init__(self, key, value):
        self.key, self.value = key, value
        self.left = self.right = None


class BinarySearchTree:
    """Unbalanced BST keyed by (case-folded title, book ID)."""
    def __init__(self):
        self.root = None
        self.node_count = 0
        self.insert_comparisons = 0

    @staticmethod
    def key_for(book: dict):
        return (str(book.get("title", "")).casefold(), int(book.get("id", 0)))

    def insert(self, book: dict) -> None:
        item = dict(book)
        key = self.key_for(item)
        if self.root is None:
            self.root = _BSTNode(key, item)
            self.node_count = 1
            return
        node = self.root
        while True:
            self.insert_comparisons += 1
            if key == node.key:
                node.value = item
                return
            if key < node.key:
                if node.left is None:
                    node.left = _BSTNode(key, item)
                    self.node_count += 1
                    return
                node = node.left
            else:
                if node.right is None:
                    node.right = _BSTNode(key, item)
                    self.node_count += 1
                    return
                node = node.right

    def in_order(self):
        result, stack, node = [], [], self.root
        while node is not None or stack:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            result.append(node.value)
            node = node.right
        return result

    def height(self):
        def walk(node):
            if node is None:
                return 0
            return 1 + max(walk(node.left), walk(node.right))
        return walk(self.root)


def build_title_bst(book_rows: Iterable[dict]) -> BinarySearchTree:
    tree = BinarySearchTree()
    for row in book_rows:
        tree.insert(dict(row))
    return tree


class FIFOQueue:
    """Array-backed circular FIFO queue; enqueue and dequeue are O(1)."""
    def __init__(self, capacity: int = 64):
        if int(capacity) < 1:
            raise ValueError("Queue capacity must be at least one.")
        self.capacity = int(capacity)
        self._items = [None] * self.capacity
        self._front = 0
        self._size = 0

    def enqueue(self, item: Any) -> None:
        if self._size == self.capacity:
            raise OverflowError("The queue is full.")
        rear = (self._front + self._size) % self.capacity
        self._items[rear] = item
        self._size += 1

    def dequeue(self):
        if self._size == 0:
            return None
        item = self._items[self._front]
        self._items[self._front] = None
        self._front = (self._front + 1) % self.capacity
        self._size -= 1
        return item

    def peek(self):
        return None if self._size == 0 else self._items[self._front]

    def to_list(self):
        return [self._items[(self._front + i) % self.capacity] for i in range(self._size)]

    def __len__(self):
        return self._size


def merge_sort(items: Iterable[Any], key: Callable[[Any], Any] = lambda item: item):
    """Stable Merge Sort returning (sorted_items, number_of_key_comparisons)."""
    values = list(items)
    comparisons = 0

    def sort(part):
        nonlocal comparisons
        if len(part) <= 1:
            return part
        middle = len(part) // 2
        left, right = sort(part[:middle]), sort(part[middle:])
        merged, i, j = [], 0, 0
        while i < len(left) and j < len(right):
            comparisons += 1
            if key(left[i]) <= key(right[j]):
                merged.append(left[i]); i += 1
            else:
                merged.append(right[j]); j += 1
        merged.extend(left[i:]); merged.extend(right[j:])
        return merged

    return sort(values), comparisons
