/*
Copilot: This file defines the Book model that represents a single record
from the processed Parquet files.

Goals:
1. Create a simple, immutable Book class that mirrors the backend schema.
2. Include fields that match the ETL pipeline output (filename, title, author, isbn, processed_at).
3. Add a fromJson constructor for deserializing API responses.
4. Add a toJson method for serialization if needed.
5. Keep the model pure—no business logic, just data representation.

Expectations:
- Use final fields and const constructors for immutability.
- Include null safety (? for optional fields).
- Add helpful docstrings for each field.
- Keep the model in sync with backend/parquet_reader.py output format.

Do not include:
- API calls or state management.
- Complex validation logic (that belongs in services).
- Widget-specific code.
*/