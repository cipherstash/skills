"""Tests for the examples that references/typing.md quotes."""

from typing import Any, Self, assert_type

import pytest

from practices.builder import Builder
from practices.cache import Cache
from practices.decorators import logging_decorator
from practices.exhaustive import handle_mode
from practices.guards import is_string_list
from practices.overloads import process
from practices.protocols import Circle, render
from practices.records import UserDict, create_user


class Squaring(Builder):
    """A builder subclass, to show that Self keeps its type through a base method."""

    def square(self) -> Self:
        return self.multiply(self._value)


def test_a_class_with_the_methods_satisfies_the_protocol() -> None:
    circle = Circle(2.0, "red")
    assert (render(circle), circle.color) == ("Drawing red circle", "red")


def test_a_typed_dict_key_may_be_missing(capsys: pytest.CaptureFixture[str]) -> None:
    with_age: UserDict = {"id": 1, "name": "Ada", "email": "ada@example.com", "age": 36}
    without_age: UserDict = {"id": 2, "name": "Grace", "email": "grace@example.com"}
    create_user(with_age)
    create_user(without_age)
    assert capsys.readouterr().out == "Ada\nGrace\n"


def test_a_chain_of_calls_returns_the_builder() -> None:
    assert Builder().add(2).multiply(3)._value == 6


def test_a_subclass_keeps_its_type_through_a_base_method() -> None:
    # add returns Self, so the Squaring method is still there after it.
    assert Squaring().add(3).square()._value == 9


def test_each_overload_returns_its_own_type() -> None:
    text: str = process("ab")
    number: int = process(21)
    assert (text, number) == ("AB", 42)


def test_every_mode_has_a_label() -> None:
    assert [handle_mode("read"), handle_mode("write")] == ["Reading", "Writing"]


def test_the_decorator_keeps_the_signature_and_reports_the_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    @logging_decorator
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, b=3) == 5
    assert capsys.readouterr().out == "Calling add\n"
    assert add.__name__ == "add"


def test_the_cache_holds_values_by_key() -> None:
    user_cache: Cache[int, str] = Cache()
    user_cache.set(1, "Alice")
    assert user_cache.get(1) == "Alice"
    assert user_cache.get(2) is None


def test_the_guard_narrows_to_a_list_of_strings() -> None:
    names: list[Any] = ["a", "b"]
    assert is_string_list(names)
    assert_type(names, list[str])


def test_the_guard_rejects_a_list_with_another_item() -> None:
    assert not is_string_list(["a", 1])
