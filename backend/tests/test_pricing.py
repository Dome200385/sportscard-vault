from app.pricing import Comp, calculate_valuation

def test_two_comps_never_create_fantasy_value():
    v=calculate_valuation([Comp(10,"USD"),Comp(12,"USD")],3)
    assert not v.reliable and v.median_value is None and v.low_value==10 and v.high_value==12

def test_three_comps_use_median():
    v=calculate_valuation([Comp(10,"USD"),Comp(12,"USD"),Comp(30,"USD")],3)
    assert v.reliable and v.median_value==12

def test_mixed_currency_is_rejected():
    v=calculate_valuation([Comp(10,"USD"),Comp(12,"CHF"),Comp(11,"USD")],3)
    assert not v.reliable and v.median_value is None
