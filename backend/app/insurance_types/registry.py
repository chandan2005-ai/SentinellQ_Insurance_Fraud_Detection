"""Registry separates supported forms from validated predictive capabilities."""
COMMON = {
    'policy_number': 'text', 'policy_start': 'date', 'policy_end': 'date',
    'incident_date': 'date', 'reported_date': 'date', 'claim_amount': 'number',
    'coverage_amount': 'number', 'invoice_total': 'number', 'invoice_number': 'text',
    'prior_claims': 'integer', 'description': 'textarea',
}
SPECIFIC = {
    'motor': {'vehicle_registration': 'text', 'vehicle_type': 'text', 'repair_estimate': 'number'},
    'health': {'hospital_name': 'text', 'admission_date': 'date', 'discharge_date': 'date'},
    'life': {'beneficiary_reference': 'text', 'beneficiary_change_date': 'date'},
    'property': {'property_reference': 'text', 'loss_cause': 'text'},
    'travel': {'trip_start': 'date', 'trip_end': 'date', 'booking_reference': 'text'},
    'commercial': {'business_reference': 'text', 'loss_period_start': 'date'},
    'marine': {'shipment_reference': 'text', 'vessel_reference': 'text'},
    'crop': {'crop_type': 'text', 'season': 'text', 'plot_reference': 'text'},
    'personal_accident': {'injury_date': 'date'},
    'liability': {'incident_reference': 'text', 'liability_type': 'text'},
    'cyber': {'incident_type': 'text', 'incident_reference': 'text'},
    'pet': {'animal_reference': 'text', 'vet_invoice_number': 'text'},
    'gadget': {'device_reference': 'text', 'device_type': 'text'},
    'workers_comp': {'employment_reference': 'text', 'incident_location': 'text'},
}
REQUIRED = {key: ['policy_number', 'claim_amount', 'incident_date'] for key in SPECIFIC}
DISPLAY = {k: k.replace('_', ' ').title() for k in SPECIFIC}

def registry():
    return {k: {'name':DISPLAY[k], 'fields':COMMON | v, 'required':REQUIRED[k],
                'default_model_readiness':'unavailable_until_trained',
                'underwriting_model_readiness':'unavailable'} for k,v in SPECIFIC.items()}

def validate_category(category):
    if category not in SPECIFIC: raise ValueError('Unsupported insurance category')
    return category
