# 学生提交指南

请在提交作业前仔细阅读本文档。如有疑问，请在 [Discussions · Q&A](../../discussions) 提问。

---

## 一、文件夹命名规范

你们小组的文件夹放在对应学年目录下，格式：

```
submissions/{学年}/T{话题编号}-G{小组编号}-{简短主题}/
```

示例：
```
submissions/2026/T01-G03-资产定价/
submissions/2026/T02-G01-波动率预测/
```

规则：
- 话题和小组编号均用两位数字：`T01`、`G03`
- 简短主题不超过 10 个字，中英文均可
- **文件夹名一经确定请勿修改**，否则会导致历史记录断裂
- 路径中只使用**正斜杠 `/`**，不要使用反斜杠 `\`（即使你用的是 Windows）

---

## 二、文件夹内容要求

```
T01-G03-资产定价/
├── README.md          ← 必须，格式见下方
├── report.pdf         ← 报告正文
├── code/
│   ├── main.ipynb     ← 主分析代码
│   └── utils.py       ← 辅助函数（如有）
└── data/
    ├── README.md      ← 数据说明（必须，格式见下方）
    └── sample.parquet ← 小文件数据（<10MB 可直接放入）
```

### README.md 模板

```markdown
# T01-G03 · 资产定价

## 小组信息

| 姓名 | 学号 | 分工 |
|------|------|------|
| 张三 | 2024001 | 数据处理、建模 |
| 李四 | 2024002 | 文献综述、报告撰写 |

## 作业摘要

（100–300 字，说明研究问题、数据、方法和主要结论）

## 文件说明

- `report.pdf`：正式报告
- `code/main.ipynb`：主要分析代码
- `data/`：详见 data/README.md

## 运行环境

Python 3.11，主要依赖：pandas、numpy、torch
安装：`pip install -r requirements.txt`
运行：`jupyter notebook code/main.ipynb`
```

### data/README.md 模板

```markdown
# 数据说明

## 数据来源

| 数据集 | 来源 | 时间范围 | 获取方式 |
|--------|------|----------|----------|
| 股票日收益率 | CSMAR | 2015-2023 | 需校园账号登录下载 |
| 无风险利率 | Wind | 2015-2023 | 需 Wind 客户端 |

## 数据文件

| 文件名 | 说明 | 大小 | 获取方式 |
|--------|------|------|----------|
| stock_returns.parquet | 个股日收益率 | 45MB | 见下方下载脚本 |
| risk_free_rate.csv | 无风险利率 | 0.2MB | 已包含在仓库中 |

## 下载说明

运行 `python data/download_data.py` 可自动下载所有大文件数据。
（数据文件存储在本仓库的 GitHub Release 中，无需登录，国内可正常访问）
```

---

## 三、大文件处理规范

> ⚠️ **GitHub 单文件上限 100MB，超出会推送失败。建议单文件控制在 50MB 以内。**  
> 已推入的大文件很难清除，请务必在推送前处理好。

### 判断与处理方式

| 文件大小 | 推荐处理方式 |
|----------|-------------|
| < 10MB | 直接放入仓库 |
| 10MB – 50MB | 转为 Parquet 后放入仓库（通常可缩小 5–10 倍） |
| > 50MB | 上传到 GitHub Release，仓库中只放下载脚本 |
| 付费数据库数据 | **禁止直接上传**，无论大小，见第 3.3 节 |

### 3.1 CSV 转 Parquet（推荐首选）

Parquet 是列式存储格式，同样数据通常比 CSV 小 **5–10 倍**，读取速度也更快。

```python
import pandas as pd

# 一行代码转换
df = pd.read_csv("data/stock_prices.csv")
df.to_parquet("data/stock_prices.parquet", index=False)

# 读取时
df = pd.read_parquet("data/stock_prices.parquet")
```

> 首次使用需安装：`pip install pyarrow`

### 3.2 使用 GitHub Release 存储大文件（推荐，国内无限速）

GitHub Release 是 GitHub 自带的文件发布功能，单文件上限 2GB，下载无需登录、国内访问稳定无限速，是最适合本课程的大文件解决方案。

**上传步骤（在你自己的 Fork 仓库中操作）：**

1. 进入你 Fork 后的仓库主页
2. 点击右侧 **Releases → Create a new release**
3. Tag 填写 `data-2026-T01-G03`（方便识别）
4. 标题填写 `T01-G03 数据文件`
5. 将数据文件**拖拽**到 "Attach binaries" 区域上传
6. 点击 **Publish release**
7. 上传完成后，右键点击文件名 → **复制链接地址**，格式如：  
   `https://github.com/你的账号/dsfin-hw/releases/download/data-2026-T01-G03/stock_prices.parquet`

**在仓库中提供下载脚本（`data/download_data.py`）：**

