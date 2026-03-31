import io
import logging
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Handles image transformation operations."""

    @staticmethod
    def resize_to_jpeg(image_bytes: bytes, max_dim: int = 1024, quality: int = 90) -> bytes:
        """Resize image to fit within max_dim x max_dim and convert to JPEG.

        Raises:
            ValueError: If image_bytes is empty.
            IOError: If image processing fails.
        """
        if not image_bytes:
            raise ValueError("image_bytes must not be empty")

        try:
            original_img: "PILImage"
            with Image.open(io.BytesIO(image_bytes)) as original_img:
                rgb_img: "PILImage" = original_img.convert("RGB")
                rgb_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                buffer: io.BytesIO = io.BytesIO()
                rgb_img.save(buffer, format="JPEG", quality=quality)
                return buffer.getvalue()

        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}", exc_info=True)
            raise
