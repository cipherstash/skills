"""A Protocol, and a class that satisfies it by its shape alone."""

from typing import Protocol


class Drawable(Protocol):
    """Anything with a draw method."""

    def draw(self) -> str: ...


class Circle:
    """A circle. It never names Drawable, and is one all the same."""

    def __init__(self, radius: float) -> None:
        self.radius = radius

    def draw(self) -> str:
        return f"circle of radius {self.radius}"


def render(shape: Drawable) -> str:
    """Draw any shape."""
    return shape.draw()
