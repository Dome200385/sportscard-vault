from app.recognition import analyze_locked_context, _requires_confirmation, IDENTITY_FIELDS


def test_safe_mode_keeps_locks_and_does_not_guess():
    out=analyze_locked_context({'sport':'Basketball','season':'2024-25','product_line':'Prizm'})
    assert out['extracted']['sport']['value']=='Basketball'
    assert out['extracted']['sport']['confidence']==1.0
    assert out['extracted']['parallel_name']['value'] is None
    assert 'parallel_name' in out['requires_confirmation']
    assert out['mode']=='safe-scaffold'
    assert set(out['extracted'])==set(IDENTITY_FIELDS)


def test_parallel_needs_high_confidence():
    extracted={
        'sport': {'value':'Basketball','confidence':.99},
        'season': {'value':'2024-25','confidence':.99},
        'manufacturer': {'value':'Panini','confidence':.99},
        'product_line': {'value':'Prizm','confidence':.99},
        'set_name': {'value':'Prizm','confidence':.99},
        'card_number_printed': {'value':'123','confidence':.99},
        'primary_subject_name': {'value':'Example Player','confidence':.99},
        'parallel_name': {'value':'Silver Prizm','confidence':.90},
        'variation_name': {'value':None,'confidence':0},
        'serial_print_run': {'value':None,'confidence':0},
    }
    required=_requires_confirmation(extracted)
    assert 'parallel_name' in required
    assert 'variation_name' not in required


def test_no_market_value_field_in_recognition_schema():
    forbidden={'price','market_value','estimated_value','valuation'}
    assert not (forbidden & set(IDENTITY_FIELDS))
