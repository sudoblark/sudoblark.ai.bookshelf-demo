/*
Copilot: This file implements the state provider for managing file uploads.

Goals:
1. Use the Provider package to manage upload state.
2. Track upload progress (idle, uploading, success, error).
3. Call api_service.uploadImage() and expose the result.
4. Provide a method to reset state after upload.
5. Store error messages for display in the UI.

Expectations:
- Use StateNotifierProvider to manage upload state.
- Include an enum or class for upload states (idle, loading, success, error).
- Store and expose error messages.
- Support clearing state for new uploads.
- Include optional progress tracking if feasible.

Do not include:
- UI code (this is pure state management).
- File picker logic (belongs in upload_screen).
- Complex validation.
*/