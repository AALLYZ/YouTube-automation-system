"""Shared column helpers for models."""
from __future__ import annotations

import enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


def enum_col(py_enum: type[enum.Enum], **kw: Any) -> sa.Enum:
    """A VARCHAR + CHECK column that stores the enum *value* (not name)."""
    return sa.Enum(
        py_enum,
        native_enum=False,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
        length=40,
        **kw,
    )


def jsonb(**kw: Any) -> Any:
    return sa.Column(JSONB, **kw)


JSONBType = JSONB
