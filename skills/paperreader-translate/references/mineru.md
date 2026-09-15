# MinerU 本地解析

PDF 优先使用本地 MinerU 的 `pipeline` 后端提取阅读顺序、公式、图表和 OCR 内容，再交给 Codex 翻译。现有 MinerU 解析结果可以直接导入，无须重复运行模型。

## 环境与运行

先检查 `mineru --version`。使用独立 Python 3.10–3.13 环境，安装官方的 pipeline 扩展：

```bash
python3.12 -m venv work/mineru-venv
work/mineru-venv/bin/python -m pip install 'mineru[pipeline]'
work/mineru-venv/bin/mineru -p /path/paper.pdf -o /path/mineru-output -b pipeline
```

解释器版本按机器已有环境选择。也可以在工作目录克隆 [MinerU](https://github.com/opendatalab/MinerU)，在同一环境安装 `-e '.[pipeline]'` 使用源码；需要修改解析器时保留上游来源与许可证。本 Skill 通过本地 CLI 和结果文件集成，不捆绑模型权重。

`pipeline` 支持 CPU，首轮需要下载解析模型并占用较多磁盘和内存。先检查现有运行环境、可用空间与模型缓存；具体依赖以 [官方安装说明](https://opendatalab.github.io/MinerU/quick_start/) 为准。长时间运行时将日志写入工作目录并报告进度。不要把执行超时当成模型仍在后台正常运行。

使用 `-b pipeline`，不配置云 API 地址或调用 `mineru-open-api`。本地文档处理不需要 MinerU Token 或 LLM API Key。这里的“本地”指解析；Codex 翻译仍由当前已登录会话的模型完成。

## 导入

寻找本次输入对应的 `*_content_list.json`（不是 `*_content_list_v2.json`）。保留同目录的 `images/`：

```bash
"$PYTHON" "$SCRIPT" prepare /path/paper.pdf --job "$JOB" \
  --mineru-json /path/mineru-output/paper/auto/paper_content_list.json
```

不要假设 MinerU 输出子目录固定；以实际生成路径为准。多个候选时根据文件名、页数和原页内容确定同一论文同一版本。

适配器读取官方稳定的扁平 content_list：按 `page_idx` 保持页码和块顺序，支持正文/标题、公式、图片/chart、表格、列表、代码和页面辅助文字。图注、表注、表格单元文字可翻译；数学式、图片路径、代码和 HTML 表格标签以标记保护。原 JSON 和图片复制到任务目录，译文 Markdown 带可用本地图片链接。

未知类型、缺少图片或越界页码会报错，不能静默丢块。新版本只提供 V2 时先适配其实际 schema，或导出同版本仍提供的 legacy content_list。V2 与 V1 不是相同数据格式，不能重命名冒充。

分块、accept、续译和 assemble 与常规流程一致。MinerU 的识别结果仍需对照原页，尤其是复杂公式和合并表格单元。发现 OCR 错误时，在独立解析结果副本中修正，再新建翻译任务；不改变已有断点的源文。

如果 MinerU 在当前环境无法运行，说明具体原因并使用 PyMuPDF + Codex 逐页视觉校对；交付报告标明实际解析器。

依据：[官方输出格式](https://opendatalab.github.io/MinerU/reference/output_files/)、[CLI 用法](https://github.com/opendatalab/MinerU/blob/master/docs/en/usage/quick_usage.md)。
