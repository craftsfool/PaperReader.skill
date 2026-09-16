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

## 编译失败后的修复

迁自上游 v2.1.10 的编译反馈流程，由当前 Codex 会话执行诊断和编辑。脚本不会调用修复模型或自动改写论文。

`compile` 每次运行在主文件目录的 `.paperreader-builds/0001/` 等独立目录中保存编译前的 TeX/sty/cls 快照、日志和 `report.json`。后续运行创建新编号，保留已有记录；外部编译日志也可通过以下命令诊断：

```bash
"$PYTHON" "$SCRIPT" diagnose /path/deliverable/project/main.tex --log /path/compiler.log
```

1. 读取最新报告中的错误、带行号源码上下文和日志末尾。无行号或日志缺失时，继续检查主文件、导言区及 input/include；`l.N` 单独出现时文件归属仅为猜测，报告会标注。不要把旧日志当作本轮结果。
2. 找到根因后，仅编辑译文工作副本；可修正导言区定义、引入确实需要且已安装的普通宏包，或修复完整的损坏环境。不要为了通过编译删除正文、公式、图表、文献或开放 shell escape。编辑前保留原文件副本；报告中的快照对应该轮编译开始时的状态。
3. 重新运行 `compile`，将本轮诊断、修改理由、重新编译结果记录到工作目录 `review.md`。下一轮使用新日志和上轮结果，不能反复执行相同的无效改动。
4. 通常最多尝试五轮修复；若连续两轮相同失败且没有新证据，或缺少必要资源，则停止自动修复，保留完整源码、诊断和确切阻塞原因。未编译成功的已有 PDF 不得作为新译本交付。
5. 编译通过后仍检查缺字、引用和溢出，并实际渲染校对。`.paperreader-builds/` 属于工作记录，打包交付时保留在工作目录即可，不必把全部历史源码放进最终压缩包。
