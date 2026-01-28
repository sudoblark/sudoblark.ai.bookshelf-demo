/*
Copilot: Micro-instructions for `main.dart` (App entrypoint)

Purpose:

Goals:
1. Register `BooksProvider` and `UploadProvider` at the root using
   `MultiProvider` from the `provider` package so child widgets can access them.
2. Apply the theme from `utils/app_theme.dart` via `ThemeData` returned by
   `AppTheme.buildTheme()`.
3. Set `HomeScreen` as the `home` of the `MaterialApp`.
4. Read runtime configuration from `utils/constants.dart` (API host is build-time
   defined via `--dart-define=API_HOST=...`). Ensure no hardcoded URLs are present.
5. Turn off the debug banner for demo presentations: `debugShowCheckedModeBanner: false`.

Implementation details:
    ChangeNotifierProvider(create: (_) => BooksProvider()),
    ChangeNotifierProvider(create: (_) => UploadProvider()),
  ], child: MaterialApp(...))`.
  `String.fromEnvironment('APP_TITLE', defaultValue: 'Bookshelf Demo')` if desired.

Behavioral expectations:
  in README rather than embedding permission logic here.

Developer notes / run commands:
  flutter run --dart-define=API_HOST=http://192.168.1.100:5001

Files referenced:

Do not include:

When ready, implement `main.dart` following these instructions and then
replace this comment block with the actual code.
*/

// End of micro-instructions for main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'screens/home_screen.dart';
import 'providers/books_provider.dart';
import 'providers/upload_provider.dart';
import 'utils/app_theme.dart';

/// App title can be overridden at build time with --dart-define=APP_TITLE="..."
const String _appTitle =
    String.fromEnvironment('APP_TITLE', defaultValue: 'Bookshelf Demo');

void main() {
  runApp(const AppRoot());
}

class AppRoot extends StatelessWidget {
  const AppRoot({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => BooksProvider()),
        ChangeNotifierProvider(create: (_) => UploadProvider()),
      ],
      child: MaterialApp(
        title: _appTitle,
        debugShowCheckedModeBanner: false,
        theme: AppTheme.buildTheme(),
        home: const HomeScreen(),
      ),
    );
  }
}
