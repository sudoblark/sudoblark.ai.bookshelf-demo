"""Pydantic models for the bookshelf streaming agent service."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class StreamingBookMetadataResponse(BaseModel):
    """Book metadata for streaming extraction and refinement.

    Used as the pydantic-ai ``output_type`` so the agent can be streamed via
    ``run_stream()``.  All fields mirror ``BookMetadata`` from the bookshelf-agent
    layer, plus ``assistantMessage`` and ``readyToSave`` for multi-turn chat.

    Keeping the model flat (rather than nesting ``BookMetadata``) allows
    pydantic-ai to emit partial updates for every field as tokens arrive.
    """

    title: str = Field(default="", description="Book title")
    author: str = Field(default="", description="Author name(s)")
    isbn: str = Field(default="", description="ISBN (digits only, no hyphens)")
    publisher: str = Field(default="", description="Publisher name")
    published_year: Optional[int] = Field(default=None, description="Year of publication")
    description: str = Field(default="", description="Brief book description")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="AI extraction confidence (0.0-1.0)",
    )
    assistantMessage: str = Field(
        default="",
        description="Running conversational message from the agent",
    )
    readyToSave: bool = Field(
        default=False,
        description="True when user has confirmed metadata and it is ready to persist",
    )

    @field_validator("published_year", mode="before")
    @classmethod
    def validate_published_year(cls, v: any) -> Optional[int]:
        """Convert invalid year values to None.

        The agent may return strings like 'Unknown', 'N/A', etc. when the year
        is not visible. Convert these to None so the field is nullable.
        """
        if v is None:
            return None
        if isinstance(v, int):
            # Validate year is in reasonable range
            if 1000 <= v <= 2100:
                return v
            return None
        if isinstance(v, str):
            v_lower = v.lower().strip()
            # Skip non-numeric placeholders
            if v_lower in ("", "unknown", "n/a", "na", "not found", "not visible"):
                return None
            # Try to parse as int
            try:
                year = int(v)
                if 1000 <= year <= 2100:
                    return year
            except (ValueError, TypeError):
                pass
            return None
        return None
