"""Inspect actual figure files and render print-size colour/grayscale previews."""
import argparse,json,hashlib
import pymupdf as fitz
from PIL import Image
from paths import OUT,WORK

def audit(numbers):
    records=[]
    for n in numbers:
        stem=f'fig_{n:02d}'
        pdf=OUT/(stem+'.pdf')
        if not pdf.exists():
            records.append({'figure':n,'missing':True});continue
        doc=fitz.open(pdf);p=doc[0]
        spans=[s for b in p.get_text('dict')['blocks']if b['type']==0 for l in b['lines']for s in l['spans'] if s['text'].strip()]
        small=[{'text':s['text'],'size':s['size'],'bbox':s['bbox']}for s in spans if s['size']<7.98]
        overflow=[{'text':s['text'],'bbox':s['bbox']}for s in spans if not fitz.Rect(0,0,p.rect.width,p.rect.height).contains(fitz.Rect(s['bbox']))]
        png=OUT/(stem+'.png')
        with Image.open(png)as im:
            png_size=im.size;dpi=im.info.get('dpi')
        pix=p.get_pixmap(dpi=160,alpha=False)
        preview=WORK/(stem+'_pdf_color.png');pix.save(preview)
        with Image.open(preview)as im:im.convert('L').convert('RGB').save(WORK/(stem+'_pdf_gray.png'))
        fonts=[]
        for item in p.get_fonts(full=True):
            try:
                base,ext,kind,data=doc.extract_font(item[0]);embedded=bool(data)
            except Exception:embedded=False
            fonts.append({'name':item[3],'embedded':embedded})
        record={'figure':n,'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                'width_cm':p.rect.width/72*2.54,'height_cm':p.rect.height/72*2.54,
                'png_size':png_size,'png_dpi':dpi,'min_text_pt':min((s['size']for s in spans),default=0),
                'small_text':small,'text_outside_canvas':overflow,'fonts':fonts,
                'svg_editable_text':'<text' in (OUT/(stem+'.svg')).read_text(encoding='utf-8'),
                'previews':[str(preview),str(WORK/(stem+'_pdf_gray.png'))],
                'visual_review':'requires actual viewing; not inferred from generated files'}
        records.append(record)
        print(f'{stem}: {record["width_cm"]:.2f} x {record["height_cm"]:.2f} cm, min {record["min_text_pt"]:.2f} pt, small={len(small)}, overflow={len(overflow)}',flush=True)
    return records

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('numbers',nargs='*',type=int)
    args=parser.parse_args();numbers=args.numbers or list(range(1,28))
    report=audit(numbers)
    (WORK/('file_qa_'+('_'.join(map(str,numbers)) if len(numbers)<4 else f'{min(numbers):02d}_{max(numbers):02d}')+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
