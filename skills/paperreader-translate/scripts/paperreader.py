#!/usr/bin/env python3
"""Local preparation, checkpoint validation and export for Codex translation."""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from tex_guard import TOKEN, chunks, protect, restore, strip_comments, validate
from mineru_adapter import import_pages, protect_markdown


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def inside(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Path outside project: {name}")
    return target


def unpack(source: Path, target: Path) -> None:
    target.mkdir()
    if zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            for member in archive.infolist():
                path = inside(target, member.filename)
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("Archive links are unsupported")
                if member.is_dir():
                    path.mkdir(parents=True, exist_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as src, path.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(source) as archive:
            for member in archive:
                path = inside(target, member.name)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as src, path.open("xb") as dst:
                        shutil.copyfileobj(src, dst)
                else:
                    raise ValueError("Archive links and special files are unsupported")


def tex_files(root: Path, main: Path) -> list[Path]:
    files: list[Path] = []

    def visit(path: Path) -> None:
        if path in files:
            return
        files.append(path)
        text = strip_comments(path.read_text(encoding="utf-8"))
        if re.search(r"\\(?:import|subimport|subfile|includeonly)\b", text):
            raise ValueError("Resolve import/subfile/includeonly into a working project before prepare")
        for match in re.finditer(r"\\(?:input|include)\b\s*(?:\{([^}]+)\}|([^\s%{}]+))", text):
            name = (match.group(1) or match.group(2)).strip()
            if "\\" in name or "#" in name:
                raise ValueError(f"Resolve dynamic TeX input first: {name}")
            if not Path(name).suffix:
                name += ".tex"
            candidates = [inside(root, name), inside(root, str(path.parent.relative_to(root) / name))]
            child = next((p for p in candidates if p.is_file()), None)
            if child is None:
                raise ValueError(f"Missing input file: {name}")
            if child.suffix == ".tex":
                visit(child)
    visit(main)
    return files


def pymupdf():
    try:
        import pymupdf as module
        return module
    except ImportError as exc:
        raise ValueError("PDF support needs PyMuPDF: install scripts/requirements.txt in a venv") from exc


def prepare(args: argparse.Namespace) -> None:
    source = Path(args.source).resolve()
    job = Path(args.job).resolve()
    if not source.exists():
        raise ValueError(f"Source not found: {source}")
    if job.exists():
        raise ValueError("Job already exists; use status/next to resume or choose a new job directory")
    root = Path(args.project_root).resolve() if args.project_root else (source if source.is_dir() else source.parent)
    is_tex = source.is_dir() or source.suffix.lower() == ".tex" or source.name.endswith((".zip", ".tar", ".tar.gz", ".tgz"))
    if (source.is_dir() or source.suffix.lower() == ".tex") and job.is_relative_to(root):
        raise ValueError("Place the job outside the source project to avoid recursive copying")
    job.mkdir(parents=True)
    manifest = {"version": 1, "source": str(source), "language": args.language, "mode": "tex" if is_tex else "pdf", "files": [], "chunks": [], "warnings": []}

    def add_file(name: str, text: str, page: int | None = None) -> None:
        protected, mapping = protect(text, tuple(args.prose_command)) if is_tex else protect_markdown(text) if args.mineru_json else (text, {})
        file_index = len(manifest["files"])
        manifest["files"].append({"path": name, "source": text, "mapping": mapping, "page": page})
        for part in chunks(protected, args.chunk_chars):
            chunk_id = f"{len(manifest['chunks']) + 1:04d}"
            record = {"id": chunk_id, "file": file_index, "source": part, "automatic": (is_tex or bool(args.mineru_json)) and not TOKEN.sub("", part).strip()}
            manifest["chunks"].append(record)
            path = job / "chunks" / f"{chunk_id}.source.txt"
            path.parent.mkdir(exist_ok=True)
            path.write_text(part, encoding="utf-8")
    if is_tex:
        project = job / "source-project"
        if source.is_file() and source.suffix != ".tex":
            unpack(source, project)
        else:
            if not source.is_relative_to(root):
                raise ValueError("Source must be inside project-root")
            shutil.copytree(root, project, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".DS_Store"))
        if args.main:
            main = inside(project, args.main)
        elif source.suffix == ".tex":
            main = project / source.relative_to(root)
        else:
            candidates = [p for p in project.rglob("*.tex") if re.search(r"\\documentclass\b", strip_comments(p.read_text(encoding="utf-8")))]
            if len(candidates) != 1:
                raise ValueError("Specify --main relative to the project root; candidates: " + ", ".join(str(p.relative_to(project)) for p in candidates))
            main = candidates[0]
        manifest["main"] = str(main.relative_to(project))
        for path in tex_files(project, main):
            add_file(str(path.relative_to(project)), path.read_text(encoding="utf-8"))
    else:
        if source.suffix.lower() != ".pdf":
            raise ValueError("Expected PDF, TeX, project directory, ZIP or TAR archive")
        shutil.copy2(source, job / "original.pdf")
        (job / "pages").mkdir()
        module = pymupdf()
        with module.open(source) as doc:
            parsed_pages = import_pages(Path(args.mineru_json).resolve(), job, len(doc)) if args.mineru_json else None
            manifest["parser"] = "mineru-local-import" if parsed_pages is not None else "pymupdf"
            for number, page in enumerate(doc, 1):
                page.get_pixmap(matrix=module.Matrix(1.5, 1.5)).save(job / "pages" / f"{number:04d}.png")
                blocks = page.get_text("blocks", sort=True)
                text = "\n\n".join(block[4].strip() for block in blocks if block[6] == 0 and block[4].strip())
                if parsed_pages is not None:
                    text = parsed_pages[number - 1]
                if len(text.strip()) < 60:
                    manifest["warnings"].append(f"Page {number}: sparse text; inspect page image and transcribe/OCR before translating")
                add_file(f"page-{number:04d}", text or f"[Page {number}: read the page image; no extractable text]", number)
        manifest["warnings"].append("PDF text order, equations and tables require visual review; original page images are preserved in the bilingual export")
    if not manifest["chunks"]:
        raise ValueError("No content to translate")
    write_json(job / "manifest.json", manifest)
    (job / "glossary.md").write_text("# 术语表\n\n| 原文 | 译法 |\n| --- | --- |\n", encoding="utf-8")
    status(args)


def checkpoint(job: Path, chunk: dict, mode: str) -> dict | None:
    if chunk["automatic"]:
        return {"translation": chunk["source"], "note": "Non-prose TeX"}
    path = job / "translations" / f"{chunk['id']}.json"
    if not path.exists():
        return None
    saved = read_json(path)
    if saved.get("source") != chunk["source"]:
        raise ValueError(f"Stale checkpoint {chunk['id']}; source changed")
    validate(chunk["source"], saved["translation"], mode == "tex")
    return saved


def status(args: argparse.Namespace) -> None:
    job = Path(args.job)
    manifest = read_json(job / "manifest.json")
    pending = [c["id"] for c in manifest["chunks"] if checkpoint(job, c, manifest["mode"]) is None]
    print(json.dumps({"mode": manifest["mode"], "total": len(manifest["chunks"]), "completed": len(manifest["chunks"]) - len(pending), "pending": pending, "warnings": manifest["warnings"]}, ensure_ascii=False, indent=2))


def next_chunk(args: argparse.Namespace) -> None:
    job = Path(args.job)
    manifest = read_json(job / "manifest.json")
    for chunk in manifest["chunks"]:
        if checkpoint(job, chunk, manifest["mode"]) is None:
            file = manifest["files"][chunk["file"]]
            mapping = file["mapping"]
            print(json.dumps({"id": chunk["id"], "language": manifest["language"], "file": file["path"], "page_image": str((job / "pages" / f"{file['page']:04d}.png").resolve()) if file["page"] else None, "source": chunk["source"], "protected_content": {t: mapping[t] for t in TOKEN.findall(chunk["source"])}, "glossary": (job / "glossary.md").read_text(encoding="utf-8")}, ensure_ascii=False, indent=2))
            return
    print("All chunks complete")


def accept(args: argparse.Namespace) -> None:
    job = Path(args.job)
    manifest = read_json(job / "manifest.json")
    chunk = next((c for c in manifest["chunks"] if c["id"] == args.id), None)
    if chunk is None:
        raise ValueError(f"Unknown chunk: {args.id}")
    translated = Path(args.translation).read_text(encoding="utf-8")
    validate(chunk["source"], translated, manifest["mode"] == "tex")
    if translated.strip() == chunk["source"].strip() and not args.note:
        raise ValueError("Unchanged chunk requires --note explaining why its original text is retained")
    path = job / "translations" / f"{args.id}.json"
    write_json(path, {"source": chunk["source"], "translation": translated, "note": args.note or ""})
    print(f"Accepted {args.id}")


def cjk_preamble(text: str) -> str:
    if re.search(r"\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?\{(?:ctex|xeCJK)\}|\\documentclass(?:\[[^\]]*\])?\{ctex", strip_comments(text)):
        return text
    match = re.search(r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{[^}]+\}", strip_comments(text))
    if not match:
        raise ValueError("Main file has no documentclass")
    snippet = "\n\\usepackage{xeCJK}\n\\setCJKmainfont{FandolSong-Regular.otf}[BoldFont=FandolSong-Bold.otf,ItalicFont=FandolKai-Regular.otf]\n\\setCJKsansfont{FandolHei-Regular.otf}\n\\setCJKmonofont{FandolFang-Regular.otf}\n"
    text = text[:match.end()] + snippet + text[match.end():]
    return text.replace(r"\begin{document}", "\\AtBeginDocument{\\IfPackageLoadedTF{microtype}{\\microtypesetup{protrusion=false}}{}}\n\\begin{document}", 1)


def assemble(args: argparse.Namespace) -> None:
    job = Path(args.job).resolve()
    manifest = read_json(job / "manifest.json")
    translated = ["" for _ in manifest["files"]]
    notes = []
    for chunk in manifest["chunks"]:
        saved = checkpoint(job, chunk, manifest["mode"])
        if saved is None:
            raise ValueError(f"Translation incomplete: chunk {chunk['id']}")
        translated[chunk["file"]] += saved["translation"]
        if saved.get("note") and not chunk["automatic"]:
            notes.append(f"{chunk['id']}: {saved['note']}")
    out = Path(args.output).resolve()
    if out.exists():
        raise ValueError("Output already exists; choose a new output directory")
    if out == job or job.is_relative_to(out) or out.is_relative_to(job / "source-project"):
        raise ValueError("Output conflicts with the job's source files")
    out.mkdir(parents=True)
    if manifest["mode"] == "tex":
        shutil.copytree(job / "source-project", out / "project")
        for file, value in zip(manifest["files"], translated):
            path = out / "project" / file["path"]
            path.write_text(restore(value, file["mapping"]), encoding="utf-8")
        main = out / "project" / manifest["main"]
        main.write_text(cjk_preamble(main.read_text(encoding="utf-8")), encoding="utf-8")
        # A source archive may contain its original compiled PDF.
        main.with_suffix(".pdf").unlink(missing_ok=True)
    else:
        shutil.copy2(job / "original.pdf", out / "original.pdf")
        if (job / "assets").is_dir():
            shutil.copytree(job / "assets", out / "assets")
        markdown = []
        sections = []
        for file, value in zip(manifest["files"], translated):
            page = file["page"]
            value = restore(value, file["mapping"])
            markdown.append(f"## 原文第 {page} 页\n\n{value}\n")
            data = base64.b64encode((job / "pages" / f"{page:04d}.png").read_bytes()).decode("ascii")
            sections.append(f'<section id="p{page}"><h2>第 {page} 页</h2><div class="pair"><img alt="原文第 {page} 页" src="data:image/png;base64,{data}"><div class="translation">{html.escape(value)}</div></div></section>')
        (out / "translated.md").write_text("\n".join(markdown), encoding="utf-8")
        (out / "bilingual.html").write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>论文双语对照</title><style>body{max-width:1600px;margin:32px auto;padding:0 24px;background:#faf9f6;color:#202a31;font:17px/1.8 system-ui,sans-serif}h1,h2{font-weight:600}.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}img{width:100%;border:1px solid #ddd}.translation{white-space:pre-wrap;overflow-wrap:anywhere;background:white;padding:24px;border:1px solid #ddd}section{margin-bottom:48px}@media(max-width:800px){.pair{grid-template-columns:1fr}}@media print{section{break-before:page}body{padding:0;margin:0}}</style><h1>论文双语对照</h1><p>原文页面 · 译文（公式保留 LaTeX 记法）</p>' + "".join(sections) + '</html>', encoding="utf-8")
    shutil.copy2(job / "glossary.md", out / "glossary.md")
    write_json(out / "translation-report.json", {"source": manifest["source"], "language": manifest["language"], "mode": manifest["mode"], "parser": manifest.get("parser", "tex"), "chunks": len(manifest["chunks"]), "structural_checks": "passed", "semantic_review": "required; marker validation cannot prove translation completeness or accuracy", "warnings": manifest["warnings"], "retained_original_or_notes": notes})
    print(str(out))


def compile_tex(args: argparse.Namespace) -> None:
    main = Path(args.main).resolve()
    engine = shutil.which("xelatex")
    if not engine and Path("/Library/TeX/texbin/xelatex").is_file():
        engine = "/Library/TeX/texbin/xelatex"
    if not engine:
        raise ValueError("XeLaTeX is unavailable; retain the translated TeX project and install a TeX runtime to compile")
    latexmk = shutil.which("latexmk") or str(Path(engine).with_name("latexmk"))
    if Path(latexmk).is_file():
        command = [latexmk, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-no-shell-escape", main.name]
        passes = 1
    else:
        command = [engine, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "-no-shell-escape", main.name]
        passes = 2
    import os
    env = dict(os.environ)
    env["PATH"] = str(Path(engine).parent) + os.pathsep + env.get("PATH", "")
    for _ in range(passes):
        result = subprocess.run(command, cwd=main.parent, env=env, capture_output=True, text=True, timeout=240)
        (main.parent / "paperreader-build.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise ValueError(f"Compilation failed; inspect {main.parent / 'paperreader-build.log'}")
    log = main.with_suffix(".log")
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    issues = [line for line in text.splitlines() if any(word in line for word in ("Missing character:", "undefined", "Overfull", "LaTeX Warning:"))]
    if not main.with_suffix(".pdf").is_file():
        raise ValueError("Compiler produced no PDF")
    print(json.dumps({"pdf": str(main.with_suffix(".pdf")), "review": issues}, ensure_ascii=False, indent=2))
    if any("Missing character:" in issue for issue in issues):
        raise ValueError("PDF has missing glyphs; fix fonts before delivery")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("source")
    prep.add_argument("--job", required=True)
    prep.add_argument("--main")
    prep.add_argument("--mineru-json", help="Local MinerU *_content_list.json for the same PDF")
    prep.add_argument("--project-root")
    prep.add_argument("--language", default="简体中文")
    prep.add_argument("--chunk-chars", type=int, default=5000)
    prep.add_argument("--prose-command", action="append", default=[])
    prep.set_defaults(run=prepare)
    for name, function in [("status", status), ("next", next_chunk)]:
        cmd = commands.add_parser(name)
        cmd.add_argument("--job", required=True)
        cmd.set_defaults(run=function)
    take = commands.add_parser("accept")
    take.add_argument("--job", required=True)
    take.add_argument("--id", required=True)
    take.add_argument("--translation", required=True)
    take.add_argument("--note")
    take.set_defaults(run=accept)
    build = commands.add_parser("assemble")
    build.add_argument("--job", required=True)
    build.add_argument("--output", required=True)
    build.set_defaults(run=assemble)
    compile_cmd = commands.add_parser("compile")
    compile_cmd.add_argument("main")
    compile_cmd.set_defaults(run=compile_tex)
    args = parser.parse_args()
    try:
        args.run(args)
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired, tarfile.TarError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
