"""Generate explicitly synthetic examples, never mislabel as actual claim history.

Each insurance type has diverse numerical/tabular feature coverage.
Models are trained only by an explicit administrator action or CLI command.
"""
from pathlib import Path
import csv, numpy as np, json
from datetime import date,timedelta
ROOT=Path(__file__).resolve().parents[1]
CATEGORIES={
 'motor':(15000,150000),'health':(12000,120000),'life':(50000,1000000),
 'property':(30000,700000),'travel':(2000,40000),'commercial':(25000,500000),
 'marine':(50000,1500000),'crop':(4000,90000),'personal_accident':(8000,120000),
 'liability':(45000,700000),'cyber':(35000,450000),'pet':(1000,25000),
 'gadget':(1500,65000),'workers_comp':(10000,250000)}
COLS=['entity_group','claim_amount','coverage_amount','invoice_total','prior_claims',
      'days_to_report','claim_coverage_ratio','claim_invoice_gap','fraud_label']

def generate(out_dir,n_motor=600,n_other=350,seed=731):
    rng=np.random.default_rng(seed);out_dir=Path(out_dir);out_dir.mkdir(parents=True,exist_ok=True)
    for category,(minimum,maximum) in CATEGORIES.items():
        rows=[]; n=n_motor if category=='motor' else n_other
        for i in range(n):
            value=round(float(rng.uniform(minimum,maximum)),2)
            # Travel policies can have far higher cover limits than a single delayed-baggage claim.
            max_cover_ratio = 22.0 if category=='travel' else 3.5
            coverage=round(value*float(rng.uniform(1.1,max_cover_ratio)),2)
            patterns=int(rng.binomial(1,.25))
            prior=int(min(rng.poisson(.6+patterns*2),10))
            days=int(rng.integers(0,8 if not patterns else 45))
            invoice=round(max(0,value*float(rng.uniform(.96,1.04) if not patterns else rng.uniform(.45,1.6))),2)
            # Artificial labels originate from a transparent simulation policy,
            # not any real investigation, medical status or protected attribute.
            logit=-3.5+1.0*patterns+.32*prior+.035*days+3*abs(value-invoice)/max(value,invoice,1)
            prob=float(1/(1+np.exp(-logit)))
            fraud=int(rng.random()<prob)
            rows.append({'entity_group':f'{category}_simulation_{i}', 'claim_amount':value,
                  'coverage_amount':coverage,'invoice_total':invoice,'prior_claims':prior,
                  'days_to_report':days,'claim_coverage_ratio':round(value/coverage,5),
                  'claim_invoice_gap':round(abs(value-invoice)/max(value,invoice,1),5),
                  'fraud_label':fraud})
        out=out_dir/f'{category}_SYNTHETIC.csv'
        with out.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=COLS);writer.writeheader();writer.writerows(rows)
    manifest={'disclaimer':'ALL datasets in this directory are SYNTHETIC simulations. Do not treat outcomes or metrics as real-world proof.',
      'seed':seed,'categories':list(CATEGORIES),'label_definition':'fraud_label is simulated binary indicator, NOT verified fraud',
      'data_limitations':['No real-world representation','No protected traits','No policy wording or coverage determination','Non-calibrated results']}
    (out_dir/'SYNTHETIC_DATA_NOTICE.json').write_text(json.dumps(manifest,indent=2))
    print('Created 14 synthetic category datasets at',out_dir)

if __name__=='__main__':generate(ROOT/'sample_data')
