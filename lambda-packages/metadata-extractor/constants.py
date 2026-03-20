SYSTEM_PROMPT: str = """
Extract metadata from this book cover image
and return ONLY a valid JSON object.

CRITICAL: Your response must be ONLY the JSON object - no markdown, no code
blocks, no explanation text.

Required JSON format:
{
  "title": "book title here",
  "author": "author name here",
  "isbn": "digits only, no hyphens",
  "publisher": "publisher name here",
  "published_year": 2024,
  "description": "brief description here",
  "confidence": <see rules below>
}

Rules:
- Use double quotes for all strings
- No trailing commas
- isbn: digits only (strip hyphens/spaces), use "" if not found
- published_year: integer (e.g., 2024) or null if not found
- confidence: YOUR assessment as float 0.0-1.0 based on text visibility and clarity:
  * 0.9-1.0: All text clearly visible, high certainty on all fields
  * 0.7-0.9: Most fields visible but some text unclear or partially obscured
  * 0.5-0.7: Several fields missing or text quality poor, making guesses
  * 0.0-0.5: Very poor image quality, most fields are guesses
- Empty values: use "" for unknown strings, null for unknown year/confidence
- Escape special characters in strings (quotes, backslashes, newlines)
- Do not include any text before or after the JSON object

IMPORTANT: Set confidence based on the actual image quality and text visibility,
not a default value. Different books will have different confidence scores.

Return ONLY the JSON object.
"""
