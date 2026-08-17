import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/card_record.dart';

class ApiService {
  String baseUrl;
  ApiService({this.baseUrl='http://10.0.2.2:8000'});

  Future<List<CardRecord>> collection({String? q}) async {
    final uri=Uri.parse('$baseUrl/api/v1/collection').replace(queryParameters: q==null||q.isEmpty?null:{'q':q});
    final r=await http.get(uri);
    if(r.statusCode!=200) throw Exception('API ${r.statusCode}: ${r.body}');
    return (jsonDecode(r.body)['items'] as List).map((e)=>CardRecord.fromJson(e)).toList();
  }

  Future<Map<String,dynamic>> addManual(Map<String,dynamic> payload) async {
    final r=await http.post(Uri.parse('$baseUrl/api/v1/cards/manual'),headers:{'content-type':'application/json'},body:jsonEncode(payload));
    if(r.statusCode!=200) throw Exception(r.body);
    return jsonDecode(r.body);
  }

  Future<Map<String,dynamic>> analyzeScan({
    required File front,
    File? back,
    Map<String,dynamic> lockedContext=const {},
  }) async {
    final req=http.MultipartRequest('POST', Uri.parse('$baseUrl/api/v1/scan/analyze'));
    req.files.add(await http.MultipartFile.fromPath('front_image', front.path));
    if(back!=null) req.files.add(await http.MultipartFile.fromPath('back_image', back.path));
    req.fields['locked_context']=jsonEncode(lockedContext);
    final streamed=await req.send();
    final r=await http.Response.fromStream(streamed);
    if(r.statusCode!=200) throw Exception('Scan ${r.statusCode}: ${r.body}');
    return jsonDecode(r.body) as Map<String,dynamic>;
  }

  Future<Map<String,dynamic>> confirmScan({
    required String scanId,
    required Map<String,dynamic> identity,
    required Map<String,dynamic> instance,
  }) async {
    final r=await http.post(
      Uri.parse('$baseUrl/api/v1/cards/confirm-scan'),
      headers:{'content-type':'application/json'},
      body:jsonEncode({'scan_id':scanId,'identity':identity,'instance':instance}),
    );
    if(r.statusCode!=200) throw Exception('Confirm ${r.statusCode}: ${r.body}');
    return jsonDecode(r.body) as Map<String,dynamic>;
  }
}
