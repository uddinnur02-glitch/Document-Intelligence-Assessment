"""Generate synthetic PDF pages for realistic page-count load tests (not invoice accuracy)."""
import argparse
from pathlib import Path


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--pages',type=int,default=1000)
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    if not 1 <= args.pages <= 1200:
        ap.error('--pages must be between 1 and 1200')
    import fitz
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with fitz.open() as document:
        for i in range(args.pages):
            page=document.new_page(width=595,height=842)
            page.insert_text((65,70),f'SYNTHETIC LOAD TEST — PAGE {i+1} / {args.pages}', fontsize=13)
            page.insert_text((65,110),f'Invoice Number: LOAD-{i+1:05d}', fontsize=11)
            page.insert_text((65,140),'Supplier: Synthetic Testing Only', fontsize=11)
            page.insert_text((65,170),'Subtotal: 100.00', fontsize=11)
            page.insert_text((65,200),'Tax: 10.00', fontsize=11)
            page.insert_text((65,230),'Total: 110.00', fontsize=11)
        document.save(output,garbage=3,deflate=True)
    print(f'Wrote {args.pages} synthetic PDF pages to {output}; size={output.stat().st_size} bytes')

if __name__ == '__main__': main()
