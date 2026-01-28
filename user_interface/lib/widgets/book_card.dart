import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/book.dart';
import '../utils/app_theme.dart';
import '../utils/constants.dart';

/// A reusable card widget that displays a single book record.
///
/// Shows key information about a book including title, author, ISBN,
/// filename, and processing timestamp in a clean Material Design layout.
class BookCard extends StatelessWidget {
  /// The book data to display
  final Book book;

  /// Optional callback when the card is tapped
  final VoidCallback? onTap;

  const BookCard({
    super.key,
    required this.book,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.all(UiConstants.baseSpacing),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title
              Text(
                book.title,
                style: Theme.of(context).textTheme.titleLarge,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              SizedBox(height: UiConstants.smallSpacing),

              // Author
              Text(
                'by ${book.author}',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      color: AppTheme.textSecondary,
                    ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              SizedBox(height: UiConstants.baseSpacing),

              // ISBN (if available)
              if (book.isbn != null) ...[
                Row(
                  children: [
                    Text(
                      'ISBN: ',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.w600,
                          ),
                    ),
                    Expanded(
                      child: Text(
                        book.isbn!,
                        style: Theme.of(context).textTheme.bodySmall,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
                SizedBox(height: UiConstants.smallSpacing),
              ],

              // Filename
              Row(
                children: [
                  Text(
                    'File: ',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                  Expanded(
                    child: Text(
                      book.filename,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: AppTheme.textSecondary,
                          ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              SizedBox(height: UiConstants.smallSpacing),

              // Processed timestamp
              Row(
                children: [
                  Icon(
                    Icons.access_time,
                    size: 14,
                    color: AppTheme.textHint,
                  ),
                  SizedBox(width: UiConstants.smallSpacing / 2),
                  Text(
                    _formatDate(book.processedAt),
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: AppTheme.textHint,
                        ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Format the datetime in a human-readable format.
  ///
  /// Shows date and time in the device's locale.
  String _formatDate(DateTime dateTime) {
    try {
      return DateFormat('MMM d, yyyy • h:mm a').format(dateTime);
    } catch (e) {
      return dateTime.toString();
    }
  }
}