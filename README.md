# PaperReader.skill — Codex 论文翻译

将 PaperReader 的论文翻译流程制作成独立 Codex Skill。翻译由当前 Codex 会话完成，本地脚本负责解析、保护公式、保存进度与导出，不调用 LLM API 或 MinerU 云 API。

## 安装与使用

将本仓库 `skills/paperreader-translate` 整个文件夹复制到本机 Codex 的用户技能目录（当前官方路径为 `~/.agents/skills/`；使用 `~/.codex/skills/` 的环境可放入其现有技能目录）。重新打开会话后调用：

```text
$paperreader-translate 把这篇论文完整翻译成中文，保留公式和图表，生成中文 PDF。
```

支持本地 PDF、单个 TeX、包含 input/include 的工程和 ZIP/TAR 源码包。链接由 Codex 下载后处理；arXiv 优先使用同版本源码。长论文逐块保存，可在下一会话继续。

- **TeX 源码**：保留工程目录、公式、引用和图片，翻译后编译中文 PDF。
- **只有 PDF**：优先使用开源 MinerU 本地解析公式、版面和图表，再逐页校对，导出 Markdown 和离线双语 HTML，由 Codex 制作中文重排 PDF。
- **依赖**：Python 3.10+；本地结构解析使用 MinerU pipeline，页图与轻量解析使用 PyMuPDF；PDF 编译需要 XeLaTeX。无需启动原软件。

使用 ChatGPT 登录 Codex 可使用订阅访问；Skill 不改变账户的额度或计费方式，API Key 登录仍按 API 方式计费。参见 [官方认证说明](https://developers.openai.com/codex/auth) 和 [Skill 文档](https://developers.openai.com/codex/skills)。

## 能力边界

PDF 文本提取不能保证双栏阅读顺序、扫描识别和数学结构完整，须按原页图校对；重排版不承诺原版式复刻。TeX 自定义宏和期刊模板可能需要适配。脚本能校验保护标记和块覆盖，语义准确性由 Codex 对照原文检查。完整流程见 [SKILL.md](skills/paperreader-translate/SKILL.md)。

## 开发验证

```bash
python3 -m unittest discover -s tests/skill -v
```

PDF 测试需要先在虚拟环境安装 `skills/paperreader-translate/scripts/requirements.txt`。CLI 的 prepare/next/accept/assemble/compile 用法见 Skill 附带参考文件。

改编自同学的 [Mars-Dingdang/PaperReader](https://github.com/Mars-Dingdang/PaperReader)，委托人确认已获得作者授权。改编范围与来源见 [provenance.md](skills/paperreader-translate/references/provenance.md)。本仓库仅发布独立 Skill，原应用源码可在上游仓库及本 Fork 的历史提交中查阅。


## 仓库结构

```text
skills/paperreader-translate/
  SKILL.md
  agents/openai.yaml
  scripts/
  references/
tests/skill/
```

MinerU 本地环境和导入命令见 [MinerU 流程](skills/paperreader-translate/references/mineru.md)。本地解析不需要 MinerU 云 API Key；翻译由当前 Codex 会话完成。