```python
"""
运行本脚本可自动下载所需数据文件。
数据存储在 GitHub Release 中，国内可直接访问，无需登录。
"""
import urllib.request
from pathlib import Path

# ── 在此处填写你们的文件下载链接 ──────────────────────────────────
FILES = {
    "data/stock_prices.parquet": (
        "https://github.com/你的账号/dsfin-hw/releases/download"
        "/data-2026-T01-G03/stock_prices.parquet"
    ),
    # 如有多个文件，继续添加：
    # "data/macro_data.parquet": "https://...",
}
# ──────────────────────────────────────────────────────────────────

def download():
    for local_path, url in FILES.items():
        path = Path(local_path)
        if path.exists():
            print(f"已存在，跳过：{local_path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"正在下载 {path.name} ...")
        urllib.request.urlretrieve(url, path)
        print(f"  ✅ 已保存到 {local_path}")

if __name__ == "__main__":
    download()
    print("\n所有数据文件下载完成。")
```

其他可用的网盘（次选）：

| 方案 | 国内速度 | 脚本下载 | 说明 |
|------|----------|----------|------|
| GitHub Release | ✅ 稳定 | ✅ 有稳定直链 | **首选** |
| 坚果云 | ✅ 快 | ✅ WebDAV 协议 | 学术圈常用，免费版月流量够用，见下方脚本 |
| OneDrive 教育版 | ✅ 较快 | ✅ 可生成直链 | 学校提供 365 账号的同学可用 |
| 阿里云 OSS | ✅ 快 | ✅ 有直链 | 有免费额度，配置略复杂 |
| 夸克网盘 | ✅ 目前不限速 | ❌ 无稳定直链 | 只能手动下载 |
| 百度网盘 | ❌ 非会员限速 | ❌ 无直链 | 不推荐 |
| Google Drive | ❌ 国内受限 | ✅ 有直链 | 需代理，不推荐 |

**坚果云 WebDAV 下载脚本：**

坚果云支持 WebDAV 协议，可直接用 Python 标准库下载，无需安装额外 SDK。

使用前准备：
1. 登录坚果云网页版 → 右上角账号名 → **账户信息 → 安全选项 → 第三方应用管理**
2. 点击"添加应用"，生成一个**应用密码**（不是登录密码）
3. 将数据文件上传到坚果云的某个文件夹，记录文件路径

```python
# 坚果云 WebDAV 下载示例
# 需要：pip install requests（通常已预装）
import requests
from pathlib import Path

WEBDAV_BASE = "https://dav.jianguoyun.com/dav/"
USERNAME = "你的坚果云注册邮箱"
APP_PASSWORD = "应用密码（非登录密码）"  # 建议通过环境变量传入

FILES = {
    "data/stock_prices.parquet": "你的坚果云文件夹名/stock_prices.parquet",
}

def download():
    for local_path, remote_path in FILES.items():
        path = Path(local_path)
        if path.exists():
            print(f"已存在，跳过：{local_path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        url = WEBDAV_BASE + remote_path
        print(f"正在从坚果云下载 {path.name} ...")
        resp = requests.get(url, auth=(USERNAME, APP_PASSWORD), stream=True)
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  ✅ 已保存：{local_path}")

if __name__ == "__main__":
    download()
```

> ⚠️ **安全提示**：请勿将用户名和应用密码直接写进提交到仓库的脚本中。  
> 建议改为从环境变量读取：`USERNAME = os.environ.get("JGY_USER")`

### 3.3 付费数据库数据（Wind、Bloomberg、CSMAR 等）

> ⚠️ 付费数据库的数据有版权限制，**严禁上传到公开仓库，无论文件大小**。

正确做法：
- 在 `data/README.md` 中说明数据库名称、查询条件、时间范围、下载步骤
- 代码中写好读取接口，注释掉实际路径，改为说明性占位符
- 如果有公开替代数据源（如 AkShare、Tushare 免费接口），额外提供备用获取方式

---

## 四、提交流程

> 每组**指定一名同学**负责 GitHub 操作，使用固定账号，**中途不要换账号**。

---

### 方式 A：GitHub Desktop（推荐新手使用）

