/*
Copilot: This file implements the HTTP client for communicating with the backend API.

Goals:
1. Provide methods for the three main API operations:
   - uploadImage(File image): Future<void> - POST /upload
   - getBooks(): Future<List<Book>> - GET /books
   - getStatus(): Future<Map> - GET /status
2. Handle HTTP errors gracefully with meaningful error messages.
3. Parse JSON responses into Dart objects.
4. Use the http package for HTTP requests.
5. Read API base URL from constants.dart.

Expectations:
- Use async/await for clean asynchronous code.
- Include error handling with try-catch for network failures.
- Return Future types for reactive programming compatibility.
- Keep timeout defaults reasonable (e.g., 30s).
- Log errors for debugging (use print or a logger).

Do not include:
- State management (that's for providers).
- UI/Widget code.
- Business logic beyond HTTP communication.
- Hardcoded URLs (use constants).
*/