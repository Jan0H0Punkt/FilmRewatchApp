"""Pydantic request/response schemas for the settings module (DESIGN §5.3, FR-RW-08).

One row, one shape: the same field is read on GET and written on PUT, so a
single schema serves both — built ``from_attributes`` off the ORM row for the
response, and validated from the request body for the write.
"""

from pydantic import ConfigDict, field_validator

from app.core.schemas import StrictSchema


class SettingsBody(StrictSchema):
    """The rewatch-share setting: ``null`` (Off) or 0-100 in steps of 10 (FR-RW-08)."""

    # Merged into the strict base config: allows building the schema straight
    # from the ORM row while the model stays strict and closed.
    model_config = ConfigDict(from_attributes=True)

    rewatch_share: int | None

    @field_validator("rewatch_share")
    @classmethod
    def _range_and_step(cls, value: int | None) -> int | None:
        # A shape constraint, not a domain rule (mirrors RatingCreate.value):
        # an off-step or out-of-range share is a plain VALIDATION_ERROR.
        if value is not None and (not 0 <= value <= 100 or value % 10 != 0):
            raise ValueError("rewatch_share must be between 0 and 100 in steps of 10")
        return value
