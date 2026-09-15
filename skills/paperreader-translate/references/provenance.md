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
