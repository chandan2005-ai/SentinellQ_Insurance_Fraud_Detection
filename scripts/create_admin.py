"""Run from project root: python scripts/create_admin.py --email admin@example.com"""
import sys,argparse,getpass
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from sqlalchemy import select
from app.database.db import Base,engine,SessionLocal
from app.database.models import User
from app.security.auth import hash_password

def main():
    p=argparse.ArgumentParser();p.add_argument('--email',required=True);args=p.parse_args()
    email=args.email.strip().lower();pw=getpass.getpass('Create admin password (12+ characters): ')
    pw2=getpass.getpass('Confirm password: ')
    if pw!=pw2:raise SystemExit('Passwords do not match')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email==email)):raise SystemExit('Email already exists')
        db.add(User(email=email,password_hash=hash_password(pw),role='admin'))
        db.commit()
    print(f'Created admin: {email}')
if __name__=='__main__':main()
