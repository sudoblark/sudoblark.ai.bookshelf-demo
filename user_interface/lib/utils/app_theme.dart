import 'package:flutter/material.dart';
import 'constants.dart';

/// Material Design theme for the Bookshelf Demo application.
/// 
/// Provides a clean, professional aesthetic suitable for a local ETL demo.
/// All spacing and sizing uses UiConstants for consistency.

class AppTheme {
  /// Primary color - used for main UI elements, buttons, highlights
  static const Color primaryColor = Color(0xFF2196F3);

  /// Primary dark variant
  static const Color primaryDarkColor = Color(0xFF1976D2);

  /// Secondary color - used for accents and alternative actions
  static const Color secondaryColor = Color(0xFF26C6DA);

  /// Secondary dark variant
  static const Color secondaryDarkColor = Color(0xFF00ACC1);

  /// Error color - for validation and error states
  static const Color errorColor = Color(0xFFD32F2F);

  /// Success color - for successful uploads, confirmations
  static const Color successColor = Color(0xFF388E3C);

  /// Warning color - for cautions
  static const Color warningColor = Color(0xFFFFA726);

  /// Background colors
  static const Color backgroundColor = Color(0xFFFAFAFA);
  static const Color surfaceColor = Colors.white;

  /// Text colors
  static const Color textPrimary = Color(0xFF212121);
  static const Color textSecondary = Color(0xFF757575);
  static const Color textHint = Color(0xFFBDBDBD);

  /// Divider and border color
  static const Color dividerColor = Color(0xFFEEEEEE);

  /// Build and return the Material ThemeData
  static ThemeData buildTheme() {
    return ThemeData(
      // Color scheme
      useMaterial3: true,
      colorScheme: ColorScheme.light(
        primary: primaryColor,
        secondary: secondaryColor,
        error: errorColor,
        surface: surfaceColor,
        onPrimary: Colors.white,
        onSecondary: Colors.white,
      ),

      // App bar theme
      appBarTheme: AppBarTheme(
        backgroundColor: primaryColor,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: _buildTextStyle(
          fontSize: 20,
          fontWeight: FontWeight.bold,
          color: Colors.white,
        ),
      ),

      // Text themes
      textTheme: TextTheme(
        displayLarge: _buildTextStyle(
          fontSize: 32,
          fontWeight: FontWeight.bold,
          color: textPrimary,
        ),
        displayMedium: _buildTextStyle(
          fontSize: 28,
          fontWeight: FontWeight.bold,
          color: textPrimary,
        ),
        headlineSmall: _buildTextStyle(
          fontSize: 24,
          fontWeight: FontWeight.bold,
          color: textPrimary,
        ),
        titleLarge: _buildTextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        titleMedium: _buildTextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        bodyLarge: _buildTextStyle(
          fontSize: 16,
          fontWeight: FontWeight.normal,
          color: textPrimary,
        ),
        bodyMedium: _buildTextStyle(
          fontSize: 14,
          fontWeight: FontWeight.normal,
          color: textPrimary,
        ),
        bodySmall: _buildTextStyle(
          fontSize: 12,
          fontWeight: FontWeight.normal,
          color: textSecondary,
        ),
        labelLarge: _buildTextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: Colors.white,
        ),
      ),

      // Button themes
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryColor,
          foregroundColor: Colors.white,
          padding: EdgeInsets.symmetric(
            horizontal: UiConstants.baseSpacing,
            vertical: UiConstants.smallSpacing,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(UiConstants.borderRadius),
          ),
        ),
      ),

      // Card theme (use defaults for broad compatibility)
      // Custom card styling intentionally omitted for compatibility with
      // multiple Flutter versions; rely on colorScheme and ElevatedCard styles.

      // Input decoration theme
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: backgroundColor,
        contentPadding: EdgeInsets.all(UiConstants.baseSpacing),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(UiConstants.smallBorderRadius),
          borderSide: BorderSide(color: dividerColor),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(UiConstants.smallBorderRadius),
          borderSide: BorderSide(color: dividerColor),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(UiConstants.smallBorderRadius),
          borderSide: BorderSide(color: primaryColor, width: 2),
        ),
        hintStyle: _buildTextStyle(
          fontSize: 14,
          color: textHint,
        ),
      ),

      // Scaffold background
      scaffoldBackgroundColor: backgroundColor,

      // Dialog theme (omit explicit DialogTheme for cross-version safety)
    );
  }

  /// Helper to build text style with consistent font
  static TextStyle _buildTextStyle({
    required double fontSize,
    FontWeight fontWeight = FontWeight.normal,
    Color color = textPrimary,
    double? letterSpacing,
    double? height,
  }) {
    return TextStyle(
      fontSize: fontSize,
      fontWeight: fontWeight,
      color: color,
      letterSpacing: letterSpacing,
      height: height,
    );
  }
}