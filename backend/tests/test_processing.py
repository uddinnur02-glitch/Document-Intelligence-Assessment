import io
import pytest
from pathlib import Path
from app.processing import extract_file


def test_csv_data(tmp_path):
    f = tmp_path / 'a.csv'
    f.write_text('invoice,total\nINV-1,100\n', encoding='utf8')
    result = extract_file(str(f), f.name)
    assert result['kind'] == 'csv'
    assert result['sheet_count'] == 1
    assert result['sheets'][0]['rows'] == 2
    assert result['sheets'][0]['preview'][1] == ['INV-1','100']


def test_xlsx_two_sheets(tmp_path):
    from openpyxl import Workbook
    f=tmp_path/'book.xlsx'
    book=Workbook()
    book.active.title='Invoices'
    book.active.append(['Invoice','Total'])
    book.active.append(['INV-2',42])
    book.create_sheet('Other')
    book.save(f)
    result=extract_file(str(f), f.name)
    assert result['sheet_count']==2
    assert result['sheets'][0]['preview'][1]==['INV-2','42']


def test_digital_pdf(tmp_path):
    import fitz
    f=tmp_path/'digital.pdf'
    doc=fitz.open()
    page=doc.new_page()
    page.insert_text((70, 70), 'Invoice INV-1234 supplier ACME amount 300 dollars')
    doc.save(f)
    doc.close()
    result=extract_file(str(f), f.name)
    assert 'INV-1234' in result['text']
    assert result['pages'][0]['method']=='digital'


def test_image_ocr(tmp_path):
    import shutil
    if not shutil.which('tesseract'):
        pytest.skip('tesseract executable not available outside Docker')
    from PIL import Image, ImageDraw, ImageFont
    f=tmp_path/'image.png'
    im=Image.new('RGB',(1000,200),'white')
    draw=ImageDraw.Draw(im)
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    font=ImageFont.truetype(font_path,45) if Path(font_path).exists() else ImageFont.load_default()
    draw.text((30,50),'INVOICE NUMBER 56789',fill='black',font=font)
    im.save(f)
    result=extract_file(str(f),f.name)
    assert result['pages'][0]['method']=='ocr'
    assert '56789' in result['text']


def test_corrupted_pdf(tmp_path):
    f=tmp_path/'bad.pdf';f.write_bytes(b'not a pdf')
    with pytest.raises((ValueError,RuntimeError)):
        extract_file(str(f),f.name)


def test_missing_file(tmp_path):
    with pytest.raises(ValueError, match='missing'):
        extract_file(str(tmp_path/'not.csv'),'not.csv')
