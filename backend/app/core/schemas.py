"""Shared Pydantic v2 base model for all request/response schemas (DESIGN §5.7).

Every domain schema (M1+) inherits from :class:`StrictSchema`, which turns on
Pydantic **strict mode** (``strict=True``) and **forbids unknown fields**
(``extra="forbid"``). Strict mode rejects lossy coercion — e.g. the string
``"1"`` is not silently turned into the ``int`` ``1``.

ISO-8601 strings remain valid for ``date``/``datetime``/``UUID`` because HTTP
request bodies arrive as JSON, and Pydantic accepts those string forms on the
JSON validation path even under strict mode (there is no native JSON type for
them). This keeps the wire format ergonomic while still rejecting sloppy
coercions for primitives like ``int``/``bool``.
"""

from pydantic import BaseModel, ConfigDict


class StrictSchema(BaseModel):
    """Base model enforcing the §5.7 strictness contract for every schema."""

    model_config = ConfigDict(strict=True, extra="forbid")
