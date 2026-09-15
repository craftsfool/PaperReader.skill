# PDF 本地解析与阅读版

PDF 没有可靠的原始 LaTeX 结构。此路线提供可校对的全文译文及原页对照，不能承诺恢复原始 TeX 或逐像素复刻版式。

## 提取与翻译

优先按 [MinerU 本地解析](mineru.md) 运行并传入 `--mineru-json`，使用其结构化结果。以下纯 PyMuPDF 方式用于没有 MinerU 的环境。

`prepare paper.pdf --job …` 使用 PyMuPDF 提取每页文字块并生成 `pages/0001.png` 等原页图。每页单独分块，不自动混合跨页内容。图片、矢量图表、公式和版面都保留在页图中，最终嵌入双语 HTML。

先查看页图确认栏序与内容，再翻译 `next` 的文字。文本提取常把双栏交错、数学符号拆开或误收页眉；结合页图修正，不能按抽取顺序机械翻译。整页拆为多个块时，在 review.md 记录各块覆盖段落，避免重复或遗漏。需要更清晰的符号时用 PyMuPDF 放大并裁切相应区域。

扫描页会提示 sparse text。可用当前 Codex 的图像阅读转写并翻译，也可使用环境已有的本地 OCR；必须对照图像核对公式。默认不使用云 OCR、MinerU API 或外部视觉模型。无法辨认的内容明确标注，若影响主要论述则说明该页仍未完整翻译。

PDF 模式接受 Markdown：章节标题、列表、表格、`$…$` 和 `$$…$$`。若图中文字需要翻译，保留原图并在图注中说明中文术语对应，不伪造测量值。参考文献保留原文。

## 输出

自动组装得到：

- `translated.md`：按原文页码锚定的全文译文，数学式采用 LaTeX。
- `bilingual.html`：离线原页图/译文对照。无远程资源；Markdown 和 LaTeX 以源码文本显示，适合溯源校对。
- `original.pdf`、术语表和结构检查报告。

默认继续制作可读中文 PDF：由 Codex 将已校对的 Markdown 转为简洁 `ctexart` 文档，保留章节、数学式、图表及页码对应关系，使用 `compile` 编译。若环境已有 Pandoc，可用它转换 Markdown 数学和表格，再检查产出的 TeX；不要求用户安装整套 PaperReader。

```latex
\documentclass[UTF8,fontset=fandol]{ctexart}
\usepackage[a4paper,margin=23mm]{geometry}
\usepackage{amsmath,amssymb,graphicx,longtable,booktabs,hyperref}
\begin{document}
% 已校对的完整译文；图表从原 PDF 裁切到本地 assets/ 并引用
\end{document}
```

从 PDF 裁切公式或图表时保留足够边界与分辨率。在能可靠转写的情况下用 LaTeX 表达公式；无法准确转写时使用原公式裁图，不能猜测。中文 PDF 是重排阅读版，图表和原文页码可追溯，不宣传为原版式中文 PDF。

编译后查看每页，核对图表数量、公式、段落覆盖和缺字。若运行环境无法生成 PDF，交付 Markdown 和双语 HTML，准确说明缺少的运行条件。
