import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'skills/paperreader-translate/scripts'
sys.path.insert(0, str(SCRIPTS))
from build_diagnostics import diagnose, save_report, snapshot


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.main = self.root / 'main.tex'
        self.main.write_text('\\documentclass{article}\n\\begin{document}\nHello $x$.\n\\end{document}\n')

    def test_included_file_and_unlocated_errors(self):
        child = self.root / 'parts/body.tex'
        child.parent.mkdir()
        child.write_text('First\nBroken $x$.\nLast\n')
        report = diagnose(self.main, './parts/body.tex:2: Undefined control sequence.\n')
        self.assertEqual(report['contexts'][0]['file'], str(child.resolve()))
        self.assertFalse(report['contexts'][0]['location_assumed'])
        self.assertIn('2: Broken $x$.', report['contexts'][0]['source'])
        report = diagnose(self.main, '! Emergency stop.\n')
        self.assertTrue(report['contexts'])
        self.assertIsNone(report['errors'][0]['line'])
        report = diagnose(self.main, '! Undefined control sequence.\nl.3 source\n')
        self.assertEqual(report['errors'][0]['line'], 3)
        self.assertTrue(report['contexts'][0]['location_assumed'])

    def test_snapshots_do_not_change_or_overwrite_sources(self):
        original = self.main.read_bytes()
        first = snapshot(self.main)
        self.main.write_text('Second version')
        second = snapshot(self.main)
        self.assertNotEqual(first, second)
        self.assertEqual((first / 'source/main.tex').read_bytes(), original)
        self.assertEqual((second / 'source/main.tex').read_text(), 'Second version')
        self.assertFalse((second / 'source/.paperreader-builds').exists())
        self.assertEqual(self.main.read_text(), 'Second version')

    def test_failed_or_timed_out_build_never_advertises_old_pdf(self):
        self.main.with_suffix('.pdf').write_bytes(b'old PDF')
        for code, failure in [(1, None), (None, 'timed out'), (0, 'second pass timed out')]:
            with self.subTest(code=code, failure=failure):
                attempt = snapshot(self.main)
                report = save_report(self.main, attempt, 'compiler failure', code, failure)
                self.assertFalse(report['success'])
                self.assertIsNone(report['pdf'])
                self.assertEqual(json.loads((attempt / 'report.json').read_text())['failure'], failure)
        self.main.with_suffix('.log').write_text('Missing character: There is no 昇 in font')
        self.assertFalse(save_report(self.main, snapshot(self.main), '', 0)['success'])


@unittest.skipUnless(importlib.util.find_spec('pymupdf'), 'PyMuPDF not installed')
class GalleryTests(unittest.TestCase):
    def setUp(self):
        import pymupdf
        self.fitz = pymupdf
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def pdf(self, filename, offset=0, artwork=True):
        path = self.root / filename
        with self.fitz.open() as doc:
            for _ in range(offset):
                doc.new_page(width=400, height=500)
            p = doc.new_page(width=400, height=500)
            p.insert_text((30, 35), 'As shown in Figure 1. This is prose.')
            if artwork:
                p.draw_rect(self.fitz.Rect(40, 60, 190, 150), fill=(.3, .6, .8))
            p.insert_text((40, 172), 'Figure 1: <Example & caption>')
            p.insert_text((40, 245), 'Table 1: Measurements')
            if artwork:
                for y in [260, 280, 330]:
                    p.draw_line((40, y), (220, y))
            doc.save(path)
        return path

    def test_independent_pages_vector_and_table_crops(self):
        from figure_gallery import build_gallery
        source = self.pdf('source.pdf')
        target = self.pdf('target.pdf', offset=2)
        before = source.read_bytes()
        out = self.root / 'gallery'
        result = build_gallery(source, target, out)
        self.assertEqual(len(result['items']), 2)
        for item in result['items']:
            self.assertEqual(item['original']['page'], 1)
            self.assertEqual(item['translated']['page'], 3)
            self.assertEqual(item['original']['crop_method'], 'artwork-heuristic')
            self.assertLess(item['original']['preview_bbox'][3] - item['original']['preview_bbox'][1], 200)
            self.assertGreater(item['original']['preview_bbox'][3] - item['original']['preview_bbox'][1], 65)
            self.assertTrue((out / item['original']['preview']).is_file())
        self.assertIn('&lt;Example &amp; caption&gt;', (out / 'index.html').read_text())
        self.assertIn('translated.pdf#page=3', (out / 'index.html').read_text())
        self.assertEqual(source.read_bytes(), before)
        with self.assertRaises(ValueError):
            build_gallery(source, target, out)

    def test_multipanel_labels_and_nearer_following_figure(self):
        from figure_gallery import captions, crop_artwork
        with self.fitz.open() as doc:
            p = doc.new_page(width=400, height=500)
            for x in [40, 150]:
                for y in [60, 150]:
                    p.draw_rect(self.fitz.Rect(x, y, x + 80, y + 60))
            p.insert_text((40, 229), 'Axis label below the drawing')
            p.insert_text((40, 251), 'Figure 1: Four panels')
            p.draw_rect(self.fitz.Rect(40, 260, 230, 350))
            p.insert_text((40, 380), 'Figure 2: Next figure')
            items = captions(doc)
            box = crop_artwork(p, items[0], items)
            self.assertLess(box.y0, 60)
            self.assertGreater(box.x1, 230)
            self.assertGreater(box.y1, 229)
            self.assertLess(box.y1, 240)

    def test_neighboring_columns_are_not_grouped(self):
        from figure_gallery import captions, crop_artwork
        with self.fitz.open() as doc:
            p = doc.new_page(width=600, height=500)
            p.draw_rect(self.fitz.Rect(40, 60, 280, 150))
            p.draw_rect(self.fitz.Rect(310, 60, 550, 200))
            p.insert_text((40, 180), 'Figure 1: Left column')
            p.insert_text((310, 230), 'Figure 2: Right column')
            items = captions(doc)
            first = crop_artwork(p, items[0], items)
            second = crop_artwork(p, items[1], items)
            self.assertLess(first.x1, 300)
            self.assertGreater(second.x0, 300)
            self.assertLess(second.y0, 60)

    def test_unmatched_and_full_page_fallback(self):
        from figure_gallery import build_gallery
        source = self.pdf('source.pdf', artwork=False)
        target = self.root / 'empty.pdf'
        with self.fitz.open() as doc:
            doc.new_page()
            doc.save(target)
        result = build_gallery(source, target, self.root / 'gallery')
        self.assertTrue(all('translated' not in item for item in result['items']))
        self.assertTrue(all(item['original']['crop_method'] == 'full-page-fallback' for item in result['items']))

    def test_caption_priority_merged_labels_and_body_references(self):
        from figure_gallery import captions
        with self.fitz.open() as doc:
            p = doc.new_page()
            p.insert_text((30, 30), 'in Table 2. This is a reference.')
            p.insert_text((30, 60), 'bFigure 1: merged label')
            p.insert_text((30, 90), '(c)Figure 3: merged label')
            p = doc.new_page()
            p.insert_text((30, 30), 'Figure 1: actual caption')
            items = captions(doc)
        by_number = {i['number']: i for i in items}
        self.assertEqual(set(by_number), {'1', '3'})
        self.assertEqual(by_number['1']['page'], 2)
        self.assertEqual(by_number['3']['page'], 1)


if __name__ == '__main__':
    unittest.main()
