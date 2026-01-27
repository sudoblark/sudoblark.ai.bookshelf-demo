/*
Copilot: This file implements a single book card widget for displaying one book record.

Goals:
1. Create a reusable Card widget that displays a single Book.
2. Show key fields: title, author, ISBN, filename, processed_at.
3. Use a clean, readable layout with Material Design.
4. Make the card slightly interactive (subtle elevation on hover).

Expectations:
- Accept a Book object as a parameter.
- Use Column/Row for layout.
- Display timestamps in a human-readable format (use intl package if available).
- Use constants for spacing and styling.
- Fallback to placeholder text if fields are null.

Do not include:
- Navigation or tap handlers (parent widget's responsibility).
- API calls.
- State management.
- Complex logic.
*/