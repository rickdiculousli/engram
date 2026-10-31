"""YAML frontmatter, read as strings only so tickers, dates and prices keep their text."""
import yaml


def split(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return None, text
    fields = yaml.load(text[4:end], Loader=yaml.BaseLoader) or {}
    if not isinstance(fields, dict):
        raise ValueError("frontmatter is not a mapping")
    return fields, text[end + 5:]


def _scalar(v: str) -> str:
    if v == "" or v != v.strip() or any(c in v for c in ":#[]{},&*!|>'\"%@`") or v.lower() in ("null", "~"):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return v


def dump(fields: dict) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(_scalar(str(x)) for x in v)}]")
        else:
            lines.append(f"{k}: {_scalar(str(v))}")
    lines.append("---")
    return "\n".join(lines) + "\n"
