"""Protect non-prose TeX while retaining byte-for-byte reconstruction."""
from __future__ import annotations

import re

TOKEN = re.compile(r"⟦PR\d{6}⟧")
COMMAND = re.compile(r"\\(?:[a-zA-Z@]+\*?|[^a-zA-Z@])")
PROSE = set("title section subsection subsubsection paragraph subparagraph chapter part caption captionof footnote footnotetext emph textbf textit texttt textrm textsf textsc underline mbox thanks abstract shorttitle text superscript subscript".split())
OPAQUE_ENVS = set("equation equation* align align* alignat alignat* gather gather* multline multline* eqnarray eqnarray* math displaymath array matrix pmatrix bmatrix vmatrix Vmatrix smallmatrix split aligned gathered cases tikzpicture verbatim Verbatim lstlisting minted filecontents filecontents* thebibliography".split())


def group_end(text: str, start: int, opening: str = "{", closing: str = "}") -> int:
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "%":
            end = text.find("\n", i)
            i = len(text) if end < 0 else end + 1
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"Unclosed {opening} at character {start}")


def arguments_end(text: str, start: int) -> int:
    end = start
    while True:
        i = end
        while i < len(text) and text[i].isspace():
            i += 1
        if i < len(text) and text[i] in "[{":
            end = group_end(text, i, text[i], "]" if text[i] == "[" else "}")
        else:
            return end


def protect(text: str, extra_prose: tuple[str, ...] = ()) -> tuple[str, dict[str, str]]:
    if TOKEN.search(text):
        raise ValueError("Source contains reserved ⟦PR…⟧ markers")
    mapping: dict[str, str] = {}
    prose = PROSE | set(extra_prose)

    def hold(value: str) -> str:
        token = f"⟦PR{len(mapping):06d}⟧"
        mapping[token] = value
        return token

    def scan(source: str) -> str:
        result: list[str] = []
        i = 0
        while i < len(source):
            char = source[i]
            if char == "%":
                end = source.find("\n", i)
                end = len(source) if end < 0 else end + 1
                result.append(hold(source[i:end]))
                i = end
                continue
            if char == "$" or source.startswith((r"\(", r"\["), i):
                opener = "$$" if source.startswith("$$", i) else char
                if char == "\\":
                    opener = source[i:i + 2]
                closer = {r"\(": r"\)", r"\[": r"\]"}.get(opener, opener)
                end = i + len(opener)
                while end < len(source):
                    if source.startswith(closer, end):
                        break
                    end += 2 if source[end] == "\\" else 1
                if end >= len(source):
                    raise ValueError(f"Unclosed math delimiter at character {i}")
                end += len(closer)
                result.append(hold(source[i:end]))
                i = end
                continue
            if char == "\\":
                match = COMMAND.match(source, i)
                if not match:
                    raise ValueError("Trailing backslash in TeX")
                name = match.group()[1:].rstrip("*")
                end = match.end()
                if name == "verb":
                    if end >= len(source):
                        raise ValueError("Missing verb delimiter")
                    close = source.find(source[end], end + 1)
                    if close < 0:
                        raise ValueError("Unclosed verb")
                    end = close + 1
                elif name == "begin":
                    env_match = re.match(r"\s*\{([^}]+)\}", source[end:])
                    if not env_match:
                        raise ValueError("Missing environment name")
                    env = env_match.group(1)
                    if env in OPAQUE_ENVS:
                        close = re.search(r"\\end\s*\{" + re.escape(env) + r"\}", source[end:])
                        if not close:
                            raise ValueError(f"Unclosed environment: {env}")
                        end += close.end()
                    else:
                        end = arguments_end(source, end)
                elif name == "href":
                    pos = end
                    while pos < len(source) and source[pos].isspace():
                        pos += 1
                    end = group_end(source, pos) if pos < len(source) and source[pos] == "{" else end
                elif name not in prose:
                    end = arguments_end(source, end)
                result.append(hold(source[i:end]))
                i = end
                continue
            url = re.match(r"https?://[^\s{}]+", source[i:]) if source.startswith(("http://", "https://"), i) else None
            if url:
                result.append(hold(url.group()))
                i += len(url.group())
            elif char in "{}&~#_^":
                result.append(hold(char))
                i += 1
            else:
                result.append(char)
                i += 1
        return "".join(result)

    # Keep definitions, author metadata and package options opaque. Titles are prose.
    begin = re.search(r"\\begin\s*\{document\}", strip_comments(text))
    if begin:
        prefix, body = text[:begin.end()], text[begin.end():]
        parts: list[str] = []
        cursor = 0
        for match in re.finditer(r"\\(?:title|shorttitle)\s*(?:\[[^\]]*\]\s*)?\{", strip_comments(prefix)):
            if match.start() < cursor:
                continue
            end = group_end(prefix, match.end() - 1)
            parts.extend([hold(prefix[cursor:match.start()]), scan(prefix[match.start():end])])
            cursor = end
        parts.append(hold(prefix[cursor:]))
        return "".join(parts) + scan(body), mapping
    return scan(text), mapping


def strip_comments(text: str) -> str:
    """Mask comments without changing offsets."""
    return re.sub(r"\\[\s\S]|%[^\n]*", lambda m: " " * len(m.group()) if m.group().startswith("%") else m.group(), text)


def restore(text: str, mapping: dict[str, str]) -> str:
    return TOKEN.sub(lambda match: mapping[match.group()], text)


def chunks(text: str, limit: int = 5000) -> list[str]:
    if limit < 200:
        raise ValueError("Chunk size must be at least 200")
    result = []
    while len(text) > limit:
        cut = text.rfind("\n\n", limit // 2, limit)
        if cut < 0:
            cut = text.rfind("\n", limit // 2, limit)
        if cut < 0:
            cut = text.rfind(" ", limit // 2, limit)
        if cut < 0:
            cut = limit
        else:
            cut += 1
        for match in TOKEN.finditer(text):
            if match.start() < cut < match.end():
                cut = match.start()
                break
            if match.start() >= cut:
                break
        result.append(text[:cut])
        text = text[cut:]
    if text:
        result.append(text)
    return result


def validate(source: str, translated: str, is_tex: bool) -> None:
    if not translated.strip():
        raise ValueError("Empty translation")
    if TOKEN.findall(source) != TOKEN.findall(translated):
        raise ValueError("Protected markers changed, missing, duplicated or reordered")
    if is_tex:
        prose = TOKEN.sub("", translated)
        if re.search(r"[\\{}$%&#_^~]", prose):
            raise ValueError("Translation introduces raw TeX syntax; use prose or existing markers")
        if "```" in translated:
            raise ValueError("TeX translation contains Markdown fences")
