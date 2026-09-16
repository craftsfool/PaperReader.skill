"""Caption-based PDF figure/table navigation; no parser service or model calls."""
from __future__ import annotations

import html
import json
from pathlib import Path
import re

CAPTION = r'(?P<kind>Figure|Fig\.?|Table|图|表)\s*(?P<number>\d+(?:[.-]\d+)?)\s*[.:：．]\s*'
STRICT = re.compile(r'^\s*' + CAPTION, re.I)
MERGED = re.compile(r'^\s*(?:\([a-z]\)\s*|[a-z](?=Figure|Fig|Table))' + CAPTION, re.I)


def captions(doc) -> list[dict]:
    choices = {}
    for page_index, page in enumerate(doc):
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                text = ''.join(span['text'] for span in line['spans']).strip()
                match = STRICT.match(text)
                priority = 0
                if not match:
                    match = MERGED.search(text)
                    priority = 1
                if not match:
                    continue
                kind = 'table' if match['kind'].lower() in {'table', '表'} else 'figure'
                key = (kind, match['number'])
                item = {'kind': kind, 'number': match['number'], 'caption': text,
                        'page': page_index + 1, 'caption_bbox': list(line['bbox']),
                        'caption_bottom': block['bbox'][3] if block['bbox'][3] - line['bbox'][3] < 40 else line['bbox'][3],
                        'priority': priority}
                if key not in choices or priority < choices[key]['priority']:
                    choices[key] = item
    return sorted(choices.values(), key=lambda x: (x['page'], x['caption_bbox'][1], x['caption_bbox'][0]))


def crop_artwork(page, item: dict, peers: list[dict]):
    import pymupdf as fitz
    caption = fitz.Rect(item['caption_bbox'])
    def same_region(rect):
        low, high = sorted(((caption.y0 + caption.y1) / 2, (rect.y0 + rect.y1) / 2))
        return not any(p is not item and low < p['caption_bbox'][1] < high
                       and rect.x0 - 4 <= p['caption_bbox'][0] <= rect.x1 + 4 for p in peers)
    if item['kind'] == 'table':
        candidates = [fitz.Rect(d['rect']) for d in page.get_drawings()
                      if d['rect'].width >= 36 and d['rect'].height <= 3]
    else:
        candidates = [fitz.Rect(info['bbox']) for info in page.get_image_info()
                      if fitz.Rect(info['bbox']).width >= 12 and fitz.Rect(info['bbox']).height >= 12]
        # cluster_drawings includes vector plots as well as imported PDF artwork.
        if hasattr(page, 'cluster_drawings'):
            candidates += [fitz.Rect(rect) for rect in page.cluster_drawings()
                           if rect.width >= 12 and rect.height >= 12]
    # Adjacent columns can be closer than panels of the same figure. Use other
    # captions to establish column boundaries before grouping artwork.
    left = max([(p['caption_bbox'][2] + caption.x0) / 2 for p in peers
                if p['caption_bbox'][2] < caption.x0], default=0)
    right = min([(p['caption_bbox'][0] + caption.x1) / 2 for p in peers
                 if p['caption_bbox'][0] > caption.x1], default=page.rect.width)
    middle = page.rect.width / 2
    if caption.x1 < middle and any(p['caption_bbox'][0] > middle for p in peers):
        right = middle
    if caption.x0 > middle and any(p['caption_bbox'][2] < middle for p in peers):
        left = middle
    candidates = [r for r in candidates if r.x0 >= left - 4 and r.x1 <= right + 4
                  and same_region(r) and r.width < page.rect.width * .98
                  and r.height < page.rect.height * .9]
    distance = lambda r: max(0, caption.y0 - r.y1, r.y0 - caption.y1)
    # Scientific figures usually precede their captions; tables usually follow.
    # Choosing the absolute nearest object can select the next figure instead.
    if item['kind'] == 'table':
        nearby = [r for r in candidates if r.y0 >= caption.y1
                  and r.x0 <= caption.x1 and r.x1 >= caption.x0]
    else:
        nearby = [r for r in candidates if r.y0 < caption.y0
                  and r.x0 <= caption.x1 and r.x1 >= caption.x0]
    if not nearby:
        return None
    nearest = min(nearby, key=distance)
    if distance(nearest) > 72:
        return None
    if item['kind'] == 'table':
        selected = [r for r in nearby if abs(r.x0 - nearest.x0) < 3 and abs(r.x1 - nearest.x1) < 3
                    and distance(r) <= 300]
        if len(selected) < 2:
            return None
    else:
        selected = [nearest]
        remaining = [r for r in candidates if r != nearest and r.y0 < caption.y0]
        while remaining:
            adjacent = [r for r in remaining if any(max(0, r.x0 - b.x1, b.x0 - r.x1) <= 48
                        and max(0, r.y0 - b.y1, b.y0 - r.y1) <= 48 for b in selected)]
            if not adjacent:
                break
            selected.extend(adjacent)
            remaining = [r for r in remaining if r not in adjacent]
    # Rect unions discard zero-height horizontal rules, losing most of a table.
    box = fitz.Rect(min(r.x0 for r in selected), min(r.y0 for r in selected),
                    max(r.x1 for r in selected), max(r.y1 for r in selected))
    if box.height < 12:
        return None
    if item['kind'] == 'figure':
        previous = [p.get('caption_bottom', p['caption_bbox'][3]) for p in peers if p is not item
                    and p['caption_bbox'][3] < caption.y0
                    and p['caption_bbox'][0] < box.x1 and p['caption_bbox'][2] > box.x0]
        top = max(previous, default=0)
        region = fitz.Rect(max(0, box.x0 - 28), max(top, box.y0 - 16),
                           min(page.rect.width, box.x1 + 28), caption.y0 - 2)
        # PDF drawing bounds omit axis labels and legends, which are text objects.
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                rect = fitz.Rect(line['bbox'])
                if region.contains(rect):
                    box |= rect
        box = box & fitz.Rect(0, top, page.rect.width, caption.y0 - 2)
    return fitz.Rect(box.x0 - 6, max(top + 1, box.y0 - 6) if item['kind'] == 'figure' else box.y0 - 6, box.x1 + 6,
                     min(box.y1 + 6, caption.y0 - 1) if item['kind'] == 'figure' else box.y1 + 6) & page.rect


