"""A Protocol, and a class that satisfies it by its shape alone."""

from typing import Protocol


class Drawable(Protocol):
    def draw(self) -> str: ...

    @property
    def color(self) -> str: ...


class Circle:
    def __init__(self, radius: float, color: str) -> None:
        self.radius = radius
        self._color = color

    def draw(self) -> str:
        return f"Drawing {self._color} circle"

    @property
    def color(self) -> str:
        return self._color


# Circle implements Drawable without inheriting
def render(shape: Drawable) -> str:
    return shape.draw()
