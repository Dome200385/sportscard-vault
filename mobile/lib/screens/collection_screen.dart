import 'package:flutter/material.dart';
import '../models/card_record.dart';
import '../services/api_service.dart';

class CollectionScreen extends StatefulWidget { const CollectionScreen({super.key}); @override State<CollectionScreen> createState()=>_CollectionScreenState(); }
class _CollectionScreenState extends State<CollectionScreen>{
 final api=ApiService(); late Future<List<CardRecord>> cards;
 @override void initState(){super.initState();cards=api.collection();}
 void reload(){setState(()=>cards=api.collection());}
 @override Widget build(BuildContext context)=>Scaffold(
   appBar:AppBar(title:const Text('Meine Sammlung'),actions:[IconButton(onPressed:reload,icon:const Icon(Icons.refresh))]),
   body:FutureBuilder<List<CardRecord>>(future:cards,builder:(context,s){
     if(s.connectionState!=ConnectionState.done)return const Center(child:CircularProgressIndicator());
     if(s.hasError)return Center(child:Padding(padding:const EdgeInsets.all(24),child:Text('Backend noch nicht erreichbar.\n${s.error}',textAlign:TextAlign.center)));
     final data=s.data??[]; if(data.isEmpty)return const Center(child:Text('Noch keine Karten. Über + detailliert erfassen.'));
     return ListView.separated(itemCount:data.length,separatorBuilder:(_,__)=>const Divider(height:1),itemBuilder:(_,i){final c=data[i];return ListTile(
       leading:CircleAvatar(child:Text(c.sport.isEmpty?'?':c.sport[0].toUpperCase())),
       title:Text(c.subject), subtitle:Text([c.season,c.productLine,c.setName,c.cardNumber==null?null:'#${c.cardNumber}',c.parallel].whereType<String>().where((e)=>e.isNotEmpty).join(' · ')),
       trailing:c.rookie?const Chip(label:Text('RC')):null,
     );});
   }),
   floatingActionButton:FloatingActionButton.extended(onPressed:()=>Navigator.pushNamed(context,'/add').then((_){reload();}),icon:const Icon(Icons.add),label:const Text('Karte')),
 );
}
