"""Prepare simulated fraud models for one or all insurance categories.

From the project root: python scripts/prepare_demo_models.py health travel motor
Or: python scripts/prepare_demo_models.py --all
"""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.database.db import Base,engine,SessionLocal
from app.database import models
from app.insurance_types.registry import SPECIFIC
from app.training.demo import provision_synthetic

def main():
    p=argparse.ArgumentParser()
    p.add_argument('categories',nargs='*',choices=list(SPECIFIC))
    p.add_argument('--all',action='store_true',help='Include all 14 synthetic categories')
    args=p.parse_args()
    names=list(SPECIFIC) if args.all else args.categories or ['motor','health','travel']
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for result in provision_synthetic(db,names):
            print(result['category'],result['status'],result['model_id'])
    print('DEMO ONLY: generated models are trained on fictional labels. Re-analyze saved cases from the website.')
if __name__=='__main__':main()
