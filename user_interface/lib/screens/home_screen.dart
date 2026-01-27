/*
Copilot: This file implements the main home screen with navigation between two tabs/sections.

Goals:
1. Create a TabBar or bottom navigation to switch between:
   - Upload screen (POST images)
   - Books list screen (VIEW processed data)
2. Provide a clean, centered layout with app branding.
3. Include app title and simple navigation UI.
4. Keep navigation logic minimal and declarative.

Expectations:
- Use StatefulWidget if using TabBar, StatelessWidget if using bottom nav.
- Include a Scaffold with AppBar.
- Use the app_theme.dart for colors and typography.
- Keep the screen simple—let child screens handle complexity.
- Avoid API calls directly; delegate to child screens.

Do not include:
- Complex state management at this level.
- API calls.
- File picker or upload logic (belongs in upload_screen).
- Data fetching logic (belongs in books_list_screen).
*/