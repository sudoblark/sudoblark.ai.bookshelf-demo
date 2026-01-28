import 'package:flutter/material.dart';
import 'upload_screen.dart';
import 'books_list_screen.dart';

/// Home screen with bottom navigation to switch between Upload and Books tabs.
class HomeScreen extends StatefulWidget {
   const HomeScreen({super.key});

   @override
   State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
   int _currentIndex = 0;

   static const List<Widget> _pages = <Widget>[
      UploadScreen(),
      BooksListScreen(),
   ];

   void _onNavTapped(int index) {
      setState(() {
         _currentIndex = index;
      });
   }

   @override
   Widget build(BuildContext context) {
      return Scaffold(
         appBar: AppBar(
            title: const Text('Bookshelf Demo'),
         ),
         body: _pages[_currentIndex],
         bottomNavigationBar: BottomNavigationBar(
            currentIndex: _currentIndex,
            onTap: _onNavTapped,
            items: const [
               BottomNavigationBarItem(
                  icon: Icon(Icons.upload_file),
                  label: 'Upload',
               ),
               BottomNavigationBarItem(
                  icon: Icon(Icons.list_alt),
                  label: 'Books',
               ),
            ],
         ),
      );
   }
}