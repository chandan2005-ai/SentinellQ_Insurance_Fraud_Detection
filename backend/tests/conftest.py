import os,sys,tempfile
from pathlib import Path
TEST_DATA=tempfile.TemporaryDirectory(prefix='insurance_test_')
os.environ['DATA_DIR']=TEST_DATA.name
os.environ['DATABASE_URL']='sqlite:///'+TEST_DATA.name+'/test.db'
os.environ['JWT_SECRET']='ONLY_FOR_TEST_12345678901234567890123456789'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from fastapi.testclient import TestClient
from app.database.db import Base,engine,SessionLocal
from app.database.models import User
from app.security.auth import hash_password
from app.main import app, login_hits

@pytest.fixture
def client():
    login_hits.clear()
    Base.metadata.drop_all(bind=engine);Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        db.add(User(email='admin@example.test',password_hash=hash_password('test_password_123!'),role='admin'))
        db.add(User(email='user@example.test',password_hash=hash_password('test_password_123!'),role='analyst'))
        db.commit()
    with TestClient(app) as c:yield c

@pytest.fixture
def auth(client):
    response=client.post('/api/auth/login',json={'email':'admin@example.test','password':'test_password_123!'})
    assert response.status_code==200,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}

@pytest.fixture
def analyst(client):
    response=client.post('/api/auth/login',json={'email':'user@example.test','password':'test_password_123!'})
    assert response.status_code==200
    return {'Authorization':'Bearer '+response.json()['access_token']}

@pytest.fixture
def motor_case(client,auth):
    r=client.post('/api/cases',json={'category':'motor','kind':'claim','external_ref':'DEMO-CASE-1',
         'data':{'policy_number':'MOTOR-123','incident_date':'2026-07-08','reported_date':'2026-07-09',
                 'policy_start':'2026-01-01','policy_end':'2026-12-31','claim_amount':15000,
                 'invoice_total':15000,'coverage_amount':100000,'prior_claims':0}},headers=auth)
    assert r.status_code==201,r.text
    return r.json()['id']
