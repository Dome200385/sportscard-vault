from app.catalog import rank_catalog

def g(v): return {'value':v,'confidence':.95,'evidence':'test'}

def test_catalog_prefers_exact_parallel_and_number():
    ext={'primary_subject_name':g('Josh Allen'),'card_number_printed':g('12'),'season':g('2024'),'product_line':g('Prizm'),'parallel_name':g('Silver')}
    rows=[
      {'primary_subject_name':'Josh Allen','card_number_printed':'12','season':'2024','product_line':'Prizm','parallel_name':'Silver'},
      {'primary_subject_name':'Josh Allen','card_number_printed':'12','season':'2024','product_line':'Prizm','parallel_name':'Red'},
    ]
    r=rank_catalog(ext,rows)
    assert r[0]['fields']['parallel_name']=='Silver'
    assert r[0]['score']>r[1]['score']
