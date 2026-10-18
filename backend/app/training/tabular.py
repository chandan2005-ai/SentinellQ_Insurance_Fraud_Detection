"""Genuine sklearn and XGBoost supervised training, with held-out evaluation.

A label of 1 MUST mean independently verified/confirmed fraud. Do not use
claim denial, investigation, expense or anomaly status as a fraud ground truth.
"""
from datetime import datetime, timezone
from pathlib import Path
import math
import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import (precision_score,recall_score,f1_score,roc_auc_score,
    average_precision_score,confusion_matrix,brier_score_loss)

FEATURES=['claim_amount','coverage_amount','invoice_total','prior_claims',
          'days_to_report','claim_coverage_ratio','claim_invoice_gap']
LABEL='fraud_label'

def features_from_case(values):
    claim=_float(values.get('claim_amount')); coverage=_float(values.get('coverage_amount'))
    invoice=_float(values.get('invoice_total'))
    try:
        reported=pd.to_datetime(values['reported_date']); incident=pd.to_datetime(values['incident_date'])
        days=float((reported-incident).days)
    except (ValueError,TypeError,KeyError): days=float('nan')
    return {'claim_amount':claim,'coverage_amount':coverage,'invoice_total':invoice,
            'prior_claims':_float(values.get('prior_claims')),'days_to_report':days,
            'claim_coverage_ratio':claim/coverage if np.isfinite(claim) and np.isfinite(coverage) and coverage>0 else float('nan'),
            'claim_invoice_gap':abs(claim-invoice)/max(claim,invoice,1) if np.isfinite(claim) and np.isfinite(invoice) else float('nan')}

def _float(value):
    try: return float(value) if value is not None and value!='' else float('nan')
    except (TypeError,ValueError,OverflowError): return float('nan')

def _metrics(y_true,p,threshold=.5):
    predicted=(p>=threshold).astype(int)
    cm=confusion_matrix(y_true,predicted,labels=[0,1])
    tn,fp,fn,tp=cm.ravel()
    return {'n':int(len(y_true)),'precision':float(precision_score(y_true,predicted,zero_division=0)),
           'recall':float(recall_score(y_true,predicted,zero_division=0)),
           'f1':float(f1_score(y_true,predicted,zero_division=0)),
           'roc_auc':float(roc_auc_score(y_true,p)) if len(set(y_true))>1 else None,
           'pr_auc':float(average_precision_score(y_true,p)) if len(set(y_true))>1 else None,
           'brier':float(brier_score_loss(y_true,p)),
           'false_positive_rate':float(fp/(fp+tn)) if fp+tn else None,
           'false_negative_rate':float(fn/(fn+tp)) if fn+tp else None,
           'confusion_matrix':cm.tolist()}

def inspect_csv(path):
    df=pd.read_csv(path)
    duplicates=int(df.duplicated().sum())
    result={'rows':int(len(df)),'columns':list(df.columns),'duplicate_rows':duplicates,
            'missing_pct':{key:round(float(v)*100,2) for key,v in df.isna().mean().items()},
            'label_counts':{},'issues':[]}
    if LABEL in df:
        result['label_counts']={str(k):int(v) for k,v in df[LABEL].value_counts(dropna=False).items()}
        if set(df[LABEL].dropna().unique())-{0,1}: result['issues'].append('Labels must be exactly 0 or 1')
    else: result['issues'].append(f'Missing required target column: {LABEL}')
    for f in FEATURES:
        if f not in df: result['issues'].append(f'Missing feature: {f}')
    return result

def _split(df, seed=42):
    if 'entity_group' in df.columns:
        group=df['entity_group'].astype(str)
        split=GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed)
        trainval_idx,test_idx=next(split.split(df,groups=group))
        sub=df.iloc[trainval_idx]
        other=GroupShuffleSplit(n_splits=1,test_size=.25,random_state=seed)
        t_idx,v_idx=next(other.split(sub,groups=sub['entity_group'].astype(str)))
        train_idx=trainval_idx[t_idx]; val_idx=trainval_idx[v_idx]
    else:
        trainval_idx,test_idx=train_test_split(np.arange(len(df)),test_size=.2,stratify=df[LABEL],random_state=seed)
        train_idx,val_idx=train_test_split(trainval_idx,test_size=.25,stratify=df.iloc[trainval_idx][LABEL],random_state=seed)
    return df.iloc[train_idx],df.iloc[val_idx],df.iloc[test_idx]

