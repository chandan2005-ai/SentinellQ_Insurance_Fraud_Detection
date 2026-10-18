from datetime import date
from pydantic import BaseModel,Field,EmailStr,field_validator
from typing import Literal, Any
from app.insurance_types.registry import SPECIFIC, COMMON, REQUIRED

class Login(BaseModel):
    email: str
    password: str

class CaseCreate(BaseModel):
    category: str
    kind: Literal['claim','application']='claim'
    external_ref: str | None = Field(default=None,max_length=80)
    data: dict[str,Any] = Field(default_factory=dict)

    @field_validator('category')
    @classmethod
    def valid_category(cls,value):
        if value not in SPECIFIC: raise ValueError('Unknown insurance category')
        return value

    @field_validator('data')
    @classmethod
    def valid_fields(cls,data):
        if not isinstance(data,dict): raise ValueError('Expected a JSON object')
        if len(str(data))>30000: raise ValueError('Case data too large')
        for key,val in data.items():
            # See validate_case_data for category-restricted schema checks.
            if isinstance(val,(list,dict)):raise ValueError(f'{key} must be scalar')
        return data

def validate_case_data(category,data):
    fields=COMMON|SPECIFIC[category]
    unknown=set(data)-set(fields)
    if unknown: raise ValueError('Unsupported fields for selected category: '+', '.join(sorted(unknown)))
    cleaned={}
    for name,value in data.items():
        if value is None or value=='': continue
        if isinstance(value,str): value=value.strip()
        kind=fields[name]
        if kind=='date':
            try: value=date.fromisoformat(str(value)).isoformat()
            except ValueError as e: raise ValueError(f'{name} must use YYYY-MM-DD') from e
        elif kind in ('number','integer'):
            try: value=float(value)
            except (ValueError,TypeError) as e: raise ValueError(f'{name} must be numeric') from e
            if not (-1e-6<=value<=1e11): raise ValueError(f'{name} must be nonnegative and reasonable')
            if kind=='integer' and not value.is_integer(): raise ValueError(f'{name} must be a whole number')
            if kind=='integer': value=int(value)
        else:
            value=str(value)
            if len(value)>5000:raise ValueError(f'{name} is too long')
        cleaned[name]=value
    return cleaned
