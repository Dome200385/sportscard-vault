import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../services/api_service.dart';

class ScannerScreen extends StatefulWidget {
  const ScannerScreen({super.key});
  @override State<ScannerScreen> createState()=>_ScannerScreenState();
}

class _ScannerScreenState extends State<ScannerScreen> {
  final picker=ImagePicker();
  final api=ApiService();
  File? front;
  File? back;
  bool busy=false;
  Map<String,dynamic>? result;
  String? error;
  String? lockedSport;
  final season=TextEditingController();
  final productLine=TextEditingController();

  Future<void> pick(bool isFront) async {
    final x=await picker.pickImage(source:ImageSource.camera,imageQuality:92,maxWidth:2200);
    if(x==null) return;
    setState(() { if(isFront) front=File(x.path); else back=File(x.path); result=null; error=null; });
  }

  Map<String,dynamic> get locks=>{
    if(lockedSport!=null) 'sport':lockedSport,
    if(season.text.trim().isNotEmpty) 'season':season.text.trim(),
    if(productLine.text.trim().isNotEmpty) 'product_line':productLine.text.trim(),
  };

  Future<void> analyze() async {
    if(front==null) return;
    setState(()=>{busy=true,error=null});
    try {
      final r=await api.analyzeScan(front:front!,back:back,lockedContext:locks);
      if(!mounted) return;
      setState(()=>result=r);
    } catch(e) {
      setState(()=>error=e.toString());
    } finally {
      if(mounted) setState(()=>busy=false);
    }
  }

  @override void dispose(){season.dispose();productLine.dispose();super.dispose();}

  @override Widget build(BuildContext context)=>Scaffold(
    appBar:AppBar(title:const Text('Karte scannen')),
    body:ListView(padding:const EdgeInsets.all(16),children:[
      const Text('V0.2 · Front + Rückseite',style:TextStyle(fontSize:22,fontWeight:FontWeight.bold)),
      const SizedBox(height:6),
      const Text('Je mehr eindeutige Informationen sichtbar sind, desto genauer werden Set, Kartennummer, Parallel und Variation erkannt.'),
      const SizedBox(height:16),
      Row(children:[
        Expanded(child:_ImageTile(label:'Vorderseite',file:front,onTap:()=>pick(true))),
        const SizedBox(width:12),
        Expanded(child:_ImageTile(label:'Rückseite',file:back,onTap:()=>pick(false))),
      ]),
      const SizedBox(height:16),
      ExpansionTile(title:const Text('Fast-Scan Kontext (optional)'),children:[
        DropdownButtonFormField<String>(value:lockedSport,decoration:const InputDecoration(labelText:'Sport'),items:['Basketball','American Football','Baseball','Eishockey','Fussball','Formula 1','UFC / Boxing','Tennis','Golf'].map((s)=>DropdownMenuItem(value:s,child:Text(s))).toList(),onChanged:(v)=>setState(()=>lockedSport=v)),
        const SizedBox(height:8),
        TextField(controller:season,decoration:const InputDecoration(labelText:'Saison, z.B. 2024-25')),
        const SizedBox(height:8),
        TextField(controller:productLine,decoration:const InputDecoration(labelText:'Produkt, z.B. Prizm / Select / Optic')),
        const SizedBox(height:12),
      ]),
      FilledButton.icon(onPressed:busy||front==null?null:analyze,icon:busy?const SizedBox(width:18,height:18,child:CircularProgressIndicator(strokeWidth:2)):const Icon(Icons.auto_awesome),label:Text(busy?'Analysiere...':'Karte analysieren')),
      if(error!=null) Padding(padding:const EdgeInsets.only(top:12),child:Text(error!,style:TextStyle(color:Theme.of(context).colorScheme.error))),
      if(result!=null) ...[const SizedBox(height:18),ScanReview(result:result!)],
    ]),
  );
}

class _ImageTile extends StatelessWidget {
  final String label; final File? file; final VoidCallback onTap;
  const _ImageTile({required this.label,required this.file,required this.onTap});
  @override Widget build(BuildContext context)=>AspectRatio(aspectRatio:.72,child:InkWell(onTap:onTap,borderRadius:BorderRadius.circular(16),child:Ink(decoration:BoxDecoration(borderRadius:BorderRadius.circular(16),border:Border.all(color:Theme.of(context).colorScheme.outlineVariant)),child:file==null?Column(mainAxisAlignment:MainAxisAlignment.center,children:[const Icon(Icons.add_a_photo_outlined,size:38),const SizedBox(height:8),Text(label)]):ClipRRect(borderRadius:BorderRadius.circular(15),child:Stack(fit:StackFit.expand,children:[Image.file(file!,fit:BoxFit.cover),Align(alignment:Alignment.bottomCenter,child:Container(width:double.infinity,padding:const EdgeInsets.all(8),color:Colors.black54,child:Text(label,style:const TextStyle(color:Colors.white),textAlign:TextAlign.center)))]) ))));
}

class ScanReview extends StatelessWidget {
  final Map<String,dynamic> result;
  const ScanReview({super.key,required this.result});
  @override Widget build(BuildContext context){
    final extracted=(result['extracted'] as Map?)?.cast<String,dynamic>()??{};
    final required=(result['requires_confirmation'] as List?)?.cast<dynamic>()??[];
    final warnings=(result['warnings'] as List?)?.cast<dynamic>()??[];
    const priority=['primary_subject_name','season','manufacturer','product_line','set_name','insert_name','card_number_printed','parallel_name','variation_name','serial_print_run','team_name'];
    return Card(child:Padding(padding:const EdgeInsets.all(16),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Row(children:[Expanded(child:Text('Ergebnis · ${(100*((result['overall_confidence']??0) as num)).round()} %',style:const TextStyle(fontSize:18,fontWeight:FontWeight.bold))),Chip(label:Text('${required.length} prüfen'))]),
      if(warnings.isNotEmpty) ...warnings.map((w)=>Padding(padding:const EdgeInsets.only(bottom:6),child:Text('⚠ $w'))),
      const Divider(),
      ...priority.where((k)=>extracted.containsKey(k)).map((k){final g=(extracted[k] as Map).cast<String,dynamic>();final v=g['value'];final c=((g['confidence']??0) as num).toDouble();return ListTile(dense:true,contentPadding:EdgeInsets.zero,title:Text(_label(k)),subtitle:Text(v==null?'Nicht erkannt':v.toString()),trailing:Text('${(c*100).round()}%',style:TextStyle(fontWeight:FontWeight.bold,color:c>=.95?Colors.green:c>=.75?Colors.orange:Colors.red)));}),
      if(required.isNotEmpty) Container(margin:const EdgeInsets.only(top:8),padding:const EdgeInsets.all(12),decoration:BoxDecoration(borderRadius:BorderRadius.circular(12),color:Theme.of(context).colorScheme.errorContainer),child:Text('Vor dem Speichern bestätigen: ${required.join(', ')}')),
      const SizedBox(height:8),
      const Text('V0.2 speichert Scan-Ergebnisse noch nicht automatisch. Unsichere Angaben müssen zuerst bestätigt werden.',style:TextStyle(fontSize:12)),
    ])));
  }
  static String _label(String k)=>const {
    'primary_subject_name':'Spieler / Motiv','season':'Saison','manufacturer':'Hersteller','product_line':'Produkt','set_name':'Set','insert_name':'Insert','card_number_printed':'Kartennummer','parallel_name':'Parallel','variation_name':'Variation','serial_print_run':'Print Run','team_name':'Team'
  }[k]??k;
}
