/*
Copilot: This file implements the image upload screen.

Goals:
1. Provide a file picker to select image files (JPG, PNG, WEBP).
2. Display a preview of the selected image.
3. Implement an upload button that calls api_service.uploadImage().
4. Show upload progress and success/error feedback to the user.
5. Use upload_provider for state management.

Expectations:
- Use image_picker package for file selection.
- Display the selected image with Image.file().
- Show loading indicator during upload.
- Display success/error messages with SnackBar or AlertDialog.
- Disable the upload button while uploading.
- Support multiple sequential uploads in a session.

Do not include:
- Direct API calls (use upload_provider instead).
- Data persistence beyond current session.
- Complex image processing.
- Hardcoded file paths.
*/