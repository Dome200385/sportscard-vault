from app.market_providers import MarketFingerprint, score_sold_listing, normalize_soldcomps_results


def fp_raw():
    return MarketFingerprint(
        sport='Basketball', subject='Zach LaVine', season=None, release_year=2026,
        manufacturer='Topps', product_line='Topps Chrome Basketball', set_name='Topps Chrome Basketball',
        insert_name='Jacked Up', card_number='JU-25', parallel_name=None, variation_name=None,
        serial_print_run=None, is_rookie=False, is_autograph=False, is_relic=False,
        raw_or_graded='raw', grading_company=None, grade_numeric=None,
    )


def test_sold_listing_accepts_exact_raw_card():
    item={'title':'2025-26 Topps Chrome Basketball Zach LaVine Jacked Up JU-25', 'soldPrice':'18.50','soldCurrency':'USD','shippingPrice':'4.00'}
    m=score_sold_listing(fp_raw(),item)
    assert m['acceptable_for_comp'] is True
    assert m['score'] >= .72


def test_sold_listing_rejects_wrong_number_and_graded():
    item={'title':'2025-26 Topps Chrome Zach LaVine JU-24 PSA 10', 'soldPrice':'80','soldCurrency':'USD'}
    m=score_sold_listing(fp_raw(),item)
    assert m['acceptable_for_comp'] is False
    assert 'card_number' in m['hard_mismatches']
    assert 'graded_listing_for_raw_card' in m['hard_mismatches']


def test_normalizer_marks_extreme_outlier_excluded():
    items=[]
    for idx,price in enumerate([10,11,12,150]):
        items.append({'itemId':str(idx),'title':'2025-26 Topps Chrome Basketball Zach LaVine Jacked Up JU-25','soldPrice':str(price),'soldCurrency':'USD','shippingPrice':'0','totalPrice':str(price)})
    r=normalize_soldcomps_results(fp_raw(),{'query':'x','items':items})
    assert r['matched_count']==4
    assert r['included_count']==3
    assert sum(1 for x in r['matches'] if not x['included_in_valuation'])==1
