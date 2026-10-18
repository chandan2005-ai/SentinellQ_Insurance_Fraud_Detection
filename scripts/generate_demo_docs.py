"""Create clearly synthetic PDF and PNG evidence for IBM Datathon demonstrations."""
from pathlib import Path
from datetime import date
from PIL import Image,ImageDraw
import fitz
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'sample_data'/'demo_evidence';out.mkdir(parents=True,exist_ok=True)
from generate_synthetic import CATEGORIES
for category,(low,high) in CATEGORIES.items():
    pdf=fitz.open();page=pdf.new_page(width=612,height=792)
    lines=['SYNTHETIC DEMONSTRATION DOCUMENT - NOT A REAL INSURANCE CLAIM',
       f'Insurance category: {category}',f'Policy number: DEMO-{category.upper()}-001',
       'Policy start: 2026-01-01','Policy end: 2026-12-31',
       'Incident date: 2026-07-08',f'Claim amount: {int(low*1.2)}',
       f'Invoice total: {int(low*1.2)}',f'Invoice number: DEMO-INV-{category.upper()}-001',
       'All persons, events, policy numbers, and outcomes are artificial.',
       'These documents do not establish fraud and may not reflect real policy terms.']
    if category=='motor':lines.insert(7,'Vehicle registration: KA03AB1234')
    for i,line in enumerate(lines):page.insert_text((45,70+i*27),line,fontsize=11)
    pdf.save(out/f'{category}_ordinary_SYNTHETIC.pdf');pdf.close()
# Explicit discrepancy; amount does not match user-entered value.
pdf=fitz.open();page=pdf.new_page()
for i,line in enumerate(['SYNTHETIC CONFLICT EXAMPLE', 'Policy number: DEMO-MOTOR-001',
 'Incident date: 2026-07-08','Claim amount: 86000','Invoice total: 17500',
 'Vehicle registration: KA03AB1234']):
    page.insert_text((55,60+i*30),line,fontsize=12)
pdf.save(out/'motor_conflicting_invoice_SYNTHETIC.pdf');pdf.close()
img=Image.new('RGB',(900,650),'#dbeafe');draw=ImageDraw.Draw(img)
draw.rectangle((60,80,840,570),fill='#d1d5db',outline='#475569',width=9)
draw.ellipse((200,300,400,500),fill='#64748b');draw.ellipse((550,300,750,500),fill='#64748b')
draw.text((85,120),'SYNTHETIC TRAINING / DEMO EVIDENCE - NO REAL DAMAGE',fill='black')
img.save(out/'motor_evidence_reuse_A_SYNTHETIC.png')
img.save(out/'motor_evidence_reuse_B_SYNTHETIC.png')
print('Generated 14 ordinary policy PDFs, one discrepancy PDF and two identical images:',out)
