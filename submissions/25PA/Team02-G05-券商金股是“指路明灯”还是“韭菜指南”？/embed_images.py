"""
将 slides.md 中的相对路径图片替换为 base64 内嵌格式
使用方法：在 VS Code 终端运行：python embed_images.py
"""

import base64, os, re

slides_md = r"C:\Users\35769\Documents\xwechat_files\wxid_erk0r370hmok12_0394\msg\file\2026-05\数据分析第二次小组作业\slides.md"
base_dir  = r"C:\Users\35769\Documents\xwechat_files\wxid_erk0r370hmok12_0394\msg\file\2026-05\数据分析第二次小组作业"

with open(slides_md, 'r', encoding='utf-8') as f:
    content = f.read()

def replace_image(match):
    alt = match.group(1)
    rel_path = match.group(2)
    full_path = os.path.join(base_dir, rel_path)
    if not os.path.exists(full_path):
        print(f"  ⚠️  文件不存在: {rel_path}")
        return match.group(0)  # 保留原引用
    with open(full_path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')
    ext = os.path.splitext(rel_path)[1].lower()
    mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
            'gif': 'image/gif', 'webp': 'image/webp'}.get(ext, 'image/png')
    print(f"  ✅ 嵌入: {rel_path} ({os.path.getsize(full_path)//1024}KB)")
    return f'![{alt}](data:{mime};base64,{b64})'

images_found = re.findall(r'!\[(.*?)\]\((.*?)\)', content)
print(f"找到 {len(images_found)} 张图片，开始转换...\n")

new_content = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_image, content)

with open(slides_md, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"\n✅ 完成！所有图片已内嵌到 slides.md")
print("现在用 Marp 导出 PDF，图片即可正常显示")