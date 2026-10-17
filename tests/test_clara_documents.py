import io
import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from docx import Document
from docx.oxml import OxmlElement
from docx.shared import RGBColor
from flask import Flask
import clara_documents as d


def sample():
    doc=Document();title=doc.add_heading('مراجعة وثيقة الموارد البشرية',0)
    for style in doc.styles:
        if style.type==1:
            style.font.color.rgb=RGBColor(0,0,0)
            for border in list(style.element.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr')):border.getparent().remove(border)
    for run in title.runs:run.font.color.rgb=RGBColor(0,0,0)
    for border in list(title._p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pBdr')):border.getparent().remove(border)
    p=doc.add_paragraph();p.add_run('Human ').bold=True;p.add_run('resources need clear policies.').italic=True
    p=doc.add_paragraph('يحدد القسم احتياجاته وفق طبيعة العمل.')
    bidi=OxmlElement('w:bidi');p._p.get_or_add_pPr().append(bidi)
    table=doc.add_table(rows=2,cols=2);table.style='Table Grid'
    table.cell(0,0).text='البند';table.cell(0,1).text='المسؤول'
    table.cell(1,0).text='المراجعة';table.cell(1,1).text='القسم'
    out=io.BytesIO();doc.save(out);return out.getvalue()

class ClaraDocumentTests(unittest.TestCase):
    def test_edit_across_runs_preserves_unedited_styles_tables_and_package_parts(self):
        blob=sample();parsed=d.parse_document('sample.docx',blob)
        target=next(p for p in parsed['paragraphs'] if p['text'].startswith('Human'))
        edited,changes=d.apply_edits('sample.docx',blob,parsed,[{'id':target['id'],'old':'Human resources','new':'HR'}])
        actual=Document(io.BytesIO(edited))
        self.assertEqual(actual.paragraphs[1].text,'HR need clear policies.')
        self.assertTrue(actual.paragraphs[1].runs[0].bold)
        self.assertTrue(actual.paragraphs[1].runs[1].italic)
        self.assertEqual(actual.tables[0].cell(1,1).text,'القسم')
        with zipfile.ZipFile(io.BytesIO(blob)) as a,zipfile.ZipFile(io.BytesIO(edited)) as b:
            for name in a.namelist():
                if name!='word/document.xml':self.assertEqual(a.read(name),b.read(name),name)
        self.assertIn('bidi',actual.paragraphs[2]._p.xml)
        if os.environ.get('CLARA_RENDER_SAMPLE')=='1':
            with open('/tmp/clara-edited.docx','wb') as output:output.write(edited)

    def test_edits_fail_without_exact_unique_source_and_never_change_original(self):
        blob=sample();parsed=d.parse_document('sample.docx',blob)
        before=bytes(blob)
        for edit in ({'id':'p999','old':'missing','new':'new'},{'id':'p1','old':'not found','new':'new'},{'id':'p1','old':'Human','new':'line\nbreak'}):
            with self.assertRaises(ValueError):d.apply_edits('sample.docx',blob,parsed,[edit])
        self.assertEqual(blob,before)

    def test_utf8_text_edit_and_invalid_or_scanned_files(self):
        blob='السلام عليكم\nالنص القديم'.encode()
        parsed=d.parse_document('arabic.txt',blob)
        out,_=d.apply_edits('arabic.txt',blob,parsed,[{'id':'p1','old':'القديم','new':'المعدّل'}])
        self.assertIn('النص المعدّل',out.decode())
        for name,raw in [('bad.docx',b'bad zip'),('script.exe',b'no'),('bad.txt',b'\xff')]:
            with self.assertRaises(ValueError):d.parse_document(name,raw)
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(width=200,height=200);output=io.BytesIO();writer.write(output)
        with self.assertRaisesRegex(ValueError,'OCR'):d.parse_document('scan.pdf',output.getvalue())

    def test_macro_and_expanded_zip_are_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:archive.writestr('word/vbaProject.bin',b'x')
        with self.assertRaises(ValueError):d.parse_document('macro.docx',out.getvalue())

    def test_upload_edit_download_and_private_recall(self):
        with tempfile.TemporaryDirectory() as directory:
            db=lambda:sqlite3.connect(directory+'/files.sqlite')
            app=Flask('file-tests');d.install_routes(app,db);client=app.test_client()
            upload=client.post('/companion/files',data={'file':(io.BytesIO(sample()),'test.docx')})
            self.assertEqual(upload.status_code,200);identity=upload.json['id']
            original=client.get(upload.json['download']).data
            parsed=d.parse_document('test.docx',original)
            target=next(p for p in parsed['paragraphs'] if p['text'].startswith('Human'))
            proposal={'summary':'عدّلت التعبير المطلوب في نسخة جديدة؛ راجعها قبل الاعتماد.','edits':[{'id':target['id'],'old':'Human resources','new':'HR'}]}
            with patch.object(d,'model_plan',return_value=proposal):
                response=client.post('/companion/files/'+identity+'/work',json={'action':'edit','instruction':'اختصر Human resources إلى HR'})
            self.assertEqual(response.status_code,200);self.assertTrue(response.json['original_preserved'])
            self.assertFalse(response.json['layout_verified'])
            edited=client.get(response.json['download']).data
            self.assertEqual(Document(io.BytesIO(edited)).paragraphs[1].text,'HR need clear policies.')
            self.assertEqual(client.get(upload.json['download']).data,original)
            self.assertTrue(d.recall(db,'clear policies'))
            self.assertEqual(client.get('/companion/files/not-an-id/download').status_code,404)
            with patch.object(d,'model_plan') as generate:
                bad=client.post('/companion/files/'+identity+'/work',json={'action':'send_email','instruction':'send it'})
                self.assertEqual(bad.status_code,400);generate.assert_not_called()
