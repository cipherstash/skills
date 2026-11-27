"""Tests for the examples that references/data-modelling.md quotes."""

import dataclasses
from pathlib import Path

import pytest

from practices.models import Point, ShoppingCart, Status, read_all


def test_a_frozen_dataclass_cannot_change() -> None:
    point = Point(3.0, 4.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        point.x = 1.0  # type: ignore[misc]  # The assignment is the error under test.
    assert point.distance(Point(0.0, 0.0)) == 5.0


def test_each_cart_gets_its_own_list() -> None:
    first, second = ShoppingCart(user_id=1), ShoppingCart(user_id=2)
    first.items.append("book")
    assert second.items == []


def test_an_enum_reads_its_value_back() -> None:
    assert Status("approved") is Status.APPROVED
    with pytest.raises(ValueError, match="'lost'"):
        Status("lost")


def test_exit_stack_reads_every_file(tmp_path: Path) -> None:
    paths = [tmp_path / "a.txt", tmp_path / "b.txt"]
    for path, text in zip(paths, ["one", "two"], strict=True):
        path.write_text(text, encoding="utf-8")
    assert read_all(paths) == ["one", "two"]


def test_exit_stack_raises_when_a_file_is_missing(tmp_path: Path) -> None:
    present = tmp_path / "present.txt"
    present.write_text("here", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        read_all([present, tmp_path / "missing.txt"])
