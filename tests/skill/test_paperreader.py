import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[2] / 'skills/paperreader-translate/scripts'
sys.path.insert(0, str(SCRIPTS))
from tex_guard import TOKEN, chunks, protect, restore, validate
from paperreader import unpack


class TeXGuardTests(unittest.TestCase):
    def test_math_commands_roundtrip(self):
        source = r'''\documentclass{article}
\newcommand{\model}{Reader}
\title{A paper}
\author{Someone}
\begin{document}
\section{Introduction}
The value is $x_{i}=2$ and $$y=\frac{a}{b}$$.
\begin{align}a&=b\\c&=d\end{align}
See \cite[p.~2]{key} and \ref{fig:plot}.
\begin{figure}\includegraphics[width=.5\textwidth]{fig.png}\caption{A curve}\end{figure}
\begin{tabular}{lr}Method & Score \\ Ours & 3\end{tabular}
\verb|raw_%| and \$5. % a comment
\end{document}'''
        protected, mapping = protect(source)
        self.assertEqual(restore(protected, mapping), source)
        self.assertIn('A paper', protected)
        self.assertIn('A curve', protected)
        self.assertIn('Method', protected)
        self.assertNotIn('Someone', protected)
        self.assertIn(r'$$y=\frac{a}{b}$$', mapping.values())
        self.assertIn(r'\cite[p.~2]{key}', mapping.values())
        validate(protected, protected.replace('A paper', '一篇论文'), True)

    def test_chunks_preserve_bytes_and_tokens(self):
        source = ('Alpha $x$ and beta.\n\n' * 100)
        protected, mapping = protect(source)
        split = chunks(protected, 211)
        self.assertEqual(''.join(split), protected)
        self.assertEqual(sum(len(TOKEN.findall(x)) for x in split), len(mapping))
        self.assertEqual(restore(''.join(split), mapping), source)

    def test_corrupted_translation_rejected(self):
        source, mapping = protect('See $x$ and $y$.')
        tokens = list(mapping)
        for bad in [source.replace(tokens[0], ''), source + tokens[0], source.replace(tokens[0], 'BAD').replace(tokens[1], tokens[0]).replace('BAD', tokens[1]), source + r'\input{evil}', source + ' 20%']:
            with self.assertRaises(ValueError):
                validate(source, bad, True)

    def test_custom_prose_command(self):
        source = r'\mycaption{Some text} \label{keep}'
        opaque, _ = protect(source)
        exposed, mapping = protect(source, ('mycaption',))
        self.assertNotIn('Some text', opaque)
        self.assertIn('Some text', exposed)
        self.assertEqual(restore(exposed, mapping), source)

    def test_unclosed_math_rejected(self):
        with self.assertRaises(ValueError):
            protect('A broken $x')

    def test_commented_documentclass_and_title(self):
        source = '% \\begin{document}\n\\documentclass{article}\n% \\title{Fake}\n\\title{Real}\n\\begin{document}\nHello\\end{document}'
        protected, mapping = protect(source)
        self.assertEqual(restore(protected, mapping), source)
        self.assertIn('Real', protected)
        self.assertNotIn('Fake', protected)


class JobTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / 'source'
        self.project.mkdir()
        self.job = self.root / 'job'
        (self.project / 'main.tex').write_text('\\documentclass{article}\n\\title{Test}\n\\begin{document}\n\\maketitle\n\\input{body}\n\\end{document}', encoding='utf-8')
        (self.project / 'body.tex').write_text('Hello $x=1$.\n', encoding='utf-8')
        (self.project / 'main.pdf').write_bytes(b'original compiled PDF')
        (self.project / 'references.bib').write_text('@article{test,title={Hello}}', encoding='utf-8')

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'paperreader.py'), *map(str, args)], text=True, capture_output=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_multifile_checkpoint_and_export(self):
        self.cli('prepare', self.project, '--job', self.job)
        self.cli('assemble', '--job', self.job, '--output', self.root / 'incomplete', ok=False)
        self.assertFalse((self.root / 'incomplete').exists())
        manifest = json.loads((self.job / 'manifest.json').read_text())
        self.assertEqual(len(manifest['files']), 2)
        for chunk in manifest['chunks']:
            if chunk['automatic']:
                continue
            path = self.root / 'translation.txt'
            path.write_text(chunk['source'].replace('Hello', '你好').replace('Test', '测试'), encoding='utf-8')
            self.cli('accept', '--job', self.job, '--id', chunk['id'], '--translation', path)
        state = json.loads(self.cli('status', '--job', self.job).stdout)
        self.assertEqual(state['pending'], [])
        self.cli('assemble', '--job', self.job, '--output', self.root / 'result')
        self.assertFalse((self.root / 'result/project/main.pdf').exists())
        self.assertIn('你好 $x=1$', (self.root / 'result/project/body.tex').read_text())
        self.assertEqual((self.root / 'result/project/references.bib').read_bytes(), (self.project / 'references.bib').read_bytes())
        self.assertIn('Hello', (self.project / 'body.tex').read_text())
        self.cli('prepare', self.project, '--job', self.job, ok=False)
        self.cli('assemble', '--job', self.job, '--output', self.root / 'result', ok=False)

    def test_includegraphics_is_not_an_input_command(self):
        (self.project / 'body.tex').write_text(r'Hello \includegraphics[width=.5\textwidth]{plot.png}')
        self.cli('prepare', self.project, '--job', self.job)

    def test_stale_checkpoint_rejected(self):
        self.cli('prepare', self.project, '--job', self.job)
        manifest = json.loads((self.job / 'manifest.json').read_text())
        chunk = next(c for c in manifest['chunks'] if not c['automatic'])
        (self.job / 'translations').mkdir()
        (self.job / 'translations' / f"{chunk['id']}.json").write_text(json.dumps({'source': 'outdated', 'translation': '中文'}))
        self.cli('status', '--job', self.job, ok=False)

    def test_zip_and_traversal(self):
        archive = self.root / 'source.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            for p in self.project.iterdir():
                z.write(p, p.name)
        self.cli('prepare', archive, '--job', self.job)
        bad = self.root / 'bad.zip'
        with zipfile.ZipFile(bad, 'w') as z:
            z.writestr('../escape.tex', 'bad')
        with self.assertRaises(ValueError):
            unpack(bad, self.root / 'unpack')
        self.assertFalse((self.root / 'escape.tex').exists())

    @unittest.skipUnless(importlib.util.find_spec('pymupdf'), 'PyMuPDF not installed')
    def test_mineru_import_protects_math_and_keeps_assets(self):
        import pymupdf
        parsed = self.root / 'parsed'
        (parsed / 'images').mkdir(parents=True)
        source = self.root / 'paper.pdf'
        with pymupdf.open() as doc:
            doc.new_page()
            doc.save(source)
            doc[0].get_pixmap().save(parsed / 'images/figure.png')
        content = [
            {'type': 'text', 'text': 'A result with $x=2$.', 'page_idx': 0},
            {'type': 'equation', 'text': '$$y=3$$', 'page_idx': 0},
            {'type': 'image', 'img_path': 'images/figure.png', 'image_caption': ['A figure'], 'page_idx': 0},
            {'type': 'table', 'table_body': '<table><tr><td>Method</td><td>0.25</td></tr></table>', 'table_caption': ['Results'], 'page_idx': 0},
            {'type': 'list', 'list_items': ['First', 'Second'], 'page_idx': 0},
            {'type': 'code', 'code_body': 'x = 1', 'page_idx': 0},
        ]
        content_path = parsed / 'paper_content_list.json'
        content_path.write_text(json.dumps(content))
        self.cli('prepare', source, '--job', self.job, '--mineru-json', content_path)
        manifest = json.loads((self.job / 'manifest.json').read_text())
        self.assertEqual(manifest['parser'], 'mineru-local-import')
        for chunk in manifest['chunks']:
            if chunk['automatic']:
                continue
            translation = self.root / 'translation.txt'
            translation.write_text(chunk['source'].replace('A result with', '结果为').replace('A figure', '示意图').replace('Method', '方法').replace('Results', '结果').replace('First', '第一项').replace('Second', '第二项'), encoding='utf-8')
            self.cli('accept', '--job', self.job, '--id', chunk['id'], '--translation', translation)
        self.cli('assemble', '--job', self.job, '--output', self.root / 'result')
        text = (self.root / 'result/translated.md').read_text()
        self.assertIn('$x=2$', text)
        self.assertIn('$$y=3$$', text)
        self.assertIn('<td>方法</td><td>0.25</td>', text)
        self.assertIn('x = 1', text)
        self.assertNotIn('⟦PR', text)
        self.assertEqual((self.root / 'result/assets/images/figure.png').read_bytes(), (parsed / 'images/figure.png').read_bytes())

    @unittest.skipUnless(importlib.util.find_spec('pymupdf'), 'PyMuPDF not installed')
    def test_pdf_with_scanned_page(self):
        import pymupdf
        source = self.root / 'paper.pdf'
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((70, 70), 'A scientific paper. This page contains a short abstract with a clear result.')
            doc.new_page()
            doc.save(source)
        self.cli('prepare', source, '--job', self.job)
        manifest = json.loads((self.job / 'manifest.json').read_text())
        self.assertTrue(any('Page 2' in w for w in manifest['warnings']))
        self.assertEqual(len(manifest['files']), 2)
        for chunk in manifest['chunks']:
            translation = self.root / 'translation.txt'
            translation.write_text('科学论文摘要。' if chunk['file'] == 0 else '此页为空白。', encoding='utf-8')
            self.cli('accept', '--job', self.job, '--id', chunk['id'], '--translation', translation)
        self.cli('assemble', '--job', self.job, '--output', self.root / 'result')
        output = (self.root / 'result/bilingual.html').read_text()
        self.assertEqual(output.count('data:image/png;base64,'), 2)
        self.assertIn('科学论文摘要', output)
        self.assertEqual((self.root / 'result/original.pdf').read_bytes(), source.read_bytes())


if __name__ == '__main__':
    unittest.main()