def build_gallery(original: Path, translated: Path | None, output: Path) -> dict:
    import pymupdf as fitz
    if output.exists():
        raise ValueError('Gallery output already exists; use a new directory after PDF changes')
    for path in (original, translated):
        if path is not None and not path.is_file():
            raise ValueError(f'PDF not found: {path}')
    output.mkdir(parents=True)
    entries = {}
    for side, path in [('original', original), ('translated', translated)]:
        if path is None:
            continue
        # Copy for a portable offline gallery with PDF page links.
        import shutil
        shutil.copy2(path, output / f'{side}.pdf')
        with fitz.open(path) as doc:
            items = captions(doc)
            for i, item in enumerate(items):
                page = doc[item['page'] - 1]
                peers = [p for p in items if p['page'] == item['page']]
                box = crop_artwork(page, item, peers)
                item['crop_method'] = 'artwork-heuristic' if box else 'full-page-fallback'
                item['preview_bbox'] = list(box or page.rect)
                item['preview'] = f'{side}-{i + 1:03}.png'
                page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2), clip=box, alpha=False).save(output / item['preview'])
                entries.setdefault((item['kind'], item['number']), {})[side] = item
    result = {'items': [{'kind': key[0], 'number': key[1], **value} for key, value in entries.items()],
              'limitations': 'Caption and crop detection is heuristic. Verify against PDFs; undetected or unnumbered captions require manual indexing. Full-page previews are explicitly labeled. Each PDF is located independently.'}
    (output / 'figures.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    cards = []
    for item in result['items']:
        cells = []
        for side, label in [('original', '原文'), ('translated', '译文')]:
            value = item.get(side)
            if value is None:
                cells.append(f'<div>{label}：未定位</div>')
                continue
            fallback = ' · 整页回退预览' if value['crop_method'] == 'full-page-fallback' else ' · 图表候选裁剪'
            cells.append(f'<div><a href="{side}.pdf#page={value["page"]}">{label}第 {value["page"]} 页{fallback}'
                         f'<img src="{value["preview"]}" alt="{html.escape(value["caption"], quote=True)}"></a>'
                         f'<p>{html.escape(value["caption"])}</p></div>')
        cards.append('<section><h2>' + ('图 ' if item['kind'] == 'figure' else '表 ') + html.escape(item['number']) + '</h2><div class="pair">' + ''.join(cells) + '</div></section>')
    (output / 'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>论文图表导航</title><style>body{max-width:1100px;margin:32px auto;padding:0 24px;font:16px/1.7 system-ui;color:#26343b;background:#faf9f6}.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}img{display:block;max-width:100%;max-height:420px;object-fit:contain}section{background:white;padding:20px;margin:20px 0}a{color:#245b71}@media(max-width:650px){.pair{grid-template-columns:1fr}}</style><h1>论文图表导航</h1><p>原文与译文独立定位。点击预览打开对应 PDF 页面。自动裁剪需对照原页检查；未识别的图表不计入此目录。</p>' + ''.join(cards) + '</html>', encoding='utf-8')
    return result
