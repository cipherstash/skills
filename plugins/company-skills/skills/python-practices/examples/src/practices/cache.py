"""A generic class in PEP 695 syntax."""


class Cache[K, V]:
    """Values of type V, stored by keys of type K."""

    def __init__(self) -> None:
        self._items: dict[K, V] = {}

    def get(self, key: K) -> V | None:
        return self._items.get(key)

    def set(self, key: K, value: V) -> None:
        self._items[key] = value
