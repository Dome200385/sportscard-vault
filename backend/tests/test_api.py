import os, tempfile
fd,path=tempfile.mkstemp(suffix='.db'); os.close(fd)
os.environ['DATABASE_PATH']=path
from fastapi.testclient import TestClient
from app.main import app

SAMPLE={"identity":{"sport":"basketball","season":"2024-25","manufacturer":"Panini","product_line":"Prizm","set_name":"Base","card_number_printed":"123","primary_subject_name":"Test Player","parallel_name":"Silver","is_rookie":True},"instance":{"quantity":1,"raw_or_graded":"raw","storage_location":"Box A"}}

def test_manual_card_collection_and_pricing():
    with TestClient(app) as c:
        r=c.post('/api/v1/cards/manual',json=SAMPLE); assert r.status_code==200
        card_id=r.json()['card_identity_id']
        col=c.get('/api/v1/collection?q=Test'); assert col.json()['total']==1
        for p in (10,12,30):
            assert c.post(f'/api/v1/cards/{card_id}/comps/manual',json={"source":"manual verified","price":p,"currency":"CHF"}).status_code==200
        v=c.get(f'/api/v1/cards/{card_id}/valuation').json(); assert v['reliable'] and v['median_value']==12

def test_scan_safe_mode_returns_detailed_confirmation_fields():
    with TestClient(app) as c:
        r=c.post(
            '/api/v1/scan/analyze',
            files={'front_image':('front.jpg',b'not-a-real-image','image/jpeg')},
            data={'locked_context':'{"sport":"Basketball","season":"2024-25","product_line":"Prizm"}'},
        )
        assert r.status_code==200
        body=r.json()
        assert body['extracted']['sport']['value']=='Basketball'
        assert body['extracted']['parallel_name']['value'] is None
        assert 'parallel_name' in body['requires_confirmation']
        assert 'serial_number_actual' in body['instance_extracted']
        assert body['mode'] in ('safe-scaffold','safe-fallback')

def test_exact_identity_is_reused_for_multiple_owned_copies():
    with TestClient(app) as c:
        first=c.post('/api/v1/cards/manual',json={**SAMPLE, "identity":{**SAMPLE["identity"], "primary_subject_name":"Duplicate Test"}})
        second=c.post('/api/v1/cards/manual',json={**SAMPLE, "identity":{**SAMPLE["identity"], "primary_subject_name":"Duplicate Test"}, "instance":{**SAMPLE["instance"], "storage_location":"Box B"}})
        assert first.status_code==200 and second.status_code==200
        assert first.json()['card_identity_id']==second.json()['card_identity_id']
        assert second.json()['reused_identity'] is True
        assert second.json()['duplicate_count']==2
        col=c.get('/api/v1/collection?q=Duplicate%20Test').json()
        assert col['total']==1
        detail=c.get(f"/api/v1/cards/{first.json()['card_identity_id']}").json()
        assert len(detail['instances'])==2
