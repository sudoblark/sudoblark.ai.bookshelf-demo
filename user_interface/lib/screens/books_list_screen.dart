/*
Copilot: This file implements the books list screen that displays processed metadata.

Goals:
1. Fetch the list of books from GET /books on load.
2. Display books in a scrollable ListView using book_list widget.
3. Show a loading indicator while fetching.
4. Show an empty state message if no books exist yet.
5. Include a refresh button to reload the data.
6. Use books_provider for state management.

Expectations:
- Use FutureBuilder or Provider for async data handling.
- Display loading, error, and empty states clearly.
- Provide visual feedback when refreshing.
- Handle network errors gracefully with retry option.
- Auto-refresh on screen focus (optional: use lifecycle awareness).

Do not include:
- Direct API calls (use books_provider instead).
- Complex data manipulation.
- File download logic.
- Search/filter (save for future).
*/