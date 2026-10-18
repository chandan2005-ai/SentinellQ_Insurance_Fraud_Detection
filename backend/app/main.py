"""Authenticated API and static SPA. Start: uvicorn app.main:app --app-dir backend"""
import json, os, shutil, time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
from collections import defaultdict,deque
from fastapi import FastAPI,Depends,HTTPException,UploadFile,File,Form,Query,Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session
from pydantic import ValidationError
from app.core.config import ROOT,DATA_DIR,MAX_UPLOAD_MB,CORS_ORIGIN,check_secret
from app.database.db import engine,Base,get_db
from app.database.models import User,Case,Document,Analysis,Dataset,ModelVersion,AuditEvent,Setting
from app.security.auth import verify_password,token_for,current_user,admin
from app.api.schemas import Login, CaseCreate, validate_case_data
from app.insurance_types.registry import registry
from app.document_processing.processor import process_document
from app.image_classifier.model import classify_image
from app.services.scoring import analyze,scoring_policy
from app.training.tabular import inspect_csv,train_tabular,FEATURES
from app.training.demo import provision_synthetic
from pydantic import BaseModel
from app.audit.events import record

@asynccontextmanager
async def lifespan(app):
    check_secret()
    # Migrations are recommended; create_all permits first-run local development.
    Base.metadata.create_all(bind=engine)
    yield

app=FastAPI(title='Insurance Evidence & Risk Decision Support',version='0.1.0',lifespan=lifespan,
            description='Research/demo decision support; never autonomous fraud determination.')
if CORS_ORIGIN: app.add_middleware(CORSMiddleware,allow_origins=[CORS_ORIGIN],allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])

# Single-process login throttling. Add Redis/reverse-proxy limits in real deployment.
login_hits=defaultdict(deque)

def check_login_limit(request):
    addr=request.client.host if request.client else 'unknown'
    q=login_hits[addr]; t=time.monotonic()
    while q and t-q[0]>60: q.popleft()
    if len(q)>=10: raise HTTPException(429,'Too many login attempts. Try again later.')
    q.append(t)

def visible_case(db,case_id,user):
    c=db.get(Case,case_id)
    if not c or (user.role!='admin' and c.created_by!=user.id): raise HTTPException(404,'Case not found')
    return c

def serialize_case(c,full=False):
    r={'id':c.id,'category':c.category,'kind':c.kind,'external_ref':c.external_ref,
       'status':c.status,'outcome':c.outcome,'created_at':c.created_at.isoformat(),
       'updated_at':c.updated_at.isoformat(),'document_count':len(c.documents),
       'latest_score':c.analyses[-1].result.get('fraud_suspicion_score') if c.analyses else None}
    if full:
        r['data']=c.data
        r['documents']=[{'id':d.id,'name':d.original_name,'bytes':d.bytes,'mime':d.mime,
             'sha256':d.sha256,'extracted':d.extracted,'warnings':d.warnings,
             'image_assessment':d.image_assessment,'uploaded_at':d.uploaded_at.isoformat()} for d in c.documents]
        r['analyses']=[{'id':a.id,'created_at':a.created_at.isoformat(),'elapsed_ms':a.elapsed_ms,
                        'result':a.result} for a in c.analyses]
    return r

@app.post('/api/auth/login')
def login(body:Login, request:Request, db:Session=Depends(get_db)):
    check_login_limit(request)
    user=db.scalar(select(User).where(User.email==body.email.lower()))
    if not user or not user.active or not verify_password(body.password,user.password_hash): raise HTTPException(401,'Invalid credentials')
    record(db,user.id,'login',user.id); db.commit()
    return {'access_token':token_for(user),'token_type':'bearer','role':user.role}

@app.get('/api/auth/me')
def me(user:User=Depends(current_user)):
    return {'id':user.id,'email':user.email,'role':user.role}

@app.get('/api/insurance-types')
def types(user:User=Depends(current_user),db:Session=Depends(get_db)):
    result=registry()
    for model in db.scalars(select(ModelVersion).where(ModelVersion.deployed.is_(True))):
        result[model.category]['default_model_readiness']='synthetic_demo_only' if model.is_synthetic else 'trained_not_externally_validated'
    return result

