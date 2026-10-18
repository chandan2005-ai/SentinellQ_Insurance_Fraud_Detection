"""Optional low-privilege user creation; requires shell access."""
import sys,argparse,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select
from app.database.db import Base,engine,SessionLocal
from app.database.models import User
from app.security.auth import hash_password
p=argparse.ArgumentParser();p.add_argument('--email',required=True);args=p.parse_args()
pw=getpass.getpass('Password (12+ chars): ')
Base.metadata.create_all(engine)
with SessionLocal() as db:
    if db.scalar(select(User).where(User.email==args.email.lower())):raise SystemExit('Email already exists')
    db.add(User(email=args.email.lower(),password_hash=hash_password(pw),role='analyst'));db.commit()
print('Analyst created')
