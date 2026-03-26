"""Data lake bucket tier definitions for the bookshelf-demo pipeline."""

from dataclasses import dataclass


@dataclass
class BookshelfDataLake:
    """Full bucket names for each tier of the bookshelf-demo data lake.

    Attributes:
        landing: Bucket where users upload raw images.
        raw: Bucket for AV-clean files awaiting enrichment.
        processed: Bucket for Parquet metadata output.
    """

    landing: str
    raw: str
    processed: str

    @classmethod
    def from_prefix(cls, prefix: str) -> "BookshelfDataLake":
        """Construct bucket names from a shared account-scoped prefix.

        Args:
            prefix: Account-scoped prefix, e.g. ``aws-sudoblark-dev-bookshelf-demo``.
                    Tier suffixes (``-landing``, ``-raw``, ``-processed``) are appended.
        """
        return cls(
            landing=f"{prefix}-landing",
            raw=f"{prefix}-raw",
            processed=f"{prefix}-processed",
        )
