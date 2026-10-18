"""Real PyTorch transfer-learning pipeline; untrained checkpoints never infer.

Training expects authorized labeled images organized by class directories and
records validation measures. Default: unavailable (there is no credible data).
"""
from pathlib import Path
from datetime import datetime,timezone
import json
import numpy as np

def _imports():
    import torch
    from torch import nn
    from torchvision import models,transforms
    return torch,nn,models,transforms

def transform():
    _,_,_,T=_imports()
    return T.Compose([T.Resize((224,224)),T.ToTensor(),T.Normalize([.485,.456,.406],[.229,.224,.225])])

def train_labeled_images(data_dir, output, *, epochs=3, seed=42, use_pretrained=False):
    """Data directory contains one folder per class, >=2 images per class."""
    torch,nn,models,T=_imports()
    from torchvision.datasets import ImageFolder
    from torch.utils.data import DataLoader,Subset
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report,confusion_matrix
    torch.manual_seed(seed)
    dataset=ImageFolder(str(data_dir),transform=transform())
    if len(dataset.classes)<2 or min(np.bincount(dataset.targets))<4:
        raise ValueError('At least two classes and >=4 labeled images per class required')
    train_indices, val_indices=train_test_split(np.arange(len(dataset)),test_size=.25,stratify=dataset.targets,random_state=seed)
    weights=models.ResNet18_Weights.DEFAULT if use_pretrained else None
    net=models.resnet18(weights=weights)
    for param in net.parameters(): param.requires_grad=False
    # Without pretrained weights a frozen random feature extractor is invalid.
    if not use_pretrained:
        for param in net.parameters(): param.requires_grad=True
    net.fc=nn.Linear(net.fc.in_features,len(dataset.classes))
    opt=torch.optim.Adam(filter(lambda p:p.requires_grad,net.parameters()),lr=0.0003)
    loss_fn=nn.CrossEntropyLoss()
    train_loader=DataLoader(Subset(dataset,train_indices.tolist()),batch_size=8,shuffle=True)
    val_loader=DataLoader(Subset(dataset,val_indices.tolist()),batch_size=8)
    for _ in range(epochs):
        net.train()
        for images,labels in train_loader:
            opt.zero_grad(); loss=loss_fn(net(images),labels); loss.backward(); opt.step()
    net.eval(); true=[]; pred=[]
    with torch.no_grad():
        for images, labels in val_loader:
            true.extend(labels.tolist()); pred.extend(net(images).argmax(dim=1).tolist())
    metrics={'n_train':int(len(train_indices)),'n_validation':int(len(val_indices)),
             'class_report':classification_report(true,pred,labels=list(range(len(dataset.classes))),target_names=dataset.classes,zero_division=0,output_dict=True),
             'confusion_matrix':confusion_matrix(true,pred,labels=list(range(len(dataset.classes)))).tolist(),
             'warning':'Holdout accuracy alone does not validate document manipulation or insurance fraud.'}
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    torch.save({'state_dict':net.state_dict(),'classes':dataset.classes,'metrics':metrics,
                'version':datetime.now(timezone.utc).isoformat()},output)
    return metrics

def classify_image(image_bytes,checkpoint_path, abstain_below=.6):
    checkpoint_path=Path(checkpoint_path)
    if not checkpoint_path.is_file(): return {'status':'unavailable','reason':'No evaluated image classifier checkpoint'}
    torch,nn,models,T=_imports()
    from PIL import Image
    import io
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=True)
    net=models.resnet18(weights=None)
    net.fc=nn.Linear(net.fc.in_features,len(checkpoint['classes']))
    net.load_state_dict(checkpoint['state_dict']); net.eval()
    with Image.open(io.BytesIO(image_bytes)) as source: tensor=transform()(source.convert('RGB')).unsqueeze(0)
    with torch.no_grad(): probs=torch.softmax(net(tensor),dim=1)[0].tolist()
    best=max(range(len(probs)),key=lambda i:probs[i])
    return {'status':'abstain' if probs[best]<abstain_below else 'available',
            'class':checkpoint['classes'][best] if probs[best]>=abstain_below else None,
            'class_scores':dict(zip(checkpoint['classes'],[round(x,4) for x in probs])),
            'model_version':checkpoint['version'],
            'limitations':'Not calibrated; domain-specific labeled validation and deployment review required.'}
