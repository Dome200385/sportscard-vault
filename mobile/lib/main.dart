import 'package:flutter/material.dart';
import 'screens/collection_screen.dart';
import 'screens/add_card_screen.dart';
import 'screens/scanner_screen.dart';
void main()=>runApp(const SportsCardVaultApp());
class SportsCardVaultApp extends StatelessWidget{const SportsCardVaultApp({super.key});@override Widget build(BuildContext context)=>MaterialApp(debugShowCheckedModeBanner:false,title:'SportsCard Vault',theme:ThemeData(colorSchemeSeed:Colors.indigo,useMaterial3:true),routes:{'/add':(_)=>const AddCardScreen()},home:const HomeShell());}
class HomeShell extends StatefulWidget{const HomeShell({super.key});@override State<HomeShell> createState()=>_HomeShellState();}
class _HomeShellState extends State<HomeShell>{int index=0;final pages=const [CollectionScreen(),ScannerScreen()];@override Widget build(BuildContext context)=>Scaffold(body:pages[index],bottomNavigationBar:NavigationBar(selectedIndex:index,onDestinationSelected:(v)=>setState(()=>index=v),destinations:const [NavigationDestination(icon:Icon(Icons.collections_bookmark_outlined),selectedIcon:Icon(Icons.collections_bookmark),label:'Sammlung'),NavigationDestination(icon:Icon(Icons.document_scanner_outlined),selectedIcon:Icon(Icons.document_scanner),label:'Scanner')])));}
