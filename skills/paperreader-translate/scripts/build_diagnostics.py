"""Local compiler feedback and immutable per-attempt source snapshots."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil


def snapshot(main: Path) -> Path:
    main = main.resolve()
    root = main.parent / '.paperreader-builds'
    root.mkdir(exist_ok=True)
    number = 1
    while True:
        attempt = root / f'{number:04d}'
        try:
            attempt.mkdir()
            break
        except FileExistsError:
            number += 1
    for path in main.parent.rglob('*'):
        if (path.suffix.lower() in {'.tex', '.sty', '.cls'} and path.is_file()
                and not path.is_symlink() and root not in path.parents
                and path.resolve().is_relative_to(main.parent)):
            target = attempt / 'source' / path.relative_to(main.parent)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    return attempt


def diagnose(main: Path, text: str, radius: int = 12) -> dict:
    """Line numbers guide inspection; they never constrain the eventual repair."""
    main = main.resolve()
    errors = []
    for line in text.splitlines():
        match = re.match(r'^(.+\.(?:tex|sty|cls)):(\d+):\s*(.*)', line)
        if match:
            errors.append({'file': match[1], 'line': int(match[2]), 'message': match[3], 'anchor': 'file-line'})
        elif line.startswith('!'):
            errors.append({'file': None, 'line': None, 'message': line, 'anchor': 'unlocated'})
        elif re.match(r'^l\.\d+\s', line) and errors and errors[-1]['line'] is None:
            errors[-1].update(line=int(re.match(r'^l\.(\d+)', line)[1]), anchor='line-only')
    warnings = [line for line in text.splitlines() if any(s in line for s in
                ('Missing character:', 'undefined', 'Overfull', 'LaTeX Warning:'))]
    contexts = []
    seen = set()
    for error in errors[:20]:
        # TeX's l.N alone does not identify an included file. Label the assumption.
        path = (main.parent / error['file']).resolve() if error['file'] else main
        if not path.is_relative_to(main.parent) or not path.is_file():
            continue
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        if error['line'] is None or not 1 <= error['line'] <= len(lines):
            continue
        start, end = max(1, error['line'] - radius), min(len(lines), error['line'] + radius)
        key = (str(path), start, end)
        if key in seen:
            continue
        seen.add(key)
        contexts.append({'file': str(path), 'location_assumed': not bool(error['file']),
                         'start_line': start, 'end_line': end,
                         'source': '\n'.join(f'{n}: {lines[n - 1]}' for n in range(start, end + 1))})
    if not contexts:
        lines = main.read_text(encoding='utf-8', errors='replace').splitlines()
        contexts.append({'file': str(main), 'location_assumed': True, 'start_line': 1,
                         'end_line': min(80, len(lines)),
                         'source': '\n'.join(f'{n + 1}: {s}' for n, s in enumerate(lines[:80]))})
    return {'errors': errors[:20], 'review': warnings, 'contexts': contexts,
            'log_tail': text[-16000:], 'source': str(main),
            'guidance': 'Inspect the latest log and earlier causes, including preamble and included files. Preserve paper content; repair only the translated working copy.'}


def save_report(main: Path, attempt: Path, output: str, returncode: int | None, failure: str | None = None) -> dict:
    (attempt / 'compiler-output.log').write_text(output, encoding='utf-8')
    (main.parent / 'paperreader-build.log').write_text(output, encoding='utf-8')
    log = main.with_suffix('.log')
    log_text = log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''
    if log.exists():
        shutil.copy2(log, attempt / log.name)
    report = diagnose(main, log_text + '\n' + output)
    success = failure is None and returncode == 0 and main.with_suffix('.pdf').is_file() and not any(
        'Missing character:' in item for item in report['review'])
    report.update(success=success, returncode=returncode, failure=failure, attempt=str(attempt))
    report['pdf'] = str(main.with_suffix('.pdf')) if success else None
    (attempt / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
