from app.database.models import AuditEvent

def record(db, actor, action, obj=None, detail=None):
    db.add(AuditEvent(actor_id=actor, action=action, object_id=obj, detail=detail or {}))
