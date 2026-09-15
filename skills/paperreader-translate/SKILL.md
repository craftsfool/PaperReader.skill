---
name: paperreader-translate
description: 翻译学术论文 PDF、arXiv 论文和 LaTeX 工程，保留公式、引用与图表，生成中文 PDF、译文源码或双语对照，支持长论文断点续译。用于论文全文或指定章节翻译。
---

# PaperReader Translate

把论文翻译为用户指定语言，默认简体中文。由当前 Codex 会话直接翻译；随附 Python 脚本只做本地文档处理，无 LLM API、MinerU 云 API、API Key 或后台翻译服务。不要启动原 PaperReader 后端、读取账号凭据或通过嵌套 `codex exec` 发起另一轮翻译。

## 输入和准备

1. 确定论文文件或链接、翻译范围；用户未限定时翻译全文。对于链接，用可用下载工具获取论文；arXiv 优先取得同一版本的 TeX 源码和原 PDF，源码不可用时走 PDF 路线。记录来源和版本，不能以不同论文或不同版本替代。
2. 将工作目录放在 `work/<paper>-translation/`，最终文件放入当前环境允许的输出目录。以此 SKILL.md 所在目录定位脚本，不能假设当前目录就是 Skill 目录。
3. 先读 [翻译准则](references/translation.md)。有 TeX 时读 [TeX 流程](references/latex.md)，只有 PDF 时先读 [MinerU 本地解析](references/mineru.md)，再读 [PDF 流程](references/pdf.md)。这些流程包含脚本参数及能力边界。
4. Python 3.10+ 足以运行 TeX 准备、验证和组装；轻量 PDF 解析和页图渲染另需 `scripts/requirements.txt` 的 PyMuPDF。优先使用已提供的运行环境，否则在工作目录新建 venv 并安装依赖，不能安装整个原软件的 requirements。PDF 编译需要 XeLaTeX；可使用已安装的 TeX 工具。

## 翻译与续译

下面的 `SCRIPT` 是 `scripts/paperreader.py` 的绝对路径，`PYTHON` 是所选解释器，`JOB` 是工作目录；在 shell 中使用时定义为变量并加引号。

```bash
"$PYTHON" "$SCRIPT" prepare /absolute/path/paper.pdf --job "$JOB"
"$PYTHON" "$SCRIPT" status --job "$JOB"
"$PYTHON" "$SCRIPT" next --job "$JOB"
```

- `prepare` 只运行一次。恢复任务时读 `manifest.json`、`glossary.md`、`status` 和已有 `review.md`，继续 `next` 的第一个待译块。不要重新创建或更改已有分块的源文。若解析必须修改，另建工作目录。
- 先通读标题、摘要和章节，填写 `glossary.md` 的核心术语。术语表和 review.md 是跨块、跨上下文的工作记忆。
- `next` 返回原文、保护内容和对应 PDF 页图。阅读保护内容以理解公式语境；PDF 页图是恢复阅读顺序、公式和图表的依据，不能只信文本提取。
- 逐块完整翻译，将纯译文写入工作文件。TeX 模式保持 `⟦PR000000⟧` 等标记原样、原序；正文不引入裸 LaTeX 命令或特殊字符。PDF 模式输出 Markdown，可按页图修正顺序并转写数学式。

```bash
"$PYTHON" "$SCRIPT" accept --job "$JOB" --id 0001 --translation /absolute/path/0001.translated.txt
```

- 验证失败时修正该译文，不绕过检查。不把未翻译的英文塞回去充数。确实需要保留的参考文献或专名块可用 `--note '参考文献保留原文'` 显式记录。
- 每块保存后继续处理待译块。长任务遇到会话限制时保留工作目录、说明已完成范围和恢复位置，不把部分结果称作全文完成。

## 导出和校对

```bash
"$PYTHON" "$SCRIPT" assemble --job "$JOB" --output /absolute/path/output-directory
```

`assemble` 拒绝遗漏块、失效断点和已有输出目录。TeX 输出可编译的 `project/`；PDF 输出 `translated.md`、包含全部原页图的离线 `bilingual.html` 和 `original.pdf`。两者都带术语表和结构检查报告。

默认尽量交付中文 PDF：TeX 路线编译原工程的译本；PDF 路线按 PDF 流程制作重排阅读版。编译后实际渲染并检查中文缺字、公式、图表、标题和溢出。修复仅限工作副本，不删掉难编译的内容。源码已有问题与翻译造成的问题要区分。

完成后在输出目录写简短 `review.md`，记录翻译覆盖范围、保留原文的部分、术语、视觉校对结果及未解决的问题。结构验证不能证明语义正确；交付前对照源文检查数字、否定词、比较关系、图表和首尾段。最终给出可点击文件链接，说明是原工程译本还是 PDF 重排版。

## 来源

改编自 [Mars-Dingdang/PaperReader](https://github.com/Mars-Dingdang/PaperReader) 的论文翻译流程；Fork 为 [craftsfool/PaperReader.skill](https://github.com/craftsfool/PaperReader.skill)。参见 [来源与实现范围](references/provenance.md)。
