"""Generate labeled, entirely synthetic OCR fixtures. No personal/business data."""
import argparse
import json
from pathlib import Path

INVOICES = [
 ("OCR-2026-001", "2026-11-20", "Demo Medical Supplies", "Sample Care Center", "125.00", "12.50", "137.50"),
 ("OCR-2026-002", "2026-11-21", "Example Trading Company", "Demo Clinic", "240.00", "24.00", "264.00"),
]

def lines(values):
    number, date, supplier, customer, subtotal, tax, total = values
    return ["SYNTHETIC TEST INVOICE", f"Invoice Number: {number}", f"Invoice Date: {date}",
            f"Supplier: {supplier}", f"Customer: {customer}", f"Subtotal: {subtotal}",
            f"Tax: {tax}", f"Total: {total}", "Currency: USD"]

def fields(values):
    number, date, supplier, customer, subtotal, tax, total = values
    return dict(invoice_number=number, invoice_date=date, supplier_name=supplier,
                customer_name=customer, subtotal=subtotal, tax=tax, total=total, currency='USD')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='evaluation/ocr_fixtures')
    args=parser.parse_args()
    directory=Path(args.output).resolve(); directory.mkdir(parents=True,exist_ok=True)
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    import fitz
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    try: font=ImageFont.truetype(font_path,38)
    except OSError: font=ImageFont.load_default()
    def render(values):
        im=Image.new('RGB',(1250,950),'white'); d=ImageDraw.Draw(im)
        for i,line in enumerate(lines(values)):
            d.text((70,60+i*83),line,fill='black',font=font)
        return im
    img1=render(INVOICES[0]); img2=render(INVOICES[1]); img1.save(directory/'clear_invoice.png')
    # Controlled synthetic degradation, not representative of real scanned invoices.
    img2.resize((825,627)).filter(ImageFilter.GaussianBlur(0.6)).save(directory/'degraded_invoice.jpg',quality=75)
    img1.save(directory/'invoice_image.tiff')
    doc=fitz.open()
    for image in (img1,img2):
        import io
        buf=io.BytesIO(); image.save(buf,format='PNG')
        page=doc.new_page(width=625,height=475)
        page.insert_image(page.rect,stream=buf.getvalue())
    doc.save(directory/'scanned_two_page.pdf'); doc.close()
    (directory/'broken_image.png').write_bytes(b'not a real PNG')
    cases=[
      {'id':'clear_png','path':'clear_invoice.png','expected_text':'\n'.join(lines(INVOICES[0])), 'expected_fields':fields(INVOICES[0]),'expected_pages':1,'expect_failure':False},
      {'id':'degraded_jpeg','path':'degraded_invoice.jpg','expected_text':'\n'.join(lines(INVOICES[1])), 'expected_fields':fields(INVOICES[1]),'expected_pages':1,'expect_failure':False},
      {'id':'tiff_image','path':'invoice_image.tiff','expected_text':'\n'.join(lines(INVOICES[0])), 'expected_fields':fields(INVOICES[0]),'expected_pages':1,'expect_failure':False},
      {'id':'scanned_pdf','path':'scanned_two_page.pdf','expected_text':'\n'.join(lines(INVOICES[0])+lines(INVOICES[1])), 'expected_fields':fields(INVOICES[0]),'expected_pages':2,'expect_failure':False},
      {'id':'corrupted_png','path':'broken_image.png','expect_failure':True}
    ]
    manifest=directory/'manifest.json'; manifest.write_text(json.dumps({'cases':cases},indent=2),encoding='utf-8')
    print(f'Created {len(cases)} synthetic OCR test cases: {manifest}')
if __name__=='__main__': main()
