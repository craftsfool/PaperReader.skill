# LaTeX 工程

## 准备

```bash
"$PYTHON" "$SCRIPT" prepare /path/to/project/main.tex --job "$JOB"
"$PYTHON" "$SCRIPT" prepare /path/to/project --main main.tex --job "$JOB"
"$PYTHON" "$SCRIPT" prepare /path/to/source.tar.gz --main paper/main.tex --job "$JOB"
```

工作目录必须位于输入工程之外。单个 `.tex` 默认以其父目录为工程根；当主文件在工程子目录中时用 `--project-root` 指定完整资源根。避免以下载目录或整个仓库为单文件论文的工程根，先整理出这篇论文的文件夹。

支持 ZIP、TAR、TAR.GZ、TGZ。候选主文件不唯一时根据 documentclass、正文和输入关系指定 `--main`。解包只接受普通文件和目录；不执行归档中的脚本。

脚本保留工程目录和图片、sty、bib 等文件，并跟踪 `input` / `include` 的 `.tex` 文件。与 PaperReader 的扁平化路线不同，这里保留文件路径，避免破坏相对图片路径。动态输入、import/subimport/subfile/includeonly 需先在工作副本中整理为能独立编译的静态工程，再创建翻译任务。源文件使用 UTF-8。

## 保护范围

数学分隔符 `$…$`、`$$…$$`、`\(…\)`、`\[…\]` 和常见数学环境整体保护；引用、标签、图片路径、宏定义、代码环境、文献表保护。标题、正文、章节名、图注、表格文字、脚注和常见文字格式命令的内容参与翻译。

主文件导言区整体保留，title/shorttitle 可翻译。未知命令及紧随参数默认保留。检查自定义宏，例如 `\mycaption{human text}`；确定参数均为自然语言时，在 prepare 时加 `--prose-command mycaption`。含混合配置/正文参数的自定义命令先在工作副本中展开，不能把配置值当正文翻译。未知环境的可读正文会翻译；自定义数学环境先规范成支持的数学环境，或由 Codex 在工作副本中处理。

## 编译

```bash
"$PYTHON" "$SCRIPT" assemble --job "$JOB" --output /path/to/deliverable
"$PYTHON" "$SCRIPT" compile /path/to/deliverable/project/main.tex
```

组装时为尚无 ctex/xeCJK 的工程加入 xeCJK 和 TeX Live 的 Fandol 中文字体，关闭 microtype protrusion。已有中文字体配置保留。根据目标语言在译本中调整 abstractname、figurename、tablename 等自动标题，保证摘要与图表编号前缀也使用目标语言。默认使用 latexmk + XeLaTeX；缺少 latexmk 时运行两遍 XeLaTeX，带参考文献的项目需要另行运行 bibtex/biber 后重编译。编译默认禁用 shell escape。

编译退出成功仍需检查警告和渲染结果。脚本遇到中文缺字会返回失败；Overfull、未定义引用等在输出中报告。期刊模板可能包含仅限 pdfTeX 的宏或自定义字体，需要针对编译日志修改译本；不要全局删除宏、公式、参考文献或图表来获取成功状态。

没有 TeX 运行时时仍交付完整译文工程，明确未生成 PDF。不要把原来的 PDF 当作已翻译 PDF；组装时移除主文件对应的旧 PDF；工程中的其他 PDF 可能是图表素材，予以保留。只有实际成功编译且视觉检查过的文件才可作为译文交付。

可用 PyMuPDF 将 PDF 页渲染成图供 Codex 查看：

```python
import pymupdf
with pymupdf.open("main.pdf") as doc:
    for i, page in enumerate(doc):
        page.get_pixmap(matrix=pymupdf.Matrix(1.3, 1.3)).save(f"page-{i+1}.png")
```
