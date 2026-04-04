# 教师操作手册

---

## 一、建仓后的必要设置（只需做一次）

### 1. Branch Protection

`Settings → Branches → Add rule`，Branch name pattern 填 `main`：

- ✅ Require a pull request before merging
- ✅ Require approvals：1
- ✅ Require review from Code Owners
- ✅ Allow auto-merge
- ❌ 不勾选 "Restrict who can push"（Actions 需要写权限）

### 2. Actions 写权限

`Settings → Actions → General → Workflow permissions` → **Read and write permissions**

### 3. 启用 Discussions

`Settings → General → Features → Discussions`，建议创建：
- `📣 公告`（仅 maintainer 可发，用于通知学生）
- `❓ Q&A`
- `💬 作业交流`

### 4. 添加助教为 Collaborator

`Settings → Collaborators → Add people`，赋予权限：

| 权限 | 能做什么 | 适合谁 |
|------|----------|--------|
| **Triage** | 管理 Issues/PR（评论、打 label），不能合并 | 一般助教 |
| **Write** | 可以合并 PR | 主助教 |

添加后同步更新 `.github/CODEOWNERS`：

```
* @lianxhcn @助教账号
```

---

## 二、每学年开学时

1. 在 `submissions/` 下创建新年份文件夹（如 `submissions/2027/`），并放一个空的 `.gitkeep` 文件
2. 通知每组：**指定一名同学**作为固定提交账号，中途不换
3. 记录各组提交账号与文件夹名的对应关系（私有文档或 Wiki）

---

## 三、日常操作

### 处理首次 PR

Action 会留言"新小组首次提交，等待教师或助教审核"，操作：

1. 点击 **Files changed** 检查：命名规范、README 完整性、是否有大文件、是否只改了本组文件夹
2. 如有问题：**Review → Request changes**，说明修改要求
3. 确认无误：**Merge pull request → Squash and merge**

### 评阅作业

- **Files changed**：对具体行添加行内评论
- **Review summary**：写整体评语
- 已合并的 PR 也可以在对应 commit 上继续留评论

### 学期结束归档

1. 创建 Release Tag，如 `2026-final`，描述本学期基本情况
2. 在 Discussions 公告分类发消息，告知学生本学期作业已归档

---

## 四、安全与风险处理

### Action 三道防线

| 检查项 | 不通过时的处理 |
|--------|---------------|
| PR 标题格式 `[年份/T??-G??]` | 阻止处理，留评论要求修改 |
| 文件在 `submissions/年份/` 以外 | 阻止合并，通知教师 |
| 文件夹不含本组编号 | 阻止合并，通知教师 |

### 恢复被误删或误覆盖的文件

Git 有完整历史，任何操作都可以恢复：

```bash
# 找到该文件最后一次正常的 commit
git log --all -- submissions/2026/T01-G01-被误操作组/

# 恢复
git checkout <commit_hash> -- submissions/2026/T01-G01-被误操作组/
git commit -m "fix: 恢复 T01-G01 文件"
git push
```

### 处理被推入的大文件

**发现后立即处理，不要再合并任何 PR：**

```bash
pip install git-filter-repo
git filter-repo --path submissions/2026/T??-G??/大文件名 --invert-paths
git push --force
```

---

## 五、关于 Branch 的说明

**你的日常操作完全不涉及 Branch。**

整个工作流只用 `main` 一个分支，学生在自己 Fork 里操作，你在 PR 页面合并即可。年份隔离通过 `submissions/年份/` 文件夹实现，不需要创建额外分支。
