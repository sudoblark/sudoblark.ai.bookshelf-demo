import 'dart:io';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/upload_provider.dart';
import '../widgets/upload_form.dart';

/// UploadScreen composes the UploadForm and connects it to UploadProvider.
class UploadScreen extends StatelessWidget {
	const UploadScreen({Key? key}) : super(key: key);

	@override
	Widget build(BuildContext context) {
		final uploadProvider = Provider.of<UploadProvider>(context);

		return Padding(
			padding: const EdgeInsets.all(16.0),
			child: Column(
				crossAxisAlignment: CrossAxisAlignment.stretch,
				children: [
					Text(
						'Upload Book Cover',
						style: Theme.of(context).textTheme.headlineSmall,
					),
					const SizedBox(height: 12),
					UploadForm(
						isUploading: uploadProvider.isLoading,
						errorMessage: uploadProvider.error,
						successMessage: uploadProvider.isSuccess ? 'Upload successful' : null,
						onUpload: (File file) async {
							await uploadProvider.uploadImage(file);
							if (uploadProvider.isSuccess) {
								ScaffoldMessenger.of(context).showSnackBar(
									const SnackBar(content: Text('Upload completed')),
								);
							} else if (uploadProvider.isError) {
								ScaffoldMessenger.of(context).showSnackBar(
									SnackBar(content: Text(uploadProvider.error ?? 'Upload failed')),
								);
							}
						},
					),
				],
			),
		);
	}
}