
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../utils/constants.dart';

/// A form widget for picking an image file and triggering upload.
///
/// Handles file selection, validation, and UI feedback. Calls [onUpload] when ready.
class UploadForm extends StatefulWidget {
   final Future<void> Function(File imageFile) onUpload;
   final bool isUploading;
   final String? errorMessage;
   final String? successMessage;

   const UploadForm({
      super.key,
      required this.onUpload,
      this.isUploading = false,
      this.errorMessage,
      this.successMessage,
   });

   @override
   State<UploadForm> createState() => _UploadFormState();
}

class _UploadFormState extends State<UploadForm> {
   File? _selectedFile;
   String? _fileError;

   Future<void> _pickImage() async {
      setState(() {
         _fileError = null;
      });
      print('Attempting to pick image from gallery...');
      
      // Use file_picker for desktop platforms (macOS, Windows, Linux)
      // Use image_picker for mobile (Android, iOS)
      if (Platform.isMacOS || Platform.isWindows || Platform.isLinux) {
         print('Using file_picker for desktop platform');
         final result = await FilePicker.platform.pickFiles(
            type: FileType.custom,
            allowedExtensions: ['jpg', 'jpeg', 'png'],
         );
         print('File picker result: ${result?.files.firstOrNull?.path ?? "null (user cancelled)"}');
         
         if (result == null || result.files.isEmpty) return;
         
         final file = File(result.files.first.path!);
         _validateAndSetFile(file);
      } else {
         print('Using image_picker for mobile platform');
         final picker = ImagePicker();
         final picked = await picker.pickImage(source: ImageSource.gallery);
         print('Image picker result: ${picked?.path ?? "null (user cancelled)"}');
         
         if (picked == null) return;
         final file = File(picked.path);
         _validateAndSetFile(file);
      }
   }

   void _validateAndSetFile(File file) {
      // Validate extension
      final ext = file.path.split('.').last.toLowerCase();
      if (!FileConstants.acceptedExtensions.any((e) => e.replaceAll('.', '') == ext)) {
         setState(() {
            _fileError = 'Unsupported file type.';
            _selectedFile = null;
         });
         return;
      }
      // Validate size (async check)
      file.length().then((size) {
         if (size > FileConstants.maxFileSizeBytes) {
            setState(() {
               _fileError = 'File too large (max 10MB).';
               _selectedFile = null;
            });
         } else {
            setState(() {
               _selectedFile = file;
               _fileError = null;
            });
         }
      });
   }

   void _clearSelection() {
      setState(() {
         _selectedFile = null;
         _fileError = null;
      });
   }

   @override
   Widget build(BuildContext context) {
      return Column(
         crossAxisAlignment: CrossAxisAlignment.stretch,
         children: [
            OutlinedButton.icon(
               icon: const Icon(Icons.image),
               label: Text(_selectedFile == null ? 'Select Image' : 'Change Image'),
               onPressed: widget.isUploading ? null : _pickImage,
            ),
            if (_selectedFile != null)
               Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(
                     'Selected: ${_selectedFile!.path.split('/').last}',
                     style: Theme.of(context).textTheme.bodyMedium,
                  ),
               ),
            if (_fileError != null)
               Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(
                     _fileError!,
                     style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
               ),
            if (widget.errorMessage != null)
               Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(
                     widget.errorMessage!,
                     style: TextStyle(color: Theme.of(context).colorScheme.error),
                  ),
               ),
            if (widget.successMessage != null)
               Padding(
                  padding: const EdgeInsets.only(top: 8.0),
                  child: Text(
                     widget.successMessage!,
                     style: TextStyle(color: Colors.green),
                  ),
               ),
            const SizedBox(height: 16),
            Row(
               children: [
                  Expanded(
                     child: ElevatedButton(
                        onPressed: widget.isUploading || _selectedFile == null || _fileError != null
                              ? null
                              : () => widget.onUpload(_selectedFile!),
                        child: widget.isUploading
                              ? const SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                 )
                              : const Text('Upload'),
                     ),
                  ),
                  if (_selectedFile != null)
                     IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: widget.isUploading ? null : _clearSelection,
                        tooltip: 'Clear selection',
                     ),
               ],
            ),
         ],
      );
   }
}