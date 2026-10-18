import io
import fitz
from PIL import Image
from app.document_processing.processor import process_document,hamming
from app.training.tabular import inspect_csv,train_tabular,predict_case,features_from_case
from app.core.config import ROOT
from app.database.db import SessionLocal
from app.database.models import Case


def _pdf(text):
    doc=fitz.open();page=doc.new_page();page.insert_text((40,40),text,fontsize=10);data=doc.tobytes();doc.close();return data

def _png(color='white'):
    b=io.BytesIO();Image.new('RGB',(600,500),color).save(b,format='PNG');return b.getvalue()

def test_categories_and_health(client,auth):
    assert client.get('/api/health').json()['status']=='ok'
    data=client.get('/api/insurance-types',headers=auth).json()
    assert len(data)==14
    assert data['health']['fields']['hospital_name']=='text'
    assert data['marine']['default_model_readiness']=='unavailable_until_trained'

def test_auth_denial(client):
    assert client.get('/api/cases').status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@example.test','password':'wrong'}).status_code==401

def test_manual_case_and_analysis_unavailable(client,auth,motor_case):
    result=client.post(f'/api/cases/{motor_case}/analyze',headers=auth).json()['result']
    assert result['model']['status']=='unavailable'
    assert result['fraud_suspicion_score'] is None
    assert result['underwriting_risk_score'] is None
    assert result['decision_band']=='unavailable'
    assert result['data_completeness_pct']==100
    assert client.get(f'/api/cases/{motor_case}',headers=auth).json()['analyses']
    assert client.get('/api/dashboard',headers=auth).json()['total_cases']==1

def test_malformed_manual_fields(client,auth):
    bad=client.post('/api/cases',headers=auth,json={'category':'motor','data':{'claim_amount':-100}})
    assert bad.status_code==422
    bad2=client.post('/api/cases',headers=auth,json={'category':'motor','data':{'bad_unknown':'x'}})
    assert bad2.status_code==422
    bad3=client.post('/api/cases',headers=auth,json={'category':'invalid','data':{}})
    assert bad3.status_code==422

def test_reference_uniqueness(client,auth,motor_case):
    response=client.post('/api/cases',headers=auth,json={'category':'motor','external_ref':'DEMO-CASE-1','data':{}})
    assert response.status_code==409

def test_pdf_extraction_and_source_mismatch(client,auth,motor_case):
    file=_pdf('Policy number: MOTOR-123\nClaim amount: 50000\nInvoice total: 20000\nIncident date: 2026-07-08')
    response=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':('invoice.pdf',file,'application/pdf')})
    assert response.status_code==201,response.text
    assert response.json()['extracted']['claim_amount']['value']==50000
    assert response.json()['extracted']['claim_amount']['page']==1
    result=client.post(f'/api/cases/{motor_case}/analyze',headers=auth).json()['result']
    assert any(r['code']=='source_field_conflict' for r in result['rules'])

def test_corrupt_or_malicious_upload(client,auth,motor_case):
    for name,data in [('wrong.pdf',b'garbage'),('evil.exe',b'MZbad'),('broken.png',b'bad'),('sample.docx',b'fake-zip')]:
        r=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':(name,data)})
        assert r.status_code==422,(name,r.text)
    big=b'P'+b'X'*(10*1024*1024+1)
    r=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':('oversized.pdf',big)})
    assert r.status_code==413

def test_duplicate_document_across_cases(client,auth,motor_case):
    a=client.post('/api/cases',headers=auth,json={'category':'motor','data':{'policy_number':'OTHER'}}).json()['id']
    payload=_pdf('Policy number: MOTOR-123')
    for caseid in [motor_case,a]:
        r=client.post(f'/api/cases/{caseid}/documents',headers=auth,files={'file':('test.pdf',payload)})
        assert r.status_code==201,r.text
    result=client.post(f'/api/cases/{a}/analyze',headers=auth).json()['result']
    assert any(r['code']=='duplicate_evidence_across_cases' for r in result['rules'])
    related=client.get(f'/api/cases/{a}/related',headers=auth).json()['items']
    assert len(related)==1

def test_image_upload_and_quality(client,auth,motor_case):
    image=_png()
    r=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':('damage.png',image)})
    assert r.status_code==201,r.text
    assessment=r.json()['image_assessment']
    assert assessment['width']==600
    assert len(assessment['dhash'])==16
    assert hamming('ff00ff00ff00ff00','ff00ff00ff00ff00')==0

def test_rule_date_and_missing(client,auth):
    case=client.post('/api/cases',headers=auth,json={'category':'health','data':{'policy_number':'ABC123',
         'incident_date':'2026-05-02','policy_start':'2026-06-01','policy_end':'2026-12-31',
         'claim_amount':2000,'invoice_total':10000}}).json()['id']
    result=client.post(f'/api/cases/{case}/analyze',headers=auth).json()['result']
    codes={r['code'] for r in result['rules']}
    assert {'coverage_date_check','invoice_amount_gap'}<=codes
    assert result['model']['status']=='unavailable'

def test_no_cross_user_data_leak(client,auth,analyst,motor_case):
    assert client.get('/api/cases/'+motor_case,headers=analyst).status_code==404
    assert client.post('/api/cases/'+motor_case+'/analyze',headers=analyst).status_code==404
    assert client.get('/api/dashboard',headers=analyst).json()['total_cases']==0
    assert client.get('/api/admin/audit',headers=analyst).status_code==403

def test_download_and_delete_authorization(client,auth,analyst,motor_case):
    d=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':('d.png',_png())}).json()['document_id']
    assert client.get('/api/documents/'+d+'/download',headers=analyst).status_code==404
    assert client.get('/api/documents/'+d+'/download',headers=auth).status_code==200
    assert client.delete('/api/documents/'+d,headers=auth).status_code==200
    assert client.get('/api/documents/'+d+'/download',headers=auth).status_code==404

def test_csv_data_quality_and_train(tmp_path):
    source=ROOT/'sample_data'/'motor_SYNTHETIC.csv'
    assert source.is_file()
    quality=inspect_csv(source)
    assert quality['rows']==600
    dest=tmp_path/'trained.joblib'
    report=train_tabular(source,dest)
    assert report['held_out_test']['n']>0
    assert report['algorithm'] in ['xgboost','scikit_learn_logistic']
    assert dest.exists()
    prediction=predict_case({'claim_amount':15000,'coverage_amount':100000,'invoice_total':14900,
       'prior_claims':1,'incident_date':'2026-02-01','reported_date':'2026-02-02'},dest)
    assert prediction['status']=='demo_inference'
    assert 0<=prediction['uncalibrated_model_score']<=100

def test_admin_training_deployment_end_to_end(client,auth,motor_case):
    file=(ROOT/'sample_data'/'motor_SYNTHETIC.csv').read_bytes()
    f={'file':('training.csv',file,'text/csv')}
    body={'category':'motor','source':'Synthetic generator','label_definition':'Simulated outcomes',
          'permitted_use':'Datathon demo','synthetic':'true'}
    r=client.post('/api/admin/datasets',headers=auth,files=f,data=body)
    assert r.status_code==201,r.text
    dataset_id=r.json()['id']
    train=client.post('/api/admin/train/'+dataset_id,headers=auth)
    assert train.status_code==200,train.text
    modelid=train.json()['model_id']
    deploy=client.post('/api/admin/models/'+modelid+'/deploy',headers=auth)
    assert deploy.status_code==200,deploy.text
    result=client.post(f'/api/cases/{motor_case}/analyze',headers=auth).json()['result']
    assert result['fraud_suspicion_score'] is not None
    assert result['model']['training_data_kind']=='synthetic_demo'
    assert result['model']['calibrated'] is False
    # Unsupported category must never acquire a fraud score by borrowing the motor model.
    case=client.post('/api/cases',headers=auth,json={'category':'health','data':{'claim_amount':2500}}).json()['id']
    health=client.post(f'/api/cases/{case}/analyze',headers=auth).json()['result']
    assert health['fraud_suspicion_score'] is None

