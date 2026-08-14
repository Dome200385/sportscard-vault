class CardRecord {
  final String id;
  final String sport;
  final String? season;
  final String subject;
  final String? productLine;
  final String? setName;
  final String? cardNumber;
  final String? parallel;
  final bool rookie;

  const CardRecord({required this.id, required this.sport, required this.subject, this.season, this.productLine, this.setName, this.cardNumber, this.parallel, this.rookie=false});

  factory CardRecord.fromJson(Map<String,dynamic> j) => CardRecord(
    id: j['id'] ?? '', sport: j['sport'] ?? '', season: j['season'], subject: j['primary_subject_name'] ?? '',
    productLine: j['product_line'], setName: j['set_name'], cardNumber: j['card_number_printed'], parallel: j['parallel_name'], rookie: j['is_rookie'] == true,
  );
}
