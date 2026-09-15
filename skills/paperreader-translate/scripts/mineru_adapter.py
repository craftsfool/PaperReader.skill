"""Import MinerU's documented content_list.json with page and asset provenance."""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

from tex_guard import TOKEN


def protect_markdown(text: str) -> tuple[str, dict[str, str]]:
    if TOKEN.search(text):
        raise ValueError('Source contains reserved PaperReader markers')
    mapping = {}
    pattern = re.compile(
        r'```[\s\S]*?```|`[^`\n]+`|!\[[^\]]*\]\([^\n)]+\)'
        r'|(?<!\\)\$\$[\s\S]*?(?<!\\)\$\$'
        r'|(?<!\\)\$[^$\n]+?(?<!\\)\$'
        r'|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)'
        r'|</?[A-Za-z][^>]*>|https?://[^\s<>]+')

    def replace(match):
        token = f'⟦PR{len(mapping):06d}⟧'
        mapping[token] = match.group()
        return token
    return pattern.sub(replace, text), mapping


def import_pages(content_path: Path, job: Path, page_count: int) -> list[str]:
    data = json.loads(content_path.read_text(encoding='utf-8'))
    if not isinstance(data, list) or any(not isinstance(b, dict) or 'page_idx' not in b for b in data):
        raise ValueError('Use MinerU *_content_list.json (flat blocks with page_idx), not content_list_v2.json')
    pages = [[] for _ in range(page_count)]
    assets = job / 'assets'
    assets.mkdir(exist_ok=True)
    shutil.copy2(content_path, job / 'mineru-content-list.json')

    def strings(value):
        if not value:
            return ''
        if isinstance(value, str):
            return value
        if isinstance(value, list) and all(isinstance(x, str) for x in value):
            return '\n\n'.join(value)
        raise ValueError('Unexpected MinerU text field; inspect parser schema before importing')

    def image(block):
        name = block.get('img_path')
        if not name:
            return ''
        root = content_path.parent.resolve()
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Missing or external MinerU asset: {name}')
        destination = assets / Path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        return f'![]({destination.relative_to(job).as_posix()})'

    for block in data:
        index = block['page_idx']
        if not isinstance(index, int) or not 0 <= index < page_count:
            raise ValueError(f'MinerU page_idx outside supplied PDF: {index}')
        kind = block.get('type')
        parts = []
        if kind in {'text', 'header', 'footer', 'page_number', 'aside_text', 'page_footnote'}:
            value = strings(block.get('text'))
            level = block.get('text_level', 0)
            parts.append(('#' * max(1, min(int(level), 6)) + ' ' if level else '') + value)
        elif kind == 'equation':
            value = strings(block.get('text'))
            parts.append(value if value.lstrip().startswith(('$$', r'\[')) else '$$\n' + value + '\n$$' if value else image(block))
        elif kind in {'image', 'chart', 'table'}:
            parts.append(image(block))
            parts.append(strings(block.get(f'{kind}_caption')))
            if kind == 'table':
                parts.append(strings(block.get('table_body')))
            parts.append(strings(block.get(f'{kind}_footnote')))
            if block.get('content'):
                parts.append(strings(block['content']))
        elif kind == 'list':
            items = block.get('list_items', [])
            if not isinstance(items, list) or not all(isinstance(x, str) for x in items):
                raise ValueError('Unexpected MinerU list_items')
            parts.extend('- ' + item for item in items)
        elif kind == 'code':
            parts.extend([strings(block.get('code_caption')), '```\n' + strings(block.get('code_body')) + '\n```', strings(block.get('code_footnote'))])
        else:
            raise ValueError(f'Unsupported MinerU block type: {kind}; inspect this block instead of dropping it')
        text = '\n\n'.join(p for p in parts if p.strip())
        if text:
            pages[index].append(text)
    return ['\n\n'.join(page) for page in pages]