**前提：已安装 [GitHub Desktop](https://desktop.github.com/) 并登录你的 GitHub 账号。**

#### 第一次提交（完整流程）

**步骤 1：Fork 本仓库**

在浏览器中打开本仓库页面，点击右上角 **Fork → Create fork**。

**步骤 2：Clone 到本地**

1. 打开 GitHub Desktop
2. 菜单 **File → Clone repository**
3. 选择 **GitHub.com** 标签页，找到你刚 Fork 的 `dsfin-hw`
4. 选择本地保存路径，点击 **Clone**

**步骤 3：创建你们小组的文件夹**

用文件管理器（Windows 资源管理器 / Mac Finder）在 Clone 下来的仓库目录中手动创建文件夹：

```
（仓库根目录）/submissions/2026/T01-G03-资产定价/
```

将作业文件（README.md、report.pdf、code/、data/ 等）放入该文件夹。

**步骤 4：在 GitHub Desktop 中提交**

1. 打开 GitHub Desktop，左侧 Changes 面板会显示所有新增文件
2. 勾选所有文件（默认全选）
3. 左下角填写 Summary（必填）：`feat: 提交T01-G03第一版作业`
4. 点击蓝色 **Commit to main** 按钮

**步骤 5：推送到 GitHub**

点击顶部工具栏的 **Push origin** 按钮（或 **Publish branch**）。

**步骤 6：发起 Pull Request**

1. GitHub Desktop 顶部会出现提示横幅，点击 **Create Pull Request**（或在浏览器中打开你的 Fork 仓库，点击 **Contribute → Open pull request**）
2. **PR 标题格式（重要）**：`[2026/T01-G03] 资产定价 · 第一次提交`
3. 按模板填写描述，勾选所有声明项
4. 点击 **Create pull request**，等待教师或助教审核

#### 后续提交

首次 PR 合并后，后续更新：

1. 用文件管理器修改或新增文件
2. GitHub Desktop 左侧会显示变更，填写 Summary 后 **Commit to main**
3. 点击 **Push origin**，系统自动同步，**无需再次发起 PR**

#### 同步主仓库最新内容（如遇合并冲突时）

1. GitHub Desktop 菜单 **Branch → Update from upstream** （或 **Merge into current branch**）
2. 如果没有该选项，点击 **Fetch origin** 后再操作
3. 如有冲突会提示，按提示解决后重新 Commit

---

### 方式 B：命令行（熟悉 Git 的同学）

#### 第一次提交

```bash
# 1. Clone 你 Fork 后的仓库
git clone https://github.com/你的用户名/dsfin-hw.git
cd dsfin-hw

# 2. 添加上游仓库（用于后续同步）
git remote add upstream https://github.com/lianxhcn/dsfin-hw.git

# 3. 创建文件夹，放入作业文件
mkdir -p submissions/2026/T01-G03-资产定价

# 4. 提交
git add submissions/2026/T01-G03-资产定价/
git commit -m "feat(T01-G03): 提交第一版作业"
git push origin main
```

然后在 GitHub 网页上发起 Pull Request，标题格式：`[2026/T01-G03] 资产定价 · 第一次提交`

#### 后续提交

```bash
git add .
git commit -m "fix(T01-G03): 修正第3章数据处理错误"
git push origin main
# 无需再次发起 PR
```

#### 同步主仓库最新内容

```bash
git fetch upstream
git merge upstream/main
git push origin main
```

---

## 五、Quarto + GitHub Pages 型作业

如果你们的作业要求使用 Quarto 发布为网站，请按以下方式处理：

**步骤 1：自建仓库并发布**

在你们的账号下新建仓库，编写 Quarto 项目，发布到 GitHub Pages。  
发布地址格式：`https://{你的账号}.github.io/{仓库名}/`

**步骤 2：在本仓库登记网址**

在 `submissions/2026/T01-G03-资产定价/README.md` 中填写：

```markdown
# T01-G03 · 资产定价

## 作业网址

🌐 **发布地址**：https://your-account.github.io/your-repo/
📦 **源码仓库**：https://github.com/your-account/your-repo

## 小组信息
...
```

**步骤 3：确保教师可以访问源码**

- 源码仓库设为 **Public**，无需额外操作
- 源码仓库为 **Private** 时，请将 `lianxhcn` 添加为 Collaborator（`Settings → Collaborators`）

---

## 六、学术诚信声明

提交作业即视为全体组员声明：
1. 本作业内容为本组原创，未抄袭其他小组的作业
2. 使用 AI 工具（如 ChatGPT、Claude）的部分已在报告中注明
3. 引用的文献、代码、数据均已注明来源

---

## 七、常见问题

**Q：推送时提示"文件过大"？**  
A：参考第三节处理大文件。如果文件已经 add 进去了，先运行 `git rm --cached 文件路径` 从暂存区移除，再重新提交。

**Q：GitHub Desktop 看不到 "Update from upstream" 选项？**  
A：菜单 **Branch → Compare to branch**，选 `upstream/main`，然后 **Merge**。

**Q：PR 标题格式错了，系统报错怎么办？**  
A：直接在 PR 页面点击标题旁边的铅笔图标修改标题，保存后系统会自动重新检查。

**Q：不小心把大文件推进去了怎么办？**  
A：**立刻联系教师或助教，不要继续推送任何内容。** 大文件一旦进入 Git 历史很难完全清除，需要由管理员处理。

**Q：Fork 仓库和主仓库有什么区别？**  
A：Fork 是你账号下的独立副本，你在上面的操作不影响主仓库。发起 PR 是向主仓库提交合并请求，教师审核通过后你的内容才会出现在主仓库中。
