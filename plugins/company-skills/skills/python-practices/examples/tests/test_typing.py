"""Tests for the examples that references/typing.md quotes."""

import logging

import pytest

from practices.builder import AuthRequest
from practices.cache import Cache
from practices.decorators import logged
from practices.exhaustive import Status, label
from practices.guards import join_names
from practices.overloads import double
from practices.protocols import Circle, render
from practices.records import User, contact


def test_a_class_with_the_method_satisfies_the_protocol() -> None:
    assert render(Circle(2.0)) == "circle of radius 2.0"


def test_a_typed_dict_key_may_be_missing() -> None:
    with_email: User = {"id": 1, "name": "Ada", "email": "ada@example.com"}
    without_email: User = {"id": 2, "name": "Grace"}
    assert contact(with_email) == "ada@example.com"
    assert contact(without_email) == "Grace"


def test_a_subclass_keeps_its_type_through_a_base_method() -> None:
    # with_header returns Self, so the AuthRequest method is still there after it.
    request = AuthRequest().with_header("Accept", "text/plain").with_token("t0k3n")
    assert request.headers == {"Accept": "text/plain", "Authorization": "Bearer t0k3n"}


def test_each_overload_returns_its_own_type() -> None:
    number: int = double(21)
    text: str = double("ab")
    assert (number, text) == (42, "abab")


def test_every_status_has_a_label() -> None:
    assert [label(status) for status in Status] == ["active", "suspended"]


def test_the_decorator_keeps_the_signature_and_logs_the_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    @logged
    def add(a: int, b: int) -> int:
        return a + b

    with caplog.at_level(logging.DEBUG, logger="practices.decorators"):
        assert add(2, b=3) == 5
    assert caplog.messages == ["calling add"]
    assert add.__name__ == "add"


def test_the_cache_holds_values_by_key() -> None:
    cache: Cache[str, int] = Cache()
    cache.set("a", 1)
    assert cache.get("a") == 1
    assert cache.get("b") is None


def test_the_guard_narrows_a_list_of_strings() -> None:
    assert join_names(["a", "b"]) == "a, b"


@pytest.mark.parametrize(
    ("value", "shown"),
    [(["a", 1], "['a', 1]"), ("ab", "'ab'"), (None, "None")],
    ids=["mixed list", "string", "none"],
)
def test_the_guard_leaves_anything_else_as_it_is(value: object, shown: str) -> None:
    assert join_names(value) == shown
