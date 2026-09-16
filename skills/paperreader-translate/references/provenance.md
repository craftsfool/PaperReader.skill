# 来源与实现范围

上游：[Mars-Dingdang/PaperReader](https://github.com/Mars-Dingdang/PaperReader)。
Fork：[craftsfool/PaperReader.skill](https://github.com/craftsfool/PaperReader.skill)。
参考版本：Fork 提交 `ae9d975`，PaperReader v2.1.9。

参考模块：

- `backend/app/services/translate_service.py`：论文级术语表、公式/引用占位保护、分块校验、失败不回填英文、断点续译。
- `backend/app/services/latex_service.py`：多文件 TeX 处理、中文字体与编译检查。
- `backend/app/services/project_archive.py`：论文源码归档输入。

本 Skill 独立实现本地脚本，不导入或运行 FastAPI、LLM 客户端、数据库、MinerU 服务或桌面应用。翻译工作由当前 Codex 会话承担。保留多文件工程目录；PDF 优先导入本地 MinerU 的结构化输出，并可使用 PyMuPDF 文本提取和原页对照，复杂布局由 Codex 视觉校对。

任务委托人说明已取得上游作者授权。本说明记录来源，不代替或扩展作者授权，也不为上游代码另行指定开源许可证。

解析框架：[opendatalab/MinerU](https://github.com/opendatalab/MinerU)，通过 CLI/JSON 适配，不在本 Skill 中复制其代码或权重；使用源码时沿用所用版本的上游许可证。

## 上游更新迁移：v2.1.10–v2.1.12

本次审查范围：`ae9d97586a32` → `2523103833bcdbf06651f43cc38e970bae578856`。

- v2.1.10 / `763d6ffd6443`：参考 `latex_recovery.py` 的最新编译反馈、无行号诊断、导言区与完整环境修复、逐轮备份。独立实现 `build_diagnostics.py` 与 compile/diagnose 集成；修复由当前 Codex 会话完成，没有移植上游的 LLM API 修复循环。
- v2.1.11 / `52fc84af0660`、v2.1.12 / `2523103833bc`：参考 `document_structure.py` 的双 PDF 独立定位、标题优先、图表对象邻近裁剪。独立实现 PyMuPDF 版 `figure_gallery.py`；启发式检测失败时显示整页预览。没有移植桌面浮窗、账户、批注数据库与 API 路由。
- 上述三次提交未修改 `translate_service.py`、`latex_service.py` 或 `project_archive.py`，现有保护标记与翻译断点格式保持兼容。

本次迁移不包含上游 PDF named destinations 裁剪兜底或 TeX 浮动环境自动枚举；具体支持范围与限制见 [图表索引](figures.md)。

验证：20 项单元测试；真实 XeLaTeX 的缺宏包失败→导言区修复→编译通过，确认公式源码与首轮快照未变并渲染检查；DSTAR 原文与现有译文中分别定位 22 幅图、3 张表，并检查预览。复杂图形可回退整页；跨页拆表只索引首次标题，不代表全部表格内容。
