import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/books_provider.dart';
import '../widgets/book_list.dart';

/// BooksListScreen fetches and displays books using BooksProvider.
class BooksListScreen extends StatefulWidget {
	const BooksListScreen({Key? key}) : super(key: key);

	@override
	State<BooksListScreen> createState() => _BooksListScreenState();
}

class _BooksListScreenState extends State<BooksListScreen> {
	late BooksProvider _booksProvider;

	@override
	void didChangeDependencies() {
		super.didChangeDependencies();
		_booksProvider = Provider.of<BooksProvider>(context, listen: false);
		// Fetch books on first build
		_booksProvider.fetchBooks();
	}

	Future<void> _refresh() async {
		await _booksProvider.refresh();
	}

	@override
	Widget build(BuildContext context) {
		return Consumer<BooksProvider>(
			builder: (context, provider, child) {
				if (provider.isLoading) {
					return const Center(child: CircularProgressIndicator());
				}
				if (provider.error != null) {
					return Center(
						child: Column(
							mainAxisSize: MainAxisSize.min,
							children: [
								Text('Error: ${provider.error}'),
								const SizedBox(height: 8),
								ElevatedButton(
									onPressed: provider.fetchBooks,
									child: const Text('Retry'),
								),
							],
						),
					);
				}

				return RefreshIndicator(
					onRefresh: _refresh,
					child: BookList(
						books: provider.books,
						onBookTap: (book) {
							// Placeholder: show details in a dialog
							showDialog(
								context: context,
								builder: (context) => AlertDialog(
									title: Text(book.title),
									content: Text('Author: ${book.author}\nFilename: ${book.filename}'),
									actions: [
										TextButton(
											onPressed: () => Navigator.of(context).pop(),
											child: const Text('Close'),
										),
									],
								),
							);
						},
					),
				);
			},
		);
	}
}