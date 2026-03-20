from typing import Optional

from pydantic import BaseModel, Field, field_validator


class BookMetadata(BaseModel):
    """Pydantic model for book metadata extracted from covers."""

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

    @field_validator("isbn")
    @classmethod
    def validate_isbn(cls, v: str) -> str:
        """Remove hyphens and spaces from ISBN."""
        if v:
            return v.replace("-", "").replace(" ", "")
        return v

    @field_validator("published_year")
    @classmethod
    def validate_year(cls, v: Optional[int]) -> Optional[int]:
        """Validate year is reasonable."""
        if v is not None and (v < 1000 or v > 2100):
            return None
        return v