def test_image_model_explicitly_unavailable(tmp_path):
    from app.image_classifier.model import classify_image
    assert classify_image(_png(),tmp_path/'missing.pt')['status']=='unavailable'

def test_human_corrected_field_provenance(client,auth,motor_case):
    file=_pdf('Policy number: MOTOR-123\nClaim amount: 50000')
    response=client.post(f'/api/cases/{motor_case}/documents',headers=auth,files={'file':('invoice.pdf',file)})
    assert response.status_code==201
    old=client.get(f'/api/cases/{motor_case}',headers=auth).json()
    corrected=dict(old['data']);corrected['claim_amount']=15000
    upd=client.patch(f'/api/cases/{motor_case}',headers=auth,json={'category':'motor','data':corrected})
    assert upd.status_code==200,upd.text
    doc=upd.json()['documents'][0]['extracted']
    assert doc['claim_amount']['validated'] is True
    assert doc['claim_amount']['human_corrected'] is True
    assert doc['policy_number']['validated'] is True
    assert doc['policy_number']['human_corrected'] is False

def test_deployment_rollback(client,auth):
    from app.core.config import DATA_DIR
    from app.database.models import Dataset,ModelVersion
    from app.database.db import SessionLocal
    from uuid import uuid4
    with SessionLocal() as db:
        ds=Dataset(category='motor',source='synthetic',label_definition='simulated',permitted_use='demo',
                   is_synthetic=True,file_name='none.csv',quality={})
        db.add(ds);db.flush()
        a,b=str(uuid4()),str(uuid4());(DATA_DIR/'model_artifacts'/f'{a}.joblib').write_bytes(b'test placeholder')
        (DATA_DIR/'model_artifacts'/f'{b}.joblib').write_bytes(b'test placeholder')
        db.add(ModelVersion(id=a,category='motor',artifact_name=f'{a}.joblib',dataset_id=ds.id,deployed=True,is_synthetic=True))
        db.add(ModelVersion(id=b,category='motor',artifact_name=f'{b}.joblib',dataset_id=ds.id,deployed=False,is_synthetic=True))
        db.commit()
    assert client.post('/api/admin/models/'+b+'/deploy',headers=auth).status_code==200
    assert client.post('/api/admin/models/'+a+'/deploy',headers=auth).status_code==200
    active=[m for m in client.get('/api/models',headers=auth).json() if m['deployed']]
    assert len(active)==1 and active[0]['id']==a

def test_frontend_served_same_origin(client):
    html=client.get('/')
    assert html.status_code==200
    assert 'SentinelIQ' in html.text
    js=client.get('/assets/js/app.js')
    assert js.status_code==200 and 'uploadDoc' in js.text
    css=client.get('/assets/css/main.css')
    assert css.status_code==200 and '[hidden]' in css.text

def test_sparse_case_abstains_even_if_model_exists(tmp_path):
    source=ROOT/'sample_data'/'motor_SYNTHETIC.csv'
    output=tmp_path/'trained_sparse.joblib'
    train_tabular(source,output)
    prediction=predict_case({'claim_amount':19000},output)
    assert prediction['status']=='insufficient_data'
    assert 'uncalibrated_model_score' not in prediction

def test_scoring_settings_admin_only(client,auth,analyst):
    assert client.get('/api/admin/settings',headers=analyst).status_code==403
    old=client.get('/api/admin/settings',headers=auth).json()
    assert old['scoring_policy']['model_weight']==.8
    form={'model_weight':'0.7','low':'20','moderate':'45','high':'80'}
    r=client.post('/api/admin/settings',headers=auth,data=form)
    assert r.status_code==200,r.text
    assert client.get('/api/admin/settings',headers=auth).json()['scoring_policy']['thresholds']['high']==80
    bad=client.post('/api/admin/settings',headers=auth,data={'model_weight':'1.1','low':'50','moderate':'45','high':'80'})
    assert bad.status_code==422
