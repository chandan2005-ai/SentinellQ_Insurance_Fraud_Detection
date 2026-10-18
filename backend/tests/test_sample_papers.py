"""Regression tests using the actual three fictional papers delivered to the user."""
from pathlib import Path
import pytest
from app.insurance_types.registry import COMMON,SPECIFIC
from app.document_processing.processor import process_document

ROOT=Path(__file__).resolve().parents[2]
PAPERS={
 'motor': ROOT/'sample_data/claim_papers/01_Motor_Insurance_Claim_SAMPLE.pdf',
 'health': ROOT/'sample_data/claim_papers/02_Health_Insurance_Claim_SAMPLE.pdf',
 'travel': ROOT/'sample_data/claim_papers/03_Travel_Insurance_Claim_SAMPLE.pdf',
}

@pytest.mark.parametrize('category',list(PAPERS))
def test_sample_pdf_extraction(category):
    paper=PAPERS[category]
    d=process_document(paper.read_bytes(),paper.name,'demo-test')
    e={key:v['value'] for key,v in d['extracted'].items()}
    assert e['insurance_category'].lower()==category
    assert e['policy_number']==f'DEMO-{category.upper()}-001'
    assert e['claim_amount']>0
    assert e['coverage_amount']>0
    assert 'reported_date' in e and 'prior_claims' in e
    if category=='health': assert (e['admission_date'],e['discharge_date'])==('2026-06-14','2026-06-16')
    if category=='travel': assert (e['trip_start'],e['trip_end'])==('2026-08-10','2026-08-20')


def test_prepare_models_upload_review_analyze_three_pdfs(client,auth):
    response=client.post('/api/admin/demo-models',headers=auth,
             json={'categories':['motor','health','travel']})
    assert response.status_code==200,response.text
    assert [x['status'] for x in response.json()['results']]==['trained_and_deployed']*3
    repeated=client.post('/api/admin/demo-models',headers=auth,
             json={'categories':['motor','health','travel']}).json()
    assert all(x['status']=='already_active' for x in repeated['results'])
    for category,paper in PAPERS.items():
        extracted=process_document(paper.read_bytes(),paper.name,'local')
        values={key:e['value'] for key,e in extracted['extracted'].items() if key in COMMON|SPECIFIC[category]}
        new=client.post('/api/cases',headers=auth,json={'category':category,'data':{'policy_number':values['policy_number'],
            'incident_date':values['incident_date'],'claim_amount':values['claim_amount']}})
        assert new.status_code==201,new.text
        id_=new.json()['id']
        upload=client.post(f'/api/cases/{id_}/documents',headers=auth,
             files={'file':(paper.name,paper.read_bytes(),'application/pdf')})
        assert upload.status_code==201,upload.text
        update=client.patch(f'/api/cases/{id_}',headers=auth,
             json={'category':category,'data':values})
        assert update.status_code==200,update.text
        outcome=client.post(f'/api/cases/{id_}/analyze',headers=auth)
        assert outcome.status_code==200,outcome.text
        result=outcome.json()['result']
        assert result['data_completeness_pct']==100
        assert result['model_input_completeness_pct']==100
        assert not result['missing_model_inputs']
        assert result['model']['status'] in ('demo_inference','out_of_distribution')
        assert result['model'].get('training_data_kind')=='synthetic_demo'
        assert not any(r['code']=='source_field_conflict' for r in result['rules'])
        assert not any(r['code']=='document_category_mismatch' for r in result['rules'])
        if result['model']['status']=='demo_inference':
            assert isinstance(result['fraud_suspicion_score'],float)
            assert result['underwriting_risk_score'] is None
        else: assert result['fraud_suspicion_score'] is None
        print('PDF CATEGORY',category,'MODEL STATUS',result['model']['status'],
              'DEMO INDEX',result['fraud_suspicion_score'])


def test_category_specific_checks(client,auth):
    for category,extra,expected in [
        ('health',{'admission_date':'2026-06-20','discharge_date':'2026-06-11'},'invalid_hospital_stay'),
        ('travel',{'trip_start':'2026-06-20','trip_end':'2026-06-01'},'invalid_trip_dates')]:
        d={'policy_number':'EXAMPLE','claim_amount':1500,'incident_date':'2026-06-14',**extra}
        c=client.post('/api/cases',headers=auth,json={'category':category,'data':d}).json()['id']
        r=client.post(f'/api/cases/{c}/analyze',headers=auth).json()['result']
        assert expected in {x['code'] for x in r['rules']}


def test_synthetic_demo_admin_only(client,analyst):
    r=client.post('/api/admin/demo-models',headers=analyst,json={'categories':['health']})
    assert r.status_code==403
