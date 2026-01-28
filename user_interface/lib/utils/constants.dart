/*
Application-wide constants for the Bookshelf Demo.

Configuration is read from environment variables where applicable, with
sensible defaults for local development. Build with `--dart-define` to override.
Example: `flutter run --dart-define=API_HOST=http://192.168.1.100:5001`
*/

/// API configuration and endpoints
class ApiConstants {
  /// Base URL for backend API
  static const String baseUrl =
      String.fromEnvironment('API_HOST', defaultValue: 'http://localhost:5001');

  /// API endpoint paths
  static const String uploadImageEndpoint = '/upload';
  static const String getBooksEndpoint = '/books';
  static const String getStatusEndpoint = '/status';
}

/// File upload constraints
class FileConstants {
  /// Accepted image file extensions (without leading dot)
  static const List<String> acceptedExtensions = ['jpg', 'jpeg', 'png'];

  /// Maximum file size in bytes (10 MB)
  static const int maxFileSizeBytes = 10 * 1024 * 1024;
}

/// Network configuration
class NetworkConstants {
  /// Request timeout in seconds
  static const Duration requestTimeout = Duration(seconds: 30);

  /// Number of retries for failed requests
  static const int maxRetries = 3;

  /// Delay between retries in milliseconds
  static const Duration retryDelay = Duration(milliseconds: 500);
}

/// UI spacing and layout constants
class UiConstants {
  /// Standard padding/spacing unit
  static const double baseSpacing = 16.0;

  /// Small spacing (half of base)
  static const double smallSpacing = 8.0;

  /// Card elevation
  static const double cardElevation = 2.0;
  
  /// Standard border radius
  static const double borderRadius = 12.0;

  /// Small border radius
  static const double smallBorderRadius = 8.0;
}