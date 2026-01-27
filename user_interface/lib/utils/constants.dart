/*
Copilot: This file defines constants used throughout the Flutter app.

Goals:
1. Define the backend API base URL with environment variable support (default: http://localhost:5000).
2. Read API_HOST from environment via String.fromEnvironment() with sensible defaults.
3. List all API endpoints as constants (/upload, /books, /status, /health).
4. Define supported image file extensions (jpg, jpeg, png, webp).
5. Include app-wide constants (timeouts, max file size, spacing, border radius).
6. Allow easy reconfiguration for different environments without rebuilding.

Implementation approach:
- Use static const for all constants.
- Use String.fromEnvironment() for API_HOST with a default value.
- Group related constants into classes (ApiConstants, FileConstants, NetworkConstants, UiConstants).
- Provide full URLs as getters where needed.
- Make the file a single source of truth for configuration.

Expectations:
- Environment variables should be passed at build time: flutter run --dart-define=API_HOST=...
- Include clear variable names that are self-documenting.
- Defaults should work for local development (localhost:5000).
- Support production/different environment configuration via env vars.

Do not include:
- Logic or computations beyond deriving constants.
- State or mutable variables.
- Dependencies on other files.
- API calls.
*/