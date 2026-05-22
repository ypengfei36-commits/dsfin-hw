# Team02-G01：广州市海珠区未来房价走势与购房时机判断

## 小组成员

| 姓名 | 学号 | 分工 |
| ---- | ------- | ------------------ |
| 龙昊文 | 25210204 | 数据处理（宏观与城市层面数据获取、清洗） |
| 潘福璋 | 25210218 | 数据处理（平台挂牌数据爬取、清洗与整合） |
| 沈婷婷 | 25210230 | 数据分析（价格指数走势与一线城市对比） |
| 张梦洁 | 25210299 | 数据分析（政策时间线梳理与决策建议撰写） |
| 吴小飞 | 25210261 | 数据分析（官方成交热度分析与保利海韵案例） |
| 高一婷 | 25210134 | 数据分析（支付能力测算、月供收入比热力图） |
| 许博东 | 25210269 | 检查与提交（报告审核、GitHub 提交流程） |
| 张璇 | 25210303 | 检查与提交（报告审核、GitHub 提交流程） |

## 决策主体与选题摘要

本报告面向**计划在广州市海珠区购房的自住型刚需与改善型消费者**，围绕"2026 年是否适合在海珠区买房"这一核心决策问题展开。报告从政策环境、价格指数走势、市场成交热度、典型楼盘案例和居民支付能力五个维度进行分析，帮助消费者判断当前购房时机。初步结论是：海珠区优质新盘热度上升，但并不等同于全区房价普涨；自住需求明确、现金流稳定的消费者可重点关注核心地段项目，投资型或预算紧张的购房者应保持谨慎。

## 文件说明

| 文件 | 说明 |
| ---- | ---- |
| `report.md` | 分析报告（Markdown 格式，含图表说明与决策建议） |
| `report.pdf` | 分析报告 PDF 导出版 |
| `output/report.html` | 分析报告 HTML 导出版（含所有图表） |
| `slides.md` | Marp 幻灯片源文件 |
| `output/slides.pdf` | 幻灯片 PDF 导出版 |
| `codes/` | 全部分析代码（Python 脚本，按步骤编号） |
| `data/raw/` | 原始数据文件（链家/贝壳用户补充 CSV、政策时间线等） |
| `data/clean/` | 清洗后数据文件 |
| `output/` | 图表输出文件（fig01–fig14）及报告导出版本 |

> **数据来源说明**：宏观数据来自国家统计局/AkShare（可公开复现）；官方成交数据来自广州市住建局及广州市房地产中介协会公开接口；平台挂牌样本来自房天下公开列表（120条）及小组手动补充的链家/贝壳 CSV（共61条），均为公开挂牌价/参考价，非网签成交价。

## 项目概览

```
Team02-G01-HaizhuHousing/
├── README.md                  ← 本文件
├── report.md                  ← 分析报告
├── report.pdf                 ← 报告 PDF
├── slides.md                  ← Marp 幻灯片源文件
├── codes/                     ← 分析代码
│   ├── 01_get_data_akshare.py
│   ├── 02_make_initial_charts.py
│   ├── 03_scrape_public_listing_pages.py
│   ├── 04_make_listing_charts.py
│   ├── 05_affordability_and_policy.py
│   ├── 06_render_report_html.py
│   ├── 07_official_sales_and_poly_news.py
│   ├── 08_gzrea_secondhand_weekly.py
│   └── 09_integrate_user_house_data.py
├── data/
│   ├── raw/                   ← 原始数据
│   └── clean/                 ← 清洗后数据
└── output/                    ← 图表与报告导出
    ├── fig01_guangzhou_price_index.png
    ├── ...
    ├── fig14_user_house_sample_comparison.png
    ├── report.html
    └── slides.pdf
```
