"""Explicit, separate opt-in deployment of a SYNTHETIC motor fraud demo model."""
import sys
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.database.db import Base,engine,SessionLocal
from app.database.models import Dataset,ModelVersion
from app.training.tabular import train_tabular,inspect_csv,FEATURES
from app.core.config import DATA_DIR

def main():
    source=ROOT/'sample_data'/'motor_SYNTHETIC.csv'
    if not source.exists(): raise SystemExit('First run: python scripts/generate_synthetic.py')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        dataset_id=str(uuid4());dataset_name=dataset_id+'.csv'
        (DATA_DIR/'datasets'/dataset_name).write_bytes(source.read_bytes())
        quality=inspect_csv(source)
        dataset=Dataset(id=dataset_id,category='motor',file_name=dataset_name,source='Synthetic generator seed 731',
                        label_definition='Simulated fraud label only; not real cases',
                        permitted_use='IBM Datathon synthetic demonstration',is_synthetic=True,quality=quality)
        db.add(dataset)
        model_id=str(uuid4());artifact_name=model_id+'.joblib'
        metrics=train_tabular(source,DATA_DIR/'model_artifacts'/artifact_name)
        metrics['data_is_synthetic']=True
        for old in db.query(ModelVersion).filter_by(category='motor',task='fraud_suspicion',deployed=True):old.deployed=False
        db.add(ModelVersion(id=model_id,category='motor',artifact_name=artifact_name,dataset_id=dataset_id,
                            metrics=metrics,feature_contract={'fields':FEATURES,'label':'simulated fraud_label'},
                            approval_status='demo_approved',is_synthetic=True,deployed=True))
        db.commit()
    print('SYNTHETIC motor demonstration model active:',model_id)
    print('Held-out metrics reflect synthetic simulation ONLY:',metrics['held_out_test'])
if __name__=='__main__':main()
