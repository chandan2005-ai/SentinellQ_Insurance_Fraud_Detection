"""Transparent deterministic consistency rules + optional trained model.

No score is generated without an active model. Severity rules are advisory.
"""
import math
from datetime import date
from sqlalchemy import select
from app.document_processing.processor import hamming
from app.training.tabular import predict_case,features_from_case,FEATURES
from app.database.models import Document,ModelVersion,Case,Setting
from app.core.config import DATA_DIR
from app.insurance_types.registry import REQUIRED

DEFAULT_SCORE_POLICY={'model_weight':0.8,'thresholds':{'low':25,'moderate':50,'high':75}}

def scoring_policy(db):
    row=db.get(Setting,'score_policy')
    return row.value if row else DEFAULT_SCORE_POLICY

def _date(v):
    try: return date.fromisoformat(str(v))
    except (ValueError, TypeError): return None

def _num(v):
    try: return float(v)
    except (TypeError,ValueError): return None

def analyze(case, db):
    documents=case.documents
    # User-reviewed manual values are authoritative; unconfirmed regex results remain evidence to inspect.
    data=dict(case.data or {})
    rules=[]; flags=[]
    def flag(code,severity,message,evidence):
        rules.append({'code':code,'severity':severity,'message':message,'evidence':evidence,'kind':'verification_indicator'})
    start,end,incident=(_date(data.get(k)) for k in ('policy_start','policy_end','incident_date'))
    if start and end and start>end: flag('invalid_coverage_dates',70,'Policy start date follows policy end date',{'policy_start':str(start),'policy_end':str(end)})
    if incident and start and incident<start or incident and end and incident>end:
        flag('coverage_date_check',55,'Incident falls outside entered policy dates; verify endorsements and applicable terms',
             {'incident_date':str(incident),'policy_start':str(start) if start else None,'policy_end':str(end) if end else None})
    reported=_date(data.get('reported_date'))
    if reported and incident and reported<incident:
        flag('report_before_incident',45,'Report date precedes incident date',{'incident_date':str(incident),'reported_date':str(reported)})
    amount=_num(data.get('claim_amount')); invoice=_num(data.get('invoice_total'))
    if amount is not None and invoice is not None and max(amount,invoice)>0 and abs(amount-invoice)/max(amount,invoice)>.2:
        flag('invoice_amount_gap',45,'Entered claim and invoice totals differ by over 20% (demonstration threshold)',
             {'claim_amount':amount,'invoice_total':invoice})
    # Domain checks rely only on saved, user-reviewed case fields.
    if case.category=='health':
        admission,discharge=(_date(data.get(x)) for x in ('admission_date','discharge_date'))
        if admission and discharge and discharge<admission:
            flag('invalid_hospital_stay',75,'Discharge date precedes hospital admission date',{'admission_date':str(admission),'discharge_date':str(discharge)})
        if admission and incident and admission<incident:
            flag('admission_before_incident',25,'Hospital admission precedes reported incident; verify the recorded dates',{'admission_date':str(admission),'incident_date':str(incident)})
    elif case.category=='travel':
        trip_start,trip_end=(_date(data.get(x)) for x in ('trip_start','trip_end'))
        if trip_start and trip_end and trip_start>trip_end:
            flag('invalid_trip_dates',70,'Trip start falls after trip end',{'trip_start':str(trip_start),'trip_end':str(trip_end)})
        if incident and trip_start and incident<trip_start or incident and trip_end and incident>trip_end:
            flag('incident_outside_trip',40,'Reported incident falls outside entered trip dates; verify coverage and itinerary',{'incident_date':str(incident),'trip_start':str(trip_start) if trip_start else None,'trip_end':str(trip_end) if trip_end else None})
    elif case.category=='motor':
        estimate=_num(data.get('repair_estimate'))
        if estimate is not None and amount is not None and max(amount,estimate)>0 and abs(amount-estimate)/max(amount,estimate)>.2:
            flag('repair_estimate_gap',35,'Claim amount differs from repair estimate by over 20%',{'claim_amount':amount,'repair_estimate':estimate})
    for doc in documents:
        declared=doc.extracted.get('insurance_category')
        if declared and str(declared['value']).strip().lower().replace(' insurance','').replace(' ','_')!=case.category:
            flag('document_category_mismatch',55,'Insurance category on document differs from case category',{'category':case.category,'document_category':declared['value'],'document_id':doc.id})
        for key,entry in doc.extracted.items():
            value=entry['value']; manual=data.get(key)
            if manual is None or manual=='': continue
            if key in ('claim_amount','invoice_total','coverage_amount','repair_estimate','prior_claims'):
                if _num(value) is not None and _num(manual) is not None and abs(_num(value)-_num(manual))>1:
                    flag('source_field_conflict',45,f'Entered {key} differs from extracted document',{'field':key,'manual':manual,'extracted':value,'document_id':doc.id,'page':entry['page']})
            elif str(manual).strip().lower()!=str(value).strip().lower():
                flag('source_field_conflict',45,f'Entered {key} differs from extracted document',{'field':key,'manual':manual,'extracted':value,'document_id':doc.id,'page':entry['page']})
    for ix,d1 in enumerate(documents):
        for d2 in documents[ix+1:]:
            if d1.sha256==d2.sha256:
                flag('same_document_in_case',20,'Identical evidence uploaded twice to this case',{'document_ids':[d1.id,d2.id]})
            elif d1.dhash and d2.dhash and hamming(d1.dhash,d2.dhash)<=5:
                flag('near_duplicate_in_case',25,'Near-identical images in this case (perceptual-hash similarity)',{'document_ids':[d1.id,d2.id]})
    for doc in documents:
        others=db.scalars(select(Document).join(Case,Case.id==Document.case_id).where(Document.id!=doc.id,Document.case_id!=case.id,
                             Case.created_by==case.created_by,Document.sha256==doc.sha256).limit(5)).all()
        for other in others:
            flag('duplicate_evidence_across_cases',65,'Same file hash in another case (not proof of fraud)',
                 {'document_id':doc.id,'other_document_id':other.id,'other_case_id':other.case_id,'sha256':doc.sha256})
        if doc.dhash:
            candidates=db.scalars(select(Document).join(Case,Case.id==Document.case_id).where(Document.id!=doc.id,Document.case_id!=case.id,
                                 Case.created_by==case.created_by,Document.dhash.is_not(None)).limit(500)).all()
            for other in candidates:
                if other.sha256!=doc.sha256 and hamming(doc.dhash,other.dhash)<=5:
                    flag('near_duplicate_cross_case',50,'Visually similar evidence in another case; human verification required',
                         {'document_id':doc.id,'other_document_id':other.id,'other_case_id':other.case_id,'hash_distance':hamming(doc.dhash,other.dhash)})
                    break
    for i,d1 in enumerate(documents):
        for d2 in documents[i+1:]:
            for key in set(d1.extracted)&set(d2.extracted):
                a,b=d1.extracted[key]['value'],d2.extracted[key]['value']
                if str(a).strip().lower()!=str(b).strip().lower():
                    flag('cross_document_conflict',50,f'Documents disagree on {key}',{'field':key,'values':[a,b],'document_ids':[d1.id,d2.id]})
    required=REQUIRED[case.category]; present=[x for x in required if data.get(x) is not None and data.get(x)!='']
    completeness=round(100*len(present)/len(required),2)
    missing=[x for x in required if x not in present]
    # Required form coverage and model features measure different things.
    model_inputs=features_from_case(data)
    ready_inputs=[key for key in FEATURES if math.isfinite(model_inputs[key])]
    model_missing=[key for key in FEATURES if key not in ready_inputs]
    model_coverage=round(100*len(ready_inputs)/len(FEATURES),2)
    active=db.scalar(select(ModelVersion).where(ModelVersion.category==case.category,
             ModelVersion.task=='fraud_suspicion',ModelVersion.deployed.is_(True)).limit(1))
    model_output={'status':'unavailable','reason':'No deployed category-specific fraud model'}
    if active:
        try:
            model_output=predict_case(data,DATA_DIR/'model_artifacts'/active.artifact_name)
            model_output['training_data_kind']='synthetic_demo' if active.is_synthetic else 'authorized_dataset'
            model_output['model_id']=active.id
        except (OSError,KeyError,ValueError) as exc:
            model_output={'status':'unavailable','reason':f'Model inference unavailable ({type(exc).__name__})'}
    score=None; band='unavailable'; policy=scoring_policy(db)
    if model_output['status']=='demo_inference':
        maxseverity=max((r['severity'] for r in rules),default=0)
        # Unvalidated illustration ONLY. Ignore duplicate same-event rule counts.
        score=round(min(100,max(0,policy['model_weight']*model_output['uncalibrated_model_score']+(1-policy['model_weight'])*maxseverity)),2)
        if score<policy['thresholds']['low']: band='low'
        elif score<policy['thresholds']['moderate']:band='moderate'
        elif score<policy['thresholds']['high']:band='high'
        else: band='critical'
    review=bool(rules or missing or score is None or score>=50 or model_output.get('anomaly_indicator'))
    recommend='Human review / request verification; no automatic denial' if review else 'Continue standard review process (advisory)'
    return {'case_id':case.id,'category':case.category,'fraud_suspicion_score':score,
            'fraud_score_interpretation':'UNVALIDATED DEMONSTRATION INDEX; not a calibrated fraud probability' if score is not None else 'Unavailable: no supported model prediction',
            'underwriting_risk_score':None,'underwriting_status':'No category-specific underwriting model trained',
            'decision_band':band,'band_status':'provisional_demonstration_only',
            'data_completeness_pct':completeness,'missing_required':missing,'rules':rules,
            'model_input_completeness_pct':model_coverage,'model_inputs_present':ready_inputs,
            'missing_model_inputs':model_missing,'minimum_model_inputs':5,
            'document_authenticity':{'validated_manipulation_classifier':'unavailable','technical_indicators':len(rules),
                'note':'Hash similarity, OCR mismatch and document quality do not prove fraud.'},
            'model':model_output,'model_confidence':None,'extraction_quality':'Rule-based extraction; no calibrated extraction confidence',
            'recommendation':recommend,'human_review_required':review,
            'next_steps':(["Administrator: deploy a model trained specifically for the "+case.category+" category."] if not active else
                (["Review and save additional model fields: "+', '.join(model_missing)] if model_output.get('status')=='insufficient_data' else
                 (["Synthetic model abstained: entered values are outside its training range; human verification required."] if model_output.get('status')=='out_of_distribution' else []))),
            'scoring_method':f"If active model: clip({policy['model_weight']} * uncalibrated model index + {1-policy['model_weight']:.2f} * maximum rule severity, 0,100); configuration demonstration-only. No model => no numeric score.",
            'scoring_config_snapshot':policy,
            'disclaimer':'Decision support only. No automatic fraud accusation, claim denial or binding underwriting decision.'}
