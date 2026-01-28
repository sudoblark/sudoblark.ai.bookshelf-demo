import 'package:flutter/material.dart';
import 'package:flutter/widgets.dart';
import 'dart:async';
import '../models/book.dart';
import '../services/api_service.dart';

/// Manages the state of the books list fetched from the backend.
///
/// Handles loading, caching, and refreshing of book data. Extends ChangeNotifier
/// to notify listeners when data changes.
class BooksProvider extends ChangeNotifier {
  /// The current list of books
  List<Book> _books = [];

  /// Whether books are currently being fetched
  bool _isLoading = false;

  /// Error message if fetch fails
  String? _error;

  /// Getter for the books list
  List<Book> get books => _books;

  /// Getter for loading state
  bool get isLoading => _isLoading;

  /// Getter for error message
  String? get error => _error;

  /// Whether the list is empty
  bool get isEmpty => _books.isEmpty && !_isLoading;

  /// Fetch books from the backend API.
  ///
  /// Updates [_books], [_isLoading], and [_error] states.
  /// Notifies listeners when state changes.
  Future<void> fetchBooks() async {
    _isLoading = true;
    _error = null;
    // Defer the initial notification to avoid calling notifyListeners
    // synchronously during the widget build phase which causes
    // "setState() or markNeedsBuild() called during build" errors.
    WidgetsBinding.instance.addPostFrameCallback((_) => notifyListeners());

    try {
      _books = await ApiService.getBooks();
      _error = null;
    } catch (e) {
      _error = 'Failed to fetch books: $e';
      _books = [];
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  /// Refresh the books list by fetching from the backend again.
  ///
  /// This can be called by UI widgets (e.g., pull-to-refresh).
  Future<void> refresh() async {
    await fetchBooks();
  }

  /// Clear the current books list and reset state.
  ///
  /// Useful for cleanup or logout scenarios.
  void clear() {
    _books = [];
    _error = null;
    _isLoading = false;
    notifyListeners();
  }
}