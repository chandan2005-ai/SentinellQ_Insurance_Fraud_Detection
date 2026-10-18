"""Opt-in and idempotent training of category-specific SYNTHETIC examples.

Never trains on uploaded claim documents or auto-deploys non-synthetic models.
"""
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select
from app.core.config import ROOT,DATA_DIR
from app.insurance_types.registry import SPECIFIC
from app.database.models import Dataset,ModelVersion
from app.training.tabular import train_tabular,inspect_csv,FEATURES

def provision_synthetic(db,categories,actor_id=None):
    if not categories or any(cat not in SPECIFIC for cat in categories):
        raise ValueError('Select one or more supported insurance categories')
    output=[]
    for category in dict.fromkeys(categories):
        existing=db.scalar(select(ModelVersion).where(ModelVersion.category==category,
            ModelVersion.task=='fraud_suspicion',ModelVersion.deployed.is_(True)))
        if existing:
            output.append({'category':category,'status':'already_active','model_id':existing.id,
                           'synthetic':existing.is_synthetic})
            continue
        source=ROOT/'sample_data'/f'{category}_SYNTHETIC.csv'
        if not source.is_file():
            raise ValueError(f'Missing bundled training data: {source.name}')
        info=inspect_csv(source)
        if info['issues']:
            raise ValueError('; '.join(info['issues']))
        ds_id,model_id=str(uuid4()),str(uuid4())
        ds_name=ds_id+'.csv';model_name=model_id+'.joblib'
        (DATA_DIR/'datasets'/ds_name).write_bytes(source.read_bytes())
        try:
            metrics=train_tabular(source,DATA_DIR/'model_artifacts'/model_name)
            metrics['data_is_synthetic']=True
            ds=Dataset(id=ds_id,category=category,file_name=ds_name,
                source='Bundled reproducible fictional simulator (seed 731)',
                label_definition='Synthetic binary outcome, NOT verified fraud',
                permitted_use='Local research/IBM Datathon demo only',is_synthetic=True,quality=info)
            db.add(ds)
            db.add(ModelVersion(id=model_id,category=category,artifact_name=model_name,dataset_id=ds_id,
                feature_contract={'fields':FEATURES,'label':'SIMULATED fraud_label'},metrics=metrics,
                approval_status='demo_approved',is_synthetic=True,deployed=True))
            db.commit()
        except Exception:
            db.rollback()
            (DATA_DIR/'datasets'/ds_name).unlink(missing_ok=True)
            (DATA_DIR/'model_artifacts'/model_name).unlink(missing_ok=True)
            raise
        output.append({'category':category,'status':'trained_and_deployed',
                       'model_id':model_id,'synthetic':True,'metrics':metrics['held_out_test']})
    return output
