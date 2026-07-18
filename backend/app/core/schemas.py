"""Shared Pydantic v2 base model for all request/response schemas (DESIGN §5.7).

Every domain schema (M1+) inherits from :class:`StrictSchema`, which turns on
Pydantic **strict mode** (``strict=True``) and **forbids unknown fields**
(``extra="forbid"``). Strict mode rejects lossy coercion — e.g. the string
``"1"`` is not silently turned into the ``int`` ``1``.

Strict mode also rejects *string* input for ``date``/``datetime``/``time``/
``UUID`` on Pydantic's **Python** validation path — and that is the path FastAPI
uses: it parses the JSON body into a ``dict`` and calls ``validate_python`` on
it, never ``validate_json``. JSON has no native temporal/UUID type, so an
ISO-8601 string is the only wire form for these — accepting it is not a lossy
coercion. Declare such fields with the lax aliases below (:data:`JsonDate`,
:data:`JsonDateTime`, :data:`JsonTime`, :data:`JsonUUID`); the per-field
``strict=False`` re-enables string parsing for *those* fields while the model
stays strict for primitives like ``int``/``bool``, where coercion is lossy.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Wire-format aliases for the types whose only JSON representation is a string.
# `strict=False` overrides the model-level strictness for the annotated field, so
# an ISO-8601 string validates on the Python path (the one FastAPI uses) instead
# of being rejected. Use these in domain schemas in place of the bare types.
JsonDate = Annotated[date, Field(strict=False)]
JsonDateTime = Annotated[datetime, Field(strict=False)]
JsonTime = Annotated[time, Field(strict=False)]
JsonUUID = Annotated[UUID, Field(strict=False)]

# ``Decimal``'s wire form is a JSON *number* (there is no JSON decimal type), so
# the same reasoning applies: accepting the parsed ``float``/``int`` is not a
# lossy coercion — Pydantic converts via ``str()``, so ``4.5`` becomes exactly
# ``Decimal("4.5")``. Used for the rating ``value`` (REQ §4.2).
JsonDecimal = Annotated[Decimal, Field(strict=False)]


class StrictSchema(BaseModel):
    """Base model enforcing the §5.7 strictness contract for every schema."""

    model_config = ConfigDict(strict=True, extra="forbid")
