/*
Copilot: This file implements the upload form widget (file picker + upload button).

Goals:
1. Provide a clean form layout with:
   - File picker button (select image)
   - Upload button (send to backend)
   - Status text showing selected file or progress
2. Use image_picker to select files.
3. Validate file selection before enabling upload.
4. Disable buttons while uploading.
5. Callback to parent with upload result.

Expectations:
- Accept a callback function for upload action.
- Show selected filename or image preview.
- Provide visual feedback (buttons enable/disable based on state).
- Use Material Design buttons (ElevatedButton, OutlinedButton).
- Handle file picker cancellation gracefully.

Do not include:
- Direct API calls (parent/provider handles that).
- State management beyond local widget state.
- Complex validation logic.
*/