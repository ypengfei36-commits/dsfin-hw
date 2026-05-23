"""
将 report.md 转换为 HTML 和 PDF
使用方法：在 VS Code 终端运行：python convert_report.py
"""

import re

# 读取 markdown 文件
input_file = r"C:\Users\35769\Documents\xwechat_files\wxid_erk0r370hmok12_0394\msg\file\2026-05\数据分析第二次小组作业\report.md"
output_html = r"C:\Users\35769\Documents\xwechat_files\wxid_erk0r370hmok12_0394\msg\file\2026-05\数据分析第二次小组作业\report.html"
output_pdf  = r"C:\Users\35769\Documents\xwechat_files\wxid_erk0r370hmok12_0394\msg\file\2026-05\数据分析第二次小组作业\report.pdf"

with open(input_file, 'r', encoding='utf-8') as f:
    md_content = f.read()

print(f"读取文件成功，共 {len(md_content)} 字符")

# ============================================================
# 简单的 Markdown → HTML 转换（无需第三方库）
# ============================================================

def md_to_html(md):
    lines = md.split('\n')
    html_lines = []
    in_code_block = False
    in_table = False
    table_rows = []
    i = 0

    def escape(s):
        return (s.replace('&', '&amp;')
                 .replace('<', '&lt;')
                 .replace('>', '&gt;'))

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith('```'):
            if not in_code_block:
                in_code_block = True
                lang = line.strip()[3:]
                html_lines.append(f'<pre><code class="language-{lang}">')
            else:
                in_code_block = False
                html_lines.append('</code></pre>')
            i += 1
            continue
        if in_code_block:
            html_lines.append(escape(line))
            i += 1
            continue

        # 标题
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            html_lines.append(f'<h{level}>{text}</h{level}>')
            i += 1
            continue

        # 分割线
        if re.match(r'^---+ *$', line):
            html_lines.append('<hr>')
            i += 1
            continue

        # 表格（收集所有连续行）
        if '|' in line and line.strip().startswith('|'):
            table_rows.append(line)
            # 看下一行是不是分隔符
            if i + 1 < len(lines) and re.match(r'^\|[-: |]+\|', lines[i+1]):
                table_rows.append(lines[i+1])  # 加入分隔行
                i += 1
                # 继续收集后续表格行直到非表格行
                while i + 1 < len(lines) and '|' in lines[i+1] and lines[i+1].strip().startswith('|'):
                    i += 1
                    table_rows.append(lines[i])
                # 解析表格
                html_lines.append('<table class="md-table">')
                # 表头
                header_cells = [c.strip() for c in table_rows[0].split('|')[1:-1]]
                html_lines.append('  <thead><tr>')
                for cell in header_cells:
                    html_lines.append(f'    <th>{cell}</th>')
                html_lines.append('  </tr></thead>')
                # 表体（跳过表头行和分隔行）
                body_rows = table_rows[2:]
                html_lines.append('  <tbody>')
                for row in body_rows:
                    cells = [c.strip() for c in row.split('|')[1:-1]]
                    html_lines.append('  <tr>')
                    for cell in cells:
                        html_lines.append(f'    <td>{cell}</td>')
                    html_lines.append('  </tr>')
                html_lines.append('  </tbody>')
                html_lines.append('</table>')
                table_rows = []
            i += 1
            continue

        # 图片
        m = re.match(r'^!\[(.*?)\]\((.*?)\)', line)
        if m:
            alt, src = m.group(1), m.group(2)
            html_lines.append(f'<img src="{src}" alt="{alt}" class="md-img">')
            i += 1
            continue

        # 引用
        if line.strip().startswith('>'):
            content = line.lstrip('> ').strip()
            html_lines.append(f'<blockquote>{content}</blockquote>')
            i += 1
            continue

        # 无序列表
        if re.match(r'^[-*]\s+', line):
            content = line[2:].strip()
            html_lines.append(f'<li>{content}</li>')
            i += 1
            continue

        # 普通段落
        if line.strip() == '':
            html_lines.append('<br>')
            i += 1
            continue

        # 行内代码
        line = re.sub(r'`([^`]+)`', r'<code>\1</code>', line)
        # 加粗
        line = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', line)
        # 链接
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', line)

        html_lines.append(f'<p>{line}</p>')
        i += 1

    return '\n'.join(html_lines)


html_body = md_to_html(md_content)

# HTML 模板
html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>券商金股研究报告</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", Arial, sans-serif;
         font-size: 15px; line-height: 1.8; color: #1a1a2e; background: #f9f9f9;
         padding: 40px 60px; max-width: 1100px; margin: 0 auto; }}
  h1 {{ font-size: 2em; color: #1F4E79; margin: 1.5em 0 0.5em; border-bottom: 3px solid #1F4E79;
        padding-bottom: 0.3em; }}
  h2 {{ font-size: 1.4em; color: #2c7ab8; margin: 1.2em 0 0.4em; padding-left: 0.5em;
        border-left: 4px solid #2c7ab8; }}
  h3 {{ font-size: 1.1em; color: #444; margin: 1em 0 0.3em; }}
  p {{ margin: 0.6em 0; }}
  blockquote {{ background: #eef4fb; border-left: 4px solid #1F4E79; padding: 10px 16px;
               margin: 1em 0; border-radius: 4px; font-style: italic; color: #334; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  pre {{ background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 6px; overflow-x: auto;
         margin: 1em 0; }}
  pre code {{ background: none; padding: 0; color: inherit; font-size: 0.88em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em;
          box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
  th {{ background: #1F4E79; color: white; padding: 8px 12px; text-align: left; }}
  td {{ padding: 7px 12px; border-bottom: 1px solid #e0e0e0; }}
  tr:nth-child(even) {{ background: #f4f8fc; }}
  tr:hover {{ background: #e8f4fb; }}
  .md-img {{ max-width: 100%; border-radius: 6px; box-shadow: 0 2px 12px rgba(0,0,0,0.15);
            display: block; margin: 1em auto; }}
  a {{ color: #1F4E79; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  hr {{ border: none; border-top: 2px solid #1F4E79; margin: 2em 0; opacity: 0.3; }}
  li {{ margin: 0.3em 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>'''

# 保存 HTML
with open(output_html, 'w', encoding='utf-8') as f:
    f.write(html_template)
print(f"✅ HTML 已保存：{output_html}")

# ============================================================
# 转换为 PDF（用 weasyprint）
# ============================================================
try:
    from weasyprint import HTML as WPHTML
    print("正在生成 PDF（需要约30秒）...")
    WPHTML(filename=output_html).write_pdf(output_pdf)
    print(f"✅ PDF 已保存：{output_pdf}")
except ImportError:
    print("⚠️ weasyprint 未安装，正在安装...")
    import subprocess
    subprocess.run(['pip', 'install', 'weasyprint'], check=True)
    from weasyprint import HTML as WPHTML
    WPHTML(filename=output_html).write_pdf(output_pdf)
    print(f"✅ PDF 已保存：{output_pdf}")
except Exception as e:
    print(f"⚠️ PDF 生成失败：{e}")
    print("请在 VS Code 终端手动运行以下命令安装 weasyprint 后重新执行本脚本：")
    print("  pip install weasyprint")
    print("  python convert_report.py")