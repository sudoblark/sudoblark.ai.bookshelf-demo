
import 'package:flutter/material.dart';
import '../models/book.dart';
import 'book_card.dart';
import '../utils/constants.dart';

/// A scrollable list widget for displaying multiple books using BookCard.
///
/// Accepts a list of Book objects and displays each in a Material Card.
/// Shows an empty state message if the list is empty or null.
class BookList extends StatelessWidget {
	final List<Book>? books;
	final void Function(Book)? onBookTap;

	const BookList({
		Key? key,
		required this.books,
		this.onBookTap,
	}) : super(key: key);

	@override
	Widget build(BuildContext context) {
		if (books == null || books!.isEmpty) {
			return Center(
				child: Text(
					'No books found.',
					style: Theme.of(context).textTheme.bodyLarge,
				),
			);
		}
		return ListView.separated(
			padding: EdgeInsets.all(UiConstants.baseSpacing),
			itemCount: books!.length,
			separatorBuilder: (context, index) => SizedBox(height: UiConstants.baseSpacing),
			itemBuilder: (context, index) {
				final book = books![index];
				return BookCard(
					book: book,
					onTap: onBookTap != null ? () => onBookTap!(book) : null,
				);
			},
		);
	}
}