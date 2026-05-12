from pathlib import Path
import os
import re


config_path = Path(os.environ["HOME"]) / ".codex" / "config.toml"
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    text = config_path.read_text()
else:
    text = ""

text = re.sub(r"(?m)^\s*codex_hooks\s*=\s*(true|false)\s*$", "hooks = true", text)
text = re.sub(r"(?m)^\s*hooks\s*=\s*false\s*$", "hooks = true", text)

if not re.search(r"(?m)^\s*hooks\s*=", text):
    if re.search(r"(?m)^\[features\]\s*$", text):
        text = re.sub(r"(?m)^(\[features\]\s*)$", r"\1\nhooks = true", text, count=1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "\n[features]\nhooks = true\n"

config_path.write_text(text)
