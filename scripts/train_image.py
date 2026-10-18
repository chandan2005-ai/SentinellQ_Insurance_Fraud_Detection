"""Train genuine PyTorch evidence-image category classifier on labeled images.

Examples: python scripts/train_image.py --images /path/to/labeled --category motor --epochs 4
Only run with consented, sufficiently representative labeled data. No inference
is shown before a checkpoint exists. ImageNet transfer weights require download.
"""
import argparse,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.image_classifier.model import train_labeled_images
from app.core.config import DATA_DIR
p=argparse.ArgumentParser();p.add_argument('--images',required=True);p.add_argument('--category',required=True)
p.add_argument('--epochs',type=int,default=3);p.add_argument('--pretrained',action='store_true')
a=p.parse_args()
from app.insurance_types.registry import validate_category
validate_category(a.category)
metrics=train_labeled_images(a.images,DATA_DIR/'model_artifacts'/f'image_{a.category}.pt',epochs=a.epochs,use_pretrained=a.pretrained)
print('Checkpoint produced - research model only, not fraud validation.');print(metrics)
