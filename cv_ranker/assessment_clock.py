"""Explicit, per-run reference date shared by dated-role and model stages.

ContextVar isolates concurrent Streamlit workers, unlike a module-global date.
The clock is frozen once for a new run, and reused from the signed report on
resume; it must never depend on the day the reviewer reopens a checkpoint.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date
from typing import Iterator

_AS_OF: ContextVar[date | None] = ContextVar("textilehr_assessment_as_of", default=None)


def assessment_date() -> date:
    return _AS_OF.get() or date.today()


@contextmanager
def frozen_assessment_date(value: date) -> Iterator[None]:
    if type(value) is not date:
        raise TypeError("Assessment date must be a real date")
    token = _AS_OF.set(value)
    try:
        yield
    finally:
        _AS_OF.reset(token)