@app.post('/api/cases',status_code=201)
def create_case(body:CaseCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    try: data=validate_case_data(body.category,body.data)
    except ValueError as e: raise HTTPException(422,str(e))
    if body.external_ref:
        exists=db.scalar(select(Case).where(Case.created_by==user.id,Case.category==body.category,
                                         Case.external_ref==body.external_ref))
        if exists: raise HTTPException(409,f'Case reference already exists: {exists.id}')
    c=Case(category=body.category,kind=body.kind,external_ref=body.external_ref,data=data,created_by=user.id)
    db.add(c); db.flush(); record(db,user.id,'case_created',c.id,{'category':c.category}); db.commit(); db.refresh(c)
    return serialize_case(c)

@app.get('/api/cases')
def list_cases(q:str='',category:str='',status:str='',limit:int=Query(25,ge=1,le=100),offset:int=Query(0,ge=0),
               user:User=Depends(current_user),db:Session=Depends(get_db)):
    stmt=select(Case)
    if user.role!='admin': stmt=stmt.where(Case.created_by==user.id)
    if category:stmt=stmt.where(Case.category==category)
    if status:stmt=stmt.where(Case.status==status)
    if q: stmt=stmt.where(Case.external_ref.ilike(f'%{q[:80]}%')|Case.id.ilike(f'%{q[:80]}%'))
    total=db.scalar(select(func.count()).select_from(stmt.subquery()))
    cases=db.scalars(stmt.order_by(desc(Case.created_at)).limit(limit).offset(offset)).all()
    return {'total':total,'items':[serialize_case(c) for c in cases],'limit':limit,'offset':offset}

@app.get('/api/cases/{case_id}')
def get_case(case_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    return serialize_case(visible_case(db,case_id,user),True)

@app.patch('/api/cases/{case_id}')
def update_case(case_id:str,body:CaseCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=visible_case(db,case_id,user)
    if c.category!=body.category: raise HTTPException(422,'Cannot change category of an existing case')
    try: data=validate_case_data(c.category,body.data)
    except ValueError as e: raise HTTPException(422,str(e))
    c.data=data; c.status='draft'
    # Record human review provenance without overwriting the original extracted text.
    for evidence in c.documents:
        reviewed=dict(evidence.extracted)
        for key,entry in reviewed.items():
            if key in data:
                updated=dict(entry)
                updated['validated']=True
                updated['human_corrected']=str(data[key]).strip().lower()!=str(entry['value']).strip().lower()
                reviewed[key]=updated
        evidence.extracted=reviewed
    record(db,user.id,'case_corrected',c.id,{'keys':sorted(data)})
    db.commit();return serialize_case(c,True)

@app.post('/api/cases/{case_id}/documents',status_code=201)
async def upload_document(case_id:str,file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=visible_case(db,case_id,user)
    name=Path(file.filename or '').name
    if not name or len(name)>200: raise HTTPException(422,'Invalid file name')
    raw=await file.read(MAX_UPLOAD_MB*1024*1024+1)
    if len(raw)>MAX_UPLOAD_MB*1024*1024: raise HTTPException(413,f'Max file size is {MAX_UPLOAD_MB} MB')
    if not raw: raise HTTPException(422,'Empty file')
    doc_id=str(uuid4()); storage_name=f'{doc_id}.bin'
    try: processed=process_document(raw,name,doc_id)
    except (ValueError,RuntimeError,OverflowError) as e: raise HTTPException(422,str(e))
    if processed['mime'] in ('image/jpeg','image/png'):
        model_path=DATA_DIR/'model_artifacts'/f'image_{c.category}.pt'
        # Optional real PyTorch classifier: only activated when trained checkpoint exists.
        # Predicted evidence type is not a manipulation or fraud determination.
        processed['image_assessment']['evidence_type_classifier']=classify_image(raw,model_path)
    path=DATA_DIR/'uploads'/storage_name
    path.write_bytes(raw); os.chmod(path,0o600)
    try:
        d=Document(id=doc_id,case_id=c.id,original_name=name,storage_name=storage_name,
                   bytes=len(raw),mime=processed['mime'],sha256=processed['sha256'],
                   dhash=processed['dhash'],extracted=processed['extracted'],warnings=processed['warnings'],
                   image_assessment=processed['image_assessment'])
        db.add(d);c.status='draft';record(db,user.id,'document_uploaded',d.id,{'case_id':c.id,'mime':d.mime})
        db.commit()
    except Exception:
        path.unlink(missing_ok=True); db.rollback(); raise
    return {'document_id':doc_id,'case_id':case_id,'extracted':processed['extracted'],
            'warnings':processed['warnings'],'image_assessment':processed['image_assessment'],
            'pages_processed':processed['pages_processed'],
            'message':'Review and correct extracted fields in case form before analysis.'}

@app.get('/api/documents/{document_id}/download')
def download(document_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    d=db.get(Document,document_id)
    if not d: raise HTTPException(404,'Document not found')
    visible_case(db,d.case_id,user)
    record(db,user.id,'document_download',d.id);db.commit()
    return FileResponse(DATA_DIR/'uploads'/d.storage_name,media_type=d.mime,filename=d.original_name,
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

@app.delete('/api/documents/{document_id}')
def delete_document(document_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    d=db.get(Document,document_id)
    if not d:raise HTTPException(404,'Document not found')
    visible_case(db,d.case_id,user)
    path=DATA_DIR/'uploads'/d.storage_name
    record(db,user.id,'document_deleted',d.id);db.delete(d);db.commit();path.unlink(missing_ok=True)
    return {'deleted':document_id}

@app.post('/api/cases/{case_id}/analyze')
def analyze_case(case_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=visible_case(db,case_id,user)
    start=time.perf_counter()
    result=analyze(c,db)
    elapsed=round((time.perf_counter()-start)*1000,2)
    a=Analysis(case_id=c.id,result=result,model_id=result['model'].get('model_id'),elapsed_ms=elapsed)
    db.add(a);c.status='review' if result['human_review_required'] else 'processed'
    record(db,user.id,'case_analyzed',c.id,{'model_status':result['model']['status'],'review':result['human_review_required']})
    db.commit();return {'analysis_id':a.id,'elapsed_ms':elapsed,'result':result}

@app.post('/api/cases/{case_id}/outcome')
def set_outcome(case_id:str,outcome:str=Form(...),user:User=Depends(admin),db:Session=Depends(get_db)):
    if outcome not in {'unknown','suspected','confirmed_fraud','legitimate','unresolved'}:raise HTTPException(422,'Invalid outcome')
    c=visible_case(db,case_id,user);c.outcome=outcome
    record(db,user.id,'case_outcome_changed',c.id,{'outcome':outcome});db.commit()
    return {'case_id':c.id,'outcome':c.outcome,'note':'Human-entered outcome; not an AI conclusion'}

@app.get('/api/cases/{case_id}/related')
def related(case_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    c=visible_case(db,case_id,user)
    hashes={d.sha256 for d in c.documents}
    if not hashes:return {'items':[]}
    stmt=select(Document).join(Case,Case.id==Document.case_id).where(Document.sha256.in_(hashes),Document.case_id!=case_id)
    if user.role!='admin': stmt=stmt.where(Case.created_by==user.id)
    items=db.scalars(stmt.limit(100)).all()
    return {'items':[{'case_id':d.case_id,'document_id':d.id,'matching_hash':d.sha256} for d in items]}

@app.get('/api/dashboard')
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    stmt=select(Case)
    if user.role!='admin': stmt=stmt.where(Case.created_by==user.id)
    cases=db.scalars(stmt).all();case_ids={c.id for c in cases}
    analyses=db.scalars(select(Analysis).where(Analysis.case_id.in_(case_ids))).all() if case_ids else []
    by_category={}
    for c in cases:by_category[c.category]=by_category.get(c.category,0)+1
    latest={}
    for a in analyses:latest[a.case_id]=a
    bands={}
    for a in latest.values():
        band=a.result['decision_band'];bands[band]=bands.get(band,0)+1
    return {'total_cases':len(cases),'requiring_review':sum(c.status=='review' for c in cases),
            'confirmed_fraud_outcomes':sum(c.outcome=='confirmed_fraud' for c in cases),
            'suspected_outcomes':sum(c.outcome=='suspected' for c in cases),
            'fraud_indicator_cases':sum(bool(a.result.get('rules')) for a in latest.values()),
            'average_analysis_ms':round(sum(a.elapsed_ms for a in analyses)/len(analyses),2) if analyses else None,
            'categories':by_category,'bands':bands,
            'recent_activity':[{'case_id':c.id,'category':c.category,'status':c.status,'created_at':c.created_at.isoformat()} for c in sorted(cases,key=lambda x:x.created_at,reverse=True)[:8]],
            'note':'Suspected, rule-flagged and confirmed outcomes are distinct counts.'}

@app.post('/api/admin/datasets',status_code=201)
async def import_dataset(file:UploadFile=File(...),category:str=Form(...),source:str=Form(...),
                         label_definition:str=Form(...),permitted_use:str=Form(...),
                         synthetic:bool=Form(False),user:User=Depends(admin),db:Session=Depends(get_db)):
    if category not in registry(): raise HTTPException(422,'Unknown category')
    if not file.filename or not file.filename.lower().endswith('.csv'): raise HTTPException(422,'CSV required')
    if not all([source.strip(),label_definition.strip(),permitted_use.strip()]): raise HTTPException(422,'Provide dataset provenance, labels and permitted use')
    raw=await file.read(15_000_001)
    if len(raw)>15_000_000:raise HTTPException(413,'CSV larger than 15 MB')
    dataset_id=str(uuid4()); name=f'{dataset_id}.csv'; path=DATA_DIR/'datasets'/name
    try:
        raw.decode('utf-8-sig'); path.write_bytes(raw)
        quality=inspect_csv(path)
        if quality['issues']:raise ValueError('; '.join(quality['issues']))
    except (UnicodeError,ValueError) as e:
        path.unlink(missing_ok=True);raise HTTPException(422,str(e))
    item=Dataset(id=dataset_id,category=category,source=source,label_definition=label_definition,
                 permitted_use=permitted_use,is_synthetic=synthetic,file_name=name,quality=quality)
    db.add(item);record(db,user.id,'dataset_imported',item.id,{'category':category,'synthetic':synthetic})
    db.commit();return {'id':item.id,'quality':quality,'synthetic':synthetic}

class DemoModelRequest(BaseModel):
    categories: list[str]

@app.post('/api/admin/demo-models')
def deploy_demo_models(body:DemoModelRequest,user:User=Depends(admin),db:Session=Depends(get_db)):
    # Explicit admin action; no silent training or changes to existing deployed models.
    try: result=provision_synthetic(db,body.categories,user.id)
    except ValueError as exc: raise HTTPException(422,str(exc))
    record(db,user.id,'synthetic_demo_models_provisioned','categories',{'results':[
        {'category':r['category'],'status':r['status']} for r in result]})
    db.commit()
    return {'results':result,'warning':'Fictional training labels only. No clinical, underwriting or fraud-validation claims.'}

@app.get('/api/admin/datasets')
def datasets(user:User=Depends(admin),db:Session=Depends(get_db)):
    return [{'id':d.id,'category':d.category,'source':d.source,'is_synthetic':d.is_synthetic,
             'quality':d.quality,'created_at':d.created_at.isoformat()} for d in db.scalars(select(Dataset).order_by(desc(Dataset.created_at)))]

@app.post('/api/admin/train/{dataset_id}')
def train(dataset_id:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    dataset=db.get(Dataset,dataset_id)
    if not dataset:raise HTTPException(404,'Dataset not found')
    model_id=str(uuid4()); artifact_name=f'{model_id}.joblib'
    try:
        metrics=train_tabular(DATA_DIR/'datasets'/dataset.file_name,DATA_DIR/'model_artifacts'/artifact_name)
    except (ValueError,KeyError,ImportError) as e: raise HTTPException(422,f'Training rejected: {e}')
    metrics['data_is_synthetic']=dataset.is_synthetic
    row=ModelVersion(id=model_id,category=dataset.category,artifact_name=artifact_name,dataset_id=dataset.id,
                     metrics=metrics,feature_contract={'fields':FEATURES,'label':'fraud_label'},
                     is_synthetic=dataset.is_synthetic,approval_status='candidate')
    db.add(row);record(db,user.id,'model_trained',row.id,{'category':row.category,'synthetic':row.is_synthetic})
    db.commit();return {'model_id':row.id,'approval_status':'candidate','metrics':metrics}

@app.get('/api/models')
def models(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [{'id':m.id,'category':m.category,'task':m.task,'deployed':m.deployed,'approval_status':m.approval_status,
             'is_synthetic':m.is_synthetic,'metrics':m.metrics,'created_at':m.created_at.isoformat()}
            for m in db.scalars(select(ModelVersion).order_by(desc(ModelVersion.created_at)))]

@app.post('/api/admin/models/{model_id}/deploy')
def deploy(model_id:str,user:User=Depends(admin),db:Session=Depends(get_db)):
    m=db.get(ModelVersion,model_id)
    if not m: raise HTTPException(404,'Model not found')
    if not (DATA_DIR/'model_artifacts'/m.artifact_name).is_file():raise HTTPException(409,'Artifact missing')
    for old in db.scalars(select(ModelVersion).where(ModelVersion.category==m.category,ModelVersion.task==m.task,ModelVersion.deployed.is_(True))):
        old.deployed=False
    m.deployed=True;m.approval_status='demo_approved' if m.is_synthetic else 'approved_for_research'
    record(db,user.id,'model_deployed',m.id,{'synthetic':m.is_synthetic,'category':m.category});db.commit()
    return {'deployed':m.id,'category':m.category,'warning':'Synthetic models are demonstration-only.' if m.is_synthetic else 'External validation still required.'}

@app.get('/api/admin/settings')
def get_settings(user:User=Depends(admin),db:Session=Depends(get_db)):
    return {'scoring_policy':scoring_policy(db),'status':'provisional demonstration only'}

@app.post('/api/admin/settings')
def update_settings(model_weight:float=Form(...),low:int=Form(...),moderate:int=Form(...),
                    high:int=Form(...),user:User=Depends(admin),db:Session=Depends(get_db)):
    if not (0<=model_weight<=1 and 0<low<moderate<high<=100):
        raise HTTPException(422,'Expected 0<=weight<=1 and 0<low<moderate<high<=100')
    configuration={'model_weight':model_weight,'thresholds':{'low':low,'moderate':moderate,'high':high}}
    setting=db.get(Setting,'score_policy')
    if not setting:db.add(Setting(key='score_policy',value=configuration))
    else:setting.value=configuration
    record(db,user.id,'scoring_settings_changed','score_policy',configuration)
    db.commit()
    return {'scoring_policy':configuration,'warning':'Unvalidated demonstration thresholds only. Review human oversight.'}

@app.get('/api/admin/audit')
def audit(limit:int=Query(100,ge=1,le=500),user:User=Depends(admin),db:Session=Depends(get_db)):
    return [{'action':a.action,'object_id':a.object_id,'actor_id':a.actor_id,'at':a.at.isoformat(),
             'detail':a.detail} for a in db.scalars(select(AuditEvent).order_by(desc(AuditEvent.at)).limit(limit))]

@app.get('/api/health')
def health(): return {'status':'ok','system':'insurance-evidence-platform','model_policy':'unvalidated demo only'}

frontend=ROOT/'frontend'
app.mount('/assets',StaticFiles(directory=frontend),name='frontend_assets')
@app.get('/')
def home(): return FileResponse(frontend/'index.html',headers={'Cache-Control':'no-store'})
