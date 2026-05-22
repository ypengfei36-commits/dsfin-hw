"""Render report.md to a lightweight standalone HTML preview."""

from __future__ import annotations

from pathlib import Path

import mistune


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    markdown = mistune.create_markdown(plugins=["table", "strikethrough"])
    body = markdown((ROOT / "report.md").read_text(encoding="utf-8"))
    body = body.replace('src="output/', 'src="')
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>广州市海珠区未来房价走势与消费者购房时机判断</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", sans-serif; line-height: 1.75; color: #263238; margin: 0; background: #f6f7f9; }}
main {{ max-width: 980px; margin: 0 auto; padding: 42px 52px; background: #fff; }}
h1, h2, h3 {{ color: #1f3d5a; line-height: 1.35; }}
h1 {{ font-size: 30px; border-bottom: 2px solid #1f3d5a; padding-bottom: 14px; }}
h2 {{ margin-top: 34px; font-size: 23px; }}
h3 {{ margin-top: 24px; font-size: 18px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 14px; }}
th, td {{ border: 1px solid #d8dee6; padding: 8px 10px; text-align: left; vertical-align: top; }}
th {{ background: #eef3f8; }}
img {{ max-width: 100%; display: block; margin: 16px auto; border: 1px solid #e1e5ea; }}
blockquote {{ border-left: 4px solid #8aa4bf; padding-left: 14px; color: #53616f; }}
code {{ background: #f1f3f5; padding: 2px 4px; border-radius: 3px; }}
</style>
</head>
<body><main>{body}</main></body>
</html>
"""
    (ROOT / "output" / "report.html").write_text(html, encoding="utf-8")
    print(ROOT / "output" / "report.html")


if __name__ == "__main__":
    main()
