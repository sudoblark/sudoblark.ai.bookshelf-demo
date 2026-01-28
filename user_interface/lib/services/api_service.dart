import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/book.dart';
import '../utils/constants.dart';

/// HTTP client for communicating with the Bookshelf Demo backend API.
///
/// Handles all API requests to the local backend including image uploads,
/// fetching processed books, and checking system status.
class ApiService {
  /// Private constructor to prevent instantiation
  ApiService._();

  /// Uploads an image file to the backend for processing.
  ///
  /// Sends a multipart POST request to [ApiConstants.uploadImageEndpoint]
  /// with the image file.
  ///
  /// Throws [HttpException] if the upload fails or times out.
  /// Throws [FormatException] if the response cannot be parsed.
  static Future<void> uploadImage(File imageFile) async {
    try {
      final uri = Uri.parse(
        '${ApiConstants.baseUrl}${ApiConstants.uploadImageEndpoint}',
      );

      // The backend expects the multipart field to be named 'file'.
      final request = http.MultipartRequest('POST', uri)
        ..files.add(
          await http.MultipartFile.fromPath('file', imageFile.path),
        );

      final response = await request.send().timeout(
        NetworkConstants.requestTimeout,
        onTimeout: () {
          throw HttpException(
            'Upload request timed out after ${NetworkConstants.requestTimeout.inSeconds}s',
          );
        },
      );

      if (response.statusCode != 200 && response.statusCode != 201) {
        final body = await response.stream.bytesToString();
        throw HttpException(
          'Upload failed with status ${response.statusCode}: $body',
        );
      }
    } on HttpException {
      rethrow;
    } catch (e) {
      throw HttpException('Upload error: $e');
    }
  }

  /// Fetches all processed books from the backend.
  ///
  /// Makes a GET request to [ApiConstants.getBooksEndpoint] and parses
  /// the response into a list of [Book] objects.
  ///
  /// Returns an empty list if no books are found.
  /// Throws [HttpException] if the request fails or times out.
  /// Throws [FormatException] if the response JSON is malformed.
  static Future<List<Book>> getBooks() async {
    try {
      final uri = Uri.parse(
        '${ApiConstants.baseUrl}${ApiConstants.getBooksEndpoint}',
      );

      final response = await http.get(uri).timeout(
        NetworkConstants.requestTimeout,
        onTimeout: () {
          throw HttpException(
            'Get books request timed out after ${NetworkConstants.requestTimeout.inSeconds}s',
          );
        },
      );

      if (response.statusCode == 200) {
        final List<dynamic> jsonData = _parseJsonResponse(response.body);
        return jsonData.map((item) => Book.fromJson(item as Map<String, dynamic>)).toList();
      } else if (response.statusCode == 404) {
        return [];
      } else {
        throw HttpException(
          'Failed to fetch books with status ${response.statusCode}: ${response.body}',
        );
      }
    } on HttpException {
      rethrow;
    } catch (e) {
      throw HttpException('Get books error: $e');
    }
  }

  /// Fetches the backend system status.
  ///
  /// Makes a GET request to [ApiConstants.getStatusEndpoint] and returns
  /// the parsed JSON response as a map.
  ///
  /// Throws [HttpException] if the request fails or times out.
  /// Throws [FormatException] if the response JSON is malformed.
  static Future<Map<String, dynamic>> getStatus() async {
    try {
      final uri = Uri.parse(
        '${ApiConstants.baseUrl}${ApiConstants.getStatusEndpoint}',
      );

      final response = await http.get(uri).timeout(
        NetworkConstants.requestTimeout,
        onTimeout: () {
          throw HttpException(
            'Get status request timed out after ${NetworkConstants.requestTimeout.inSeconds}s',
          );
        },
      );

      if (response.statusCode == 200) {
        return _parseJsonResponse(response.body) as Map<String, dynamic>;
      } else {
        throw HttpException(
          'Failed to fetch status with status ${response.statusCode}: ${response.body}',
        );
      }
    } on HttpException {
      rethrow;
    } catch (e) {
      throw HttpException('Get status error: $e');
    }
  }

  /// Parses JSON response body with error handling.
  ///
  /// Throws [FormatException] if JSON is malformed.
  static dynamic _parseJsonResponse(String body) {
    try {
      return jsonDecode(body);
    } catch (e) {
      throw FormatException('JSON parse error: $e');
    }
  }
}