def train_tabular(path, artifact, *, seed=42):
    report=inspect_csv(path)
    if report['issues']: raise ValueError('; '.join(report['issues']))
    df=pd.read_csv(path).drop_duplicates().copy()
    df[LABEL]=pd.to_numeric(df[LABEL],errors='coerce')
    df=df[df[LABEL].isin([0,1])]
    if len(df)<80 or min(df[LABEL].value_counts().to_dict().values())<20:
        raise ValueError('Training requires >=80 records and >=20 independently labeled examples per class')
    for feature in FEATURES:
        df[feature]=pd.to_numeric(df[feature],errors='coerce')
    train,val,test=_split(df,seed)
    if any(len(set(part[LABEL]))<2 for part in (train,val,test)):
        raise ValueError('Each train/validation/test split must contain both labels; increase group diversity')
    xtrain,ytrain=train[FEATURES],train[LABEL].astype(int)
    xval,yval=val[FEATURES],val[LABEL].astype(int)
    xtest,ytest=test[FEATURES],test[LABEL].astype(int)
    logistic=Pipeline([('impute',SimpleImputer(strategy='median',add_indicator=False)),
                       ('scale',StandardScaler()),('classifier',LogisticRegression(max_iter=1500,class_weight='balanced',random_state=seed))])
    candidates={'scikit_learn_logistic':logistic}
    try:
        from xgboost import XGBClassifier
        candidates['xgboost']=Pipeline([('impute',SimpleImputer(strategy='median')),
            ('classifier',XGBClassifier(n_estimators=120,max_depth=3,learning_rate=.045,
                       subsample=.9,colsample_bytree=.9,objective='binary:logistic',eval_metric='logloss',random_state=seed,n_jobs=1))])
    except ImportError: pass
    validation={}
    for name, model in candidates.items():
        model.fit(xtrain,ytrain)
        validation[name]=_metrics(yval.to_numpy(),model.predict_proba(xval)[:,1])
    best=max(validation,key=lambda n: (validation[n]['pr_auc'] or -1,validation[n]['f1']))
    selected=candidates[best]
    # Never fit on validation/test to avoid contaminating the held-out performance report.
    held_out=_metrics(ytest.to_numpy(),selected.predict_proba(xtest)[:,1])
    imputer=SimpleImputer(strategy='median')
    anomaly=IsolationForest(n_estimators=100,contamination='auto',random_state=seed)
    anomaly.fit(imputer.fit_transform(xtrain))
    bounds={c:{'min':float(xtrain[c].min()) if xtrain[c].notna().any() else None,
               'max':float(xtrain[c].max()) if xtrain[c].notna().any() else None} for c in FEATURES}
    version=datetime.now(timezone.utc).isoformat()
    payload={'model':selected,'anomaly_model':anomaly,'anomaly_imputer':imputer,
             'feature_names':FEATURES,'bounds':bounds,'version':version,
             'algorithm':best,'calibrated':False,'threshold':.5,
             'global_explainability':'No per-case feature attribution provided; rules are separate.'}
    artifact=Path(artifact); artifact.parent.mkdir(parents=True,exist_ok=True)
    joblib.dump(payload,artifact)
    return {'algorithm':best,'version':version,'splits':{'train':len(train),'validation':len(val),'test':len(test)},
            'validation_comparison':validation,'held_out_test':held_out,
            'calibrated':False,'threshold':.5,'data_is_synthetic':None,
            'warning':'Observed performance applies only to this dataset and population; deployment requires external validation.'}

def predict_case(case_data, artifact):
    """Load only artifacts created and stored by this trusted application."""
    pack=joblib.load(artifact)
    features=features_from_case(case_data)
    row=pd.DataFrame([{name:features[name] for name in pack['feature_names']}])
    finite_count=sum(math.isfinite(value) for value in features.values())
    if finite_count<5:
        return {'status':'insufficient_data','model_version':pack['version'],
                'reason':f'Only {finite_count} of 7 supported model features available; at least 5 required for research inference',
                'features':{k:None if not math.isfinite(v) else round(v,4) for k,v in features.items()}}
    too_far=[]
    for name,bound in pack['bounds'].items():
        value=features[name]
        if math.isfinite(value) and bound['min'] is not None:
            low,high=bound['min'],bound['max']
            margin=max(abs(high-low)*.2,1)
            if value<low-margin or value>high+margin: too_far.append(name)
    if too_far:
        return {'status':'out_of_distribution','model_version':pack['version'],
                'out_of_range_features':too_far,'features':{k:None if not math.isfinite(v) else round(v,4) for k,v in features.items()}}
    prob=float(pack['model'].predict_proba(row)[0,1])
    is_anomaly=bool(pack['anomaly_model'].predict(pack['anomaly_imputer'].transform(row))[0]==-1)
    return {'status':'demo_inference','uncalibrated_model_score':round(prob*100,2),
            'model_version':pack['version'],'algorithm':pack['algorithm'],
            'anomaly_indicator':is_anomaly,'calibrated':False,
            'features':{k:None if not math.isfinite(v) else round(v,4) for k,v in features.items()},
            'feature_attributions':'Not available: global model importance is not a local explanation.'}
