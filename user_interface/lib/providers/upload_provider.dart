import 'dart:io';
import 'package:flutter/material.dart';
import '../services/api_service.dart';

/// Enumeration of possible upload states.
enum UploadState {
  /// No upload in progress
  idle,

  /// Currently uploading
  loading,

  /// Upload completed successfully
  success,

  /// Upload failed with an error
  error,
}

/// Manages the state of image uploads to the backend.
///
/// Tracks upload progress, handles errors, and provides methods to initiate
/// uploads and reset state. Extends ChangeNotifier to notify UI of state changes.
class UploadProvider extends ChangeNotifier {
  /// Current upload state
  UploadState _state = UploadState.idle;

  /// Error message if upload fails
  String? _error;

  /// Name of the file being uploaded (for display)
  String? _uploadedFileName;

  /// Getter for the current upload state
  UploadState get state => _state;

  /// Getter for error message
  String? get error => _error;

  /// Getter for uploaded file name
  String? get uploadedFileName => _uploadedFileName;

  /// Whether an upload is currently in progress
  bool get isLoading => _state == UploadState.loading;

  /// Whether the last upload was successful
  bool get isSuccess => _state == UploadState.success;

  /// Whether the last upload failed
  bool get isError => _state == UploadState.error;

  /// Upload an image file to the backend.
  ///
  /// Sets state to loading, calls [ApiService.uploadImage], and updates
  /// state to success or error based on the result.
  ///
  /// Arguments:
  ///   - [imageFile]: The image file to upload
  ///
  /// The UI should call [reset] after handling the result to allow new uploads.
  Future<void> uploadImage(File imageFile) async {
    _state = UploadState.loading;
    _error = null;
    _uploadedFileName = imageFile.path.split('/').last;
    notifyListeners();

    try {
      await ApiService.uploadImage(imageFile);
      _state = UploadState.success;
      _error = null;
    } catch (e) {
      _state = UploadState.error;
      _error = 'Upload failed: $e';
    } finally {
      notifyListeners();
    }
  }

  /// Reset the upload state back to idle.
  ///
  /// Call this after the UI has displayed the result (success or error)
  /// to prepare for a new upload.
  void reset() {
    _state = UploadState.idle;
    _error = null;
    _uploadedFileName = null;
    notifyListeners();
  }

  /// Clear all upload state including any error messages.
  void clear() {
    _state = UploadState.idle;
    _error = null;
    _uploadedFileName = null;
  }
}