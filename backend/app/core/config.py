"""Environment configuration, with all paths relative to the project root."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[3]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    pass
_data_location = Path(os.getenv('DATA_DIR') or 'runtime')
# The same database must be used from the project root, backend/, or IDEs.
DATA_DIR = (_data_location if _data_location.is_absolute() else ROOT / _data_location).resolve()
_raw_db = os.getenv('DATABASE_URL', 'sqlite:///./runtime/insurance.db')
if _raw_db.startswith('sqlite:///') and not _raw_db.startswith('sqlite:////'):
    _db_path = _raw_db[len('sqlite:///'):]
    # Windows absolute sqlite URLs (sqlite:///C:/...) must remain absolute.
    if not Path(_db_path).is_absolute() and not (_db_path[1:3] == ':/' if len(_db_path)>2 else False):
        _db_path = str((ROOT / _db_path).resolve())
    DB_URL = 'sqlite:///' + _db_path.replace('\\', '/')
else:
    DB_URL = _raw_db
JWT_SECRET = os.getenv('JWT_SECRET', '')
TOKEN_EXP_MINUTES = int(os.getenv('TOKEN_EXP_MINUTES', '90'))
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '10'))
MAX_PDF_PAGES = int(os.getenv('MAX_PDF_PAGES', '30'))
MAX_IMAGE_PIXELS = int(os.getenv('MAX_IMAGE_PIXELS', '30000000'))
CORS_ORIGIN = os.getenv('CORS_ORIGIN', '')
DATA_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'uploads').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'model_artifacts').mkdir(parents=True, exist_ok=True)
(DATA_DIR / 'datasets').mkdir(parents=True, exist_ok=True)


def check_secret():
    if len(JWT_SECRET) < 32 or 'REPLACE_WITH' in JWT_SECRET:
        raise RuntimeError('Set JWT_SECRET to a random 32+-character value in .env')
