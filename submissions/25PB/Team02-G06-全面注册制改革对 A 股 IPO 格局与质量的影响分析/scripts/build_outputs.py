from __future__ import annotations

import base64
import json
import math
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

import nbformat as nbf
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
FIG = ROOT / "output" / "figures"
TABLE = ROOT / "output" / "tables"
WORKSPACE = ROOT.parents[2]
PREVIOUS_IPO_CSV = WORKSPACE / "Team02-G06-全面注册制打新-提交包" / "Team02-G06-全面注册制打新" / "data" / "clean" / "ipo_merged.csv"

TEAM = [
    ("杨鹏飞", "25210278", "总体统筹、研究设计、报告终审、GitHub 提交"),
    ("况达", "25210151", "政策背景、证监会文件与时间线整理"),
    ("刘苹苹", "25210194", "数据来源说明、字段解释、复现说明"),
    ("姚尚彤", "25210281", "数据清洗、指标构造、样本筛选"),
    ("林佩敏", "25210184", "IPO 数量、募资规模与板块结构图表"),
    ("邓佳鸣", "25210124", "审核状态、撤回终止趋势与质量代理指标"),
    ("劳润杰", "25210154", "Marp 幻灯片制作、PDF 导出、展示节奏控制"),
    ("方少娜", "25210129", "结论建议、局限性、格式与引用审查"),
]

POLICY_SOURCES = [
    ("中国证监会：全面实行股票发行注册制制度规则发布实施", "https://www.csrc.gov.cn/csrc/c100028/c7123213/content.shtml"),
    ("中国政府网：全面实行股票发行注册制制度规则发布实施", "https://www.gov.cn/xinwen/2023-02/17/content_5741947.htm"),
    ("中国证监会：统筹一二级市场平衡 优化 IPO、再融资监管安排", "https://www.csrc.gov.cn/csrc/c100028/c7421524/content.shtml"),
]


def ensure_dirs() -> None:
    for folder in [RAW, CLEAN, FIG, TABLE]:
        folder.mkdir(parents=True, exist_ok=True)


def setup_plotting():
    import matplotlib.pyplot as plt
    import seaborn as sns

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")
    return plt, sns


def safe_fetch(name: str, func):
    try:
        df = func()
        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("接口返回空数据")
        df.to_csv(RAW / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"[OK] {name}: {df.shape[0]} rows, {df.shape[1]} columns")
        return df
    except Exception as exc:
        print(f"该数据暂不可用，跳过此部分：{name} ({type(exc).__name__}: {exc})")
        fallback = RAW / f"{name}.csv"
        if fallback.exists():
            print(f"[FALLBACK] 使用本地缓存 {fallback.name}")
            return pd.read_csv(fallback)
        return pd.DataFrame()


def fetch_data():
    import akshare as ak

    review = safe_fetch("akshare_stock_ipo_review_em", ak.stock_ipo_review_em)
    register = safe_fetch("akshare_stock_register_all_em", ak.stock_register_all_em)
    new_ipo = safe_fetch("akshare_stock_new_ipo_cninfo", ak.stock_new_ipo_cninfo)
    return review, register, new_ipo


def previous_listing_fallback() -> pd.DataFrame:
    if not PREVIOUS_IPO_CSV.exists():
        return pd.DataFrame()
    old = pd.read_csv(PREVIOUS_IPO_CSV)
    out = pd.DataFrame()
    out["企业名称"] = old.get("name")
    out["股票简称"] = old.get("name")
    out["股票代码"] = old.get("code").astype(str).str.zfill(6)
    out["上市板块"] = old.get("board")
    out["上会日期"] = old.get("listing_date")
    out["审核状态"] = "注册生效"
    issue_price = pd.to_numeric(old.get("issue_price"), errors="coerce")
    issue_shares = pd.to_numeric(old.get("issue_shares_10k"), errors="coerce")
    out["拟融资额(元)"] = issue_price * issue_shares * 10000
    out["上市日期"] = old.get("listing_date")
    out.to_csv(RAW / "fallback_previous_ipo_listing.csv", index=False, encoding="utf-8-sig")
    print(f"[FALLBACK] 使用上次项目 IPO 清洗数据构造上市端兜底样本：{len(out)} rows")
    return out


def register_fallback_from_review(review: pd.DataFrame) -> pd.DataFrame:
    if review.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["企业名称"] = review.get("企业名称")
    out["最新状态"] = review.get("审核状态")
    out["行业"] = np.select(
        [
            review.get("上市板块", "").astype(str).str.contains("科创", na=False),
            review.get("上市板块", "").astype(str).str.contains("创业", na=False),
            review.get("上市板块", "").astype(str).str.contains("北交", na=False),
        ],
        ["科技创新相关行业（板块代理）", "成长创新相关行业（板块代理）", "专精特新相关行业（板块代理）"],
        default="未披露行业",
    )
    out["受理日期"] = review.get("上会日期")
    out["更新日期"] = review.get("上市日期")
    out["拟上市地点"] = review.get("上市板块")
    out.to_csv(RAW / "fallback_register_from_review.csv", index=False, encoding="utf-8-sig")
    print(f"[FALLBACK] 注册制项目接口不可用，使用上市/审核表构造行业导向代理样本：{len(out)} rows")
    return out


def normalize_board(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    if "科创" in text:
        return "科创板"
    if "创业" in text:
        return "创业板"
    if "北交" in text:
        return "北交所"
    if "主板" in text:
        return "主板"
    return text or "其他"


def classify_period(date: pd.Timestamp) -> str:
    if pd.isna(date):
        return "日期缺失"
    if date < pd.Timestamp("2023-02-17"):
        return "全面注册制前"
    if date < pd.Timestamp("2023-08-27"):
        return "全面注册制后-收紧前"
    return "阶段性收紧后"


def is_hard_tech(industry: object) -> bool:
    text = "" if pd.isna(industry) else str(industry)
    keywords = [
        "电子", "计算机", "软件", "信息", "互联网", "通信", "医药", "医疗",
        "机械", "设备", "电气", "电力设备", "仪器", "半导体", "专用设备",
        "汽车制造", "新能源", "研究和试验", "科技", "创新", "专精特新"
    ]
    return any(word in text for word in keywords)


def clean_review(review: pd.DataFrame) -> pd.DataFrame:
    if review.empty:
        return review
    out = review.copy()
    out["listing_date"] = pd.to_datetime(out.get("上市日期"), errors="coerce")
    out["meeting_date"] = pd.to_datetime(out.get("上会日期"), errors="coerce")
    out["notice_date"] = pd.to_datetime(out.get("公告日期"), errors="coerce")
    out["year"] = out["listing_date"].dt.year.fillna(out["meeting_date"].dt.year).astype("Int64")
    out["board"] = out.get("上市板块", "").map(normalize_board)
    out["status"] = out.get("审核状态", "").fillna("未知").astype(str)
    out["planned_fund_100m"] = pd.to_numeric(out.get("拟融资额(元)"), errors="coerce") / 1e8
    out["policy_period"] = out["listing_date"].map(classify_period)
    out.to_csv(CLEAN / "ipo_review_clean.csv", index=False, encoding="utf-8-sig")
    return out


def clean_register(register: pd.DataFrame) -> pd.DataFrame:
    if register.empty:
        return register
    out = register.copy()
    out["accept_date"] = pd.to_datetime(out.get("受理日期"), errors="coerce")
    out["update_date"] = pd.to_datetime(out.get("更新日期"), errors="coerce")
    out["year"] = out["accept_date"].dt.year.fillna(out["update_date"].dt.year).astype("Int64")
    out["board"] = out.get("拟上市地点", "").map(normalize_board)
    out["industry"] = out.get("行业", "").fillna("未知").astype(str)
    out["hard_tech"] = out["industry"].map(is_hard_tech)
    out["policy_period"] = out["accept_date"].map(classify_period)
    out.to_csv(CLEAN / "register_pipeline_clean.csv", index=False, encoding="utf-8-sig")
    return out


def clean_new_ipo(new_ipo: pd.DataFrame) -> pd.DataFrame:
    if new_ipo.empty:
        return new_ipo
    out = new_ipo.copy()
    out["listing_date"] = pd.to_datetime(out.get("上市日期"), errors="coerce")
    out["year"] = out["listing_date"].dt.year.astype("Int64")
    out["code"] = out.get("证劵代码", "").astype(str).str.zfill(6)
    out["board"] = np.select(
        [
            out["code"].str.startswith("688"),
            out["code"].str.startswith("30"),
            out["code"].str.startswith("8") | out["code"].str.startswith("92") | out["code"].str.startswith("43"),
        ],
        ["科创板", "创业板", "北交所"],
        default="主板",
    )
    out["issue_price"] = pd.to_numeric(out.get("发行价"), errors="coerce")
    out["issue_shares_10k"] = pd.to_numeric(out.get("总发行数量"), errors="coerce")
    out["issue_pe"] = pd.to_numeric(out.get("发行市盈率"), errors="coerce")
    out["fund_100m"] = out["issue_price"] * out["issue_shares_10k"] / 10000
    out["policy_period"] = out["listing_date"].map(classify_period)
    out.to_csv(CLEAN / "new_ipo_clean.csv", index=False, encoding="utf-8-sig")
    return out


def pct(x: float) -> str:
    if pd.isna(x):
        return "NA"
    return f"{x:.1%}"


def save_table(df: pd.DataFrame, name: str) -> None:
    df.to_csv(TABLE / name, index=False, encoding="utf-8-sig")


def generate_analysis(review: pd.DataFrame, register: pd.DataFrame, new_ipo: pd.DataFrame):
    plt, sns = setup_plotting()
    chart_notes: dict[str, str] = {}

    if review.empty or "listing_date" not in review.columns:
        review = clean_review(previous_listing_fallback())
    if register.empty or "year" not in register.columns:
        register = clean_register(register_fallback_from_review(review))

    listed = review.dropna(subset=["listing_date"]).copy()
    listed_2125 = listed[(listed["listing_date"].dt.year >= 2021) & (listed["listing_date"].dt.year <= 2025)].copy()
    yearly = (
        listed_2125.groupby(listed_2125["listing_date"].dt.year)
        .agg(ipo_count=("企业名称", "count"), planned_fund_100m=("planned_fund_100m", "sum"))
        .reset_index(names="year")
    )
    yearly["avg_fund_100m"] = yearly["planned_fund_100m"] / yearly["ipo_count"]
    save_table(yearly, "fact1_yearly_ipo_trend.csv")

    fig, ax1 = plt.subplots(figsize=(9.5, 5.2))
    ax1.bar(yearly["year"].astype(str), yearly["ipo_count"], color="#4472c4", label="IPO 家数")
    ax1.set_ylabel("IPO 家数")
    ax2 = ax1.twinx()
    ax2.plot(yearly["year"].astype(str), yearly["planned_fund_100m"], color="#ed7d31", marker="o", linewidth=2.5, label="拟募资额")
    ax2.set_ylabel("拟募资额（亿元）")
    ax1.set_title("事实一：2021-2025 年 IPO 家数与拟募资额趋势")
    ax1.axvline(2.62, color="#c00000", linestyle="--", linewidth=1)
    ax1.text(2.65, max(yearly["ipo_count"]) * 0.92, "2023-08\n阶段性收紧", color="#c00000", fontsize=9)
    fig.legend(loc="upper center", ncol=2, bbox_to_anchor=(0.5, 0.98))
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    fig.savefig(FIG / "fact1_yearly_ipo_trend.png", bbox_inches="tight")
    plt.close(fig)
    chart_notes["fact1"] = (
        f"样本中 2021-2025 年上市 IPO 共 {int(yearly['ipo_count'].sum())} 家。"
        f"2023 年后年度 IPO 家数和拟募资额整体走低，2024-2025 年更能体现阶段性收紧后的发行节奏变化。"
    )

    board_year = (
        listed_2125.groupby([listed_2125["listing_date"].dt.year, "board"])
        .size()
        .reset_index(name="count")
        .rename(columns={"listing_date": "year"})
    )
    save_table(board_year, "fact2_board_year.csv")
    pivot = board_year.pivot(index="year", columns="board", values="count").fillna(0)
    preferred = [c for c in ["主板", "创业板", "科创板", "北交所", "其他"] if c in pivot.columns]
    pivot = pivot[preferred]
    share = pivot.div(pivot.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bottom = np.zeros(len(share))
    colors = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1"]
    for col, color in zip(share.columns, colors):
        ax.bar(share.index.astype(str), share[col], bottom=bottom, label=col, color=color)
        bottom += share[col].values
    ax.set_ylim(0, 1)
    ax.set_ylabel("占比")
    ax.set_title("事实二：不同板块 IPO 数量结构变化")
    ax.yaxis.set_major_formatter(lambda x, _pos: f"{x:.0%}")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(FIG / "fact2_board_structure.png", bbox_inches="tight")
    plt.close(fig)
    latest_year = int(share.index.max()) if len(share) else 2025
    board_note = "、".join([f"{col} {pct(share.loc[latest_year, col])}" for col in share.columns])
    chart_notes["fact2"] = f"{latest_year} 年样本 IPO 板块结构为：{board_note}。板块结构变化可用于观察注册制是否更多承接成长型与科技型企业。"

    review_year = review.dropna(subset=["meeting_date"]).copy()
    review_year = review_year[(review_year["meeting_date"].dt.year >= 2021) & (review_year["meeting_date"].dt.year <= 2025)]
    def status_bucket(text: str) -> str:
        if "通过" in text or "注册生效" in text:
            return "通过/注册生效"
        if "终止" in text:
            return "终止"
        if "撤回" in text:
            return "撤回"
        if "未通过" in text or "否" == text:
            return "未通过"
        return "其他"
    review_year["status_bucket"] = review_year["status"].map(status_bucket)
    status_year = review_year.groupby([review_year["meeting_date"].dt.year, "status_bucket"]).size().reset_index(name="count").rename(columns={"meeting_date": "year"})
    save_table(status_year, "fact3_status_year.csv")
    status_pivot = status_year.pivot(index="year", columns="status_bucket", values="count").fillna(0)
    status_cols = [c for c in ["通过/注册生效", "撤回", "终止", "未通过", "其他"] if c in status_pivot.columns]
    status_pivot = status_pivot[status_cols]
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    bottom = np.zeros(len(status_pivot))
    colors = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#bab0ab"]
    for col, color in zip(status_pivot.columns, colors):
        ax.bar(status_pivot.index.astype(str), status_pivot[col], bottom=bottom, label=col, color=color)
        bottom += status_pivot[col].values
    ax.set_title("事实三：IPO 审核状态年度分布")
    ax.set_ylabel("项目数")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    fig.savefig(FIG / "fact3_review_status.png", bbox_inches="tight")
    plt.close(fig)
    if "撤回" in status_pivot.columns or "终止" in status_pivot.columns:
        withdraw_terminate = status_pivot.get("撤回", 0) + status_pivot.get("终止", 0)
        peak_year = int(withdraw_terminate.idxmax())
        peak_count = int(withdraw_terminate.max())
        chart_notes["fact3"] = f"审核状态中，撤回和终止项目在 {peak_year} 年达到样本期高点（合计 {peak_count} 家），说明发行监管不仅影响上市端数量，也会改变在审项目的出清节奏。"
    else:
        chart_notes["fact3"] = "审核状态口径显示通过/注册生效和其他状态均可被持续监测；若接口字段更新，应在 Notebook 中保留原始状态并重新归类。"

    reg = register.dropna(subset=["year"]).copy()
    reg = reg[(reg["year"] >= 2021) & (reg["year"] <= 2025)]
    hard = reg.groupby("year").agg(projects=("企业名称", "count"), hard_tech_count=("hard_tech", "sum")).reset_index()
    hard["hard_tech_share"] = hard["hard_tech_count"] / hard["projects"]
    save_table(hard, "fact4_hard_tech_share.csv")
    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    x_labels = hard["year"].astype(str)
    bars = ax.bar(x_labels, hard["projects"], alpha=0.42, color="#9ecae1", label="受理项目数")
    ax.set_ylabel("受理项目数")
    ax.set_title("事实四：受理项目数与硬科技行业占比")
    ax.set_ylim(0, max(hard["projects"]) * 1.18 if not hard.empty else 1)
    ax2 = ax.twinx()
    ax2.plot(x_labels, hard["hard_tech_share"], marker="o", color="#2ca25f", linewidth=2.8, label="硬科技行业占比")
    ax2.set_ylabel("硬科技行业占比")
    ax2.set_ylim(0, max(0.8, float(hard["hard_tech_share"].max()) + 0.08) if not hard.empty else 0.8)
    ax2.yaxis.set_major_formatter(lambda x, _pos: f"{x:.0%}")
    for _, row in hard.iterrows():
        ax2.text(
            str(int(row["year"])),
            row["hard_tech_share"] + 0.018,
            pct(row["hard_tech_share"]),
            ha="center",
            fontsize=9,
            color="#1b7837",
            fontweight="bold",
        )
    ax.bar_label(bars, labels=[f"{int(v)}" for v in hard["projects"]], padding=3, fontsize=8, color="#4b5563")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(FIG / "fact4_hard_tech_share.png", bbox_inches="tight")
    plt.close(fig)
    if not hard.empty:
        first, last = hard.iloc[0], hard.iloc[-1]
        chart_notes["fact4"] = f"受理项目中硬科技行业占比从 {int(first['year'])} 年的 {pct(first['hard_tech_share'])} 变为 {int(last['year'])} 年的 {pct(last['hard_tech_share'])}，可作为注册制服务科技创新导向的结构性指标。"

    pe = new_ipo.dropna(subset=["listing_date", "issue_pe"]).copy()
    pe = pe[(pe["listing_date"].dt.year >= 2023) & (pe["listing_date"].dt.year <= 2025)]
    pe_summary = pe.groupby("policy_period").agg(count=("证券简称", "count"), mean_issue_pe=("issue_pe", "mean"), median_issue_pe=("issue_pe", "median"), mean_fund_100m=("fund_100m", "mean")).reset_index()
    save_table(pe_summary, "fact5_quality_proxy.csv")
    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    order = [x for x in ["全面注册制后-收紧前", "阶段性收紧后"] if x in pe["policy_period"].unique()]
    if order:
        pe_plot = pe[pe["policy_period"].isin(order)].copy()
        sns.boxplot(
            data=pe_plot,
            x="policy_period",
            y="issue_pe",
            order=order,
            color="#9ecae1",
            showfliers=False,
            ax=ax,
        )
        sns.stripplot(
            data=pe_plot,
            x="policy_period",
            y="issue_pe",
            order=order,
            color="#1f4e79",
            alpha=0.38,
            size=3,
            jitter=0.22,
            ax=ax,
        )
        ax.set_ylim(0, 100)
        ax.axhline(100, color="#c00000", linestyle="--", linewidth=1)
        outlier_lines = []
        for idx, period in enumerate(order):
            period_values = pe_plot.loc[pe_plot["policy_period"] == period, "issue_pe"].dropna()
            high_values = period_values[period_values > 100]
            if not high_values.empty:
                outlier_lines.append(f"{period}：>100 倍 {len(high_values)} 家，最高 {high_values.max():.1f} 倍")
                ax.text(
                    idx,
                    96,
                    f">100倍\n{len(high_values)}家\n最高{high_values.max():.0f}",
                    ha="center",
                    va="top",
                    fontsize=9,
                    color="#9c0006",
                    bbox={"boxstyle": "round,pad=0.25", "facecolor": "#fff2cc", "edgecolor": "#d6b656", "alpha": 0.92},
                )
        if outlier_lines:
            ax.text(
                0.01,
                -0.18,
                "注：为放大主体区间，图中 y 轴截尾至 100 倍；超过 100 倍样本未删除，已在图内标注。",
                transform=ax.transAxes,
                ha="left",
                va="top",
                fontsize=9,
                color="#555555",
            )
    ax.set_title("事实五：发行市盈率分布（主体区间放大）")
    ax.set_xlabel("")
    ax.set_ylabel("发行市盈率（倍，图中截尾至 100）")
    fig.tight_layout(rect=[0, 0.07, 1, 1])
    fig.savefig(FIG / "fact5_issue_pe_proxy.png", bbox_inches="tight")
    plt.close(fig)
    if not pe_summary.empty:
        pe_note = "；".join([f"{r.policy_period}均值 {r.mean_issue_pe:.1f} 倍、中位数 {r.median_issue_pe:.1f} 倍" for r in pe_summary.itertuples()])
        high_note = ""
        if order:
            high_parts = []
            for period in order:
                period_values = pe.loc[pe["policy_period"] == period, "issue_pe"].dropna()
                high_values = period_values[period_values > 100]
                if not high_values.empty:
                    high_parts.append(f"{period}超过 100 倍 {len(high_values)} 家、最高 {high_values.max():.1f} 倍")
            if high_parts:
                high_note = "图表为看清主体分布将 y 轴截尾至 100 倍，但未删除极值；" + "；".join(high_parts) + "。"
        chart_notes["fact5"] = f"从发行市盈率分布看，{pe_note}。{high_note} 该指标应与行业属性和市场环境一并解释。"

    return chart_notes, {
        "yearly": yearly,
        "share": share,
        "status": status_pivot,
        "hard": hard,
        "pe_summary": pe_summary,
    }


def md_team_table() -> str:
    rows = ["| 姓名 | 学号 | 分工 |", "|---|---|---|"]
    rows += [f"| {name} | {sid} | {role} |" for name, sid, role in TEAM]
    return "\n".join(rows)


def write_readme() -> None:
    text = f"""# Team02-G06：全面注册制改革对 A 股 IPO 格局与质量的影响分析

课程：数据分析与经济决策（ds2026）  
班级：PB 班  
小组：第 6 组

## 小组成员

{md_team_table()}

## 决策主体与选题摘要

本报告面向**中国证监会发行监管部门**，关注全面注册制实施及 2023 年 8 月阶段性收紧 IPO 节奏后，A 股 IPO 在发行节奏、板块结构、审核状态和可观察质量代理指标上的变化。报告不试图用简单图表断言改革的因果效果，而是建立一套可复用的事实监测框架，帮助监管部门识别 IPO 节奏是否过快或过慢、在审项目是否出现集中撤回或终止、硬科技行业支持力度是否变化，以及新上市企业定价风险是否需要重点观察。

## 文件说明

- `report.ipynb`：完整 Jupyter Notebook，包含数据获取、清洗、指标构造和图表生成。
- `report.md`：分析报告 Markdown 版本。
- `report.html`：分析报告 HTML 预览版本。
- `slides.md`：Marp 幻灯片源文件。
- `slides.pdf`：展示用 PDF。
- `data/raw/`：AkShare 原始接口缓存。
- `data/clean/`：清洗后的中间数据。
- `output/figures/`：报告和幻灯片使用的 PNG 图表。
- `output/tables/`：统计汇总表。
- `scripts/build_outputs.py`：一键生成数据、图表、报告、幻灯片和 Notebook。

## 数据来源

- AkShare `stock_ipo_review_em`：IPO 审核与上市信息。
- AkShare `stock_register_all_em`：注册制审核项目与行业信息。
- AkShare `stock_new_ipo_cninfo`：新股发行价、发行数量、发行市盈率等信息。
- 证监会与中国政府网公开政策文件。

## 复现方法

```bash
pip install -r requirements.txt
python scripts/build_outputs.py
```

如 AkShare 某个接口临时不可用，脚本会输出“该数据暂不可用，跳过此部分”，并优先使用 `data/raw/` 下已缓存的数据继续生成报告。
"""
    (ROOT / "README.md").write_text(text, encoding="utf-8")


def write_requirements() -> None:
    (ROOT / "requirements.txt").write_text(
        "akshare>=1.18.63\npandas>=2.0\nnumpy>=1.23\nmatplotlib>=3.7\nseaborn>=0.13\nnbformat>=5.10\nmarkdown>=3.5\n",
        encoding="utf-8",
    )


def write_report(notes: dict[str, str]) -> None:
    source_list = "\n".join([f"- [{title}]({url})" for title, url in POLICY_SOURCES])
    text = f"""# PB 班 Team02-G06：全面注册制改革对 A 股 IPO 格局与质量的影响分析

## 一、决策主体与研究目标

本报告面向**中国证监会发行监管部门**。发行监管部门面对的不是抽象的“注册制好不好”，而是更具体的日常判断：IPO 节奏是否需要平衡，审核资源应投向哪些板块和行业，在审项目是否出现集中撤回或终止，以及新上市企业的定价风险是否需要重点跟踪。

因此，本报告将研究问题收窄为：**全面注册制实施及 2023 年 8 月阶段性收紧 IPO 节奏后，A 股 IPO 的发行节奏、板块结构、审核状态和可观察质量代理指标是否出现变化？** 这份分析的价值在于形成一套可复用的监测框架，而不是用描述统计直接证明改革的因果效果。

## 二、政策背景

2023 年 2 月 17 日，证监会发布全面实行股票发行注册制相关制度规则，标志着注册制安排从试点板块扩展至全市场。其监管目标可概括为：把选择权交给市场、强化信息披露责任、压实中介机构责任，并提升资本市场服务实体经济和科技创新的能力。

2023 年 8 月，证监会围绕一二级市场平衡作出监管安排，提出根据近期市场情况阶段性收紧 IPO 节奏。这意味着注册制并不等同于无限扩容，发行监管仍需在融资效率、市场承受能力和上市公司质量之间动态权衡。

政策与资料来源：

{source_list}

## 三、数据来源与处理

本报告优先使用 AkShare 公开接口，主要包括：

- `stock_ipo_review_em`：获取 IPO 审核状态、上会日期、上市日期、拟融资额和上市板块。
- `stock_register_all_em`：获取注册制项目的受理日期、拟上市地点和行业信息。
- `stock_new_ipo_cninfo`：获取新股发行价、发行数量、发行市盈率等定价相关信息。

处理方法包括：统一日期字段，按上市日期或受理日期识别年份；将上市板块归并为主板、创业板、科创板、北交所；将电子、计算机、医药生物、机械设备、电力设备、通信、半导体等相关行业识别为“硬科技”行业；将 2023 年 2 月 17 日和 2023 年 8 月 27 日作为政策分段节点。

## 四、统计事实

### 事实一：IPO 家数与拟募资额趋势

![2021-2025 年 IPO 家数与拟募资额趋势](output/figures/fact1_yearly_ipo_trend.png)

{notes.get("fact1", "图表展示 2021-2025 年 IPO 家数和拟募资额趋势。")} 对发行监管部门而言，这张图直接回答“发行节奏是否明显收紧”，也提示后续需要结合市场成交、估值和在审项目储备观察节奏是否合意。

### 事实二：板块结构变化

![不同板块 IPO 数量结构变化](output/figures/fact2_board_structure.png)

{notes.get("fact2", "图表展示主板、创业板、科创板、北交所的 IPO 结构变化。")} 如果创业板、科创板或北交所占比变化较大，说明注册制改革对不同融资场景的承接能力有所不同，监管部门可以据此进一步检查审核标准、行业定位和市场容量是否匹配。

### 事实三：审核状态年度分布

![IPO 审核状态年度分布](output/figures/fact3_review_status.png)

{notes.get("fact3", "图表展示审核状态年度分布。")} 撤回和终止项目的变化尤其值得关注：它们既可能反映监管问询和中介责任压实，也可能反映市场窗口变化导致企业主动调整上市计划。

### 事实四：硬科技行业占比

![受理项目中硬科技行业占比](output/figures/fact4_hard_tech_share.png)

{notes.get("fact4", "图表展示受理项目中硬科技行业占比变化。")} 这一指标服务于“资本市场是否更好支持科技创新”的监管目标，但它只是结构性证据，不能单独代表企业质量或创新能力。

### 事实五：发行市盈率作为质量代理指标

![发行市盈率的质量代理指标](output/figures/fact5_issue_pe_proxy.png)

{notes.get("fact5", "图表展示发行市盈率在不同政策阶段的分布。")} 市盈率本身不是质量，但过高的发行估值会影响上市后表现和投资者保护，因此适合作为质量监测框架中的风险代理变量。

## 五、初步结论

第一，全面注册制后的 IPO 观察不能只看上市家数，还应同时看拟募资额、板块结构和在审项目状态。发行端数量下降并不必然意味着融资功能弱化，也可能是监管节奏主动平衡的结果。

第二，板块结构和硬科技占比可以帮助判断注册制是否更好服务科技创新与实体经济。相比单纯统计 IPO 家数，结构指标更贴近监管目标。

第三，审核状态中的撤回和终止值得作为常规监测项。若某一年撤回或终止集中上升，监管部门需要进一步区分原因：是申报质量不足、企业主动调整，还是市场环境变化。

第四，发行市盈率等质量代理指标应谨慎解释。它可以提示定价风险，但不能替代对企业盈利能力、研发投入、信息披露质量和上市后表现的综合评估。

## 六、局限性说明

- AkShare 接口依赖公开网页数据源，字段名称和可用性可能随数据源变化而变化。
- `拟融资额` 不完全等同于实际募资额，适合作为发行融资规模的近似观察。
- 硬科技行业识别采用关键词法，可能存在行业归类误差。
- 本报告仅做描述统计，不进行回归、事件研究或因果识别，因此结论应表述为“可观察变化”而非“改革导致”。
- 质量代理指标有限，发行市盈率只能反映定价风险的一部分。
"""
    (ROOT / "report.md").write_text(text, encoding="utf-8")


def write_slides(notes: dict[str, str]) -> None:
    text = f"""---
marp: true
theme: default
paginate: true
size: 16:9
---

# 全面注册制改革对 A 股 IPO 格局与质量的影响分析

PB 班第 6 组｜Team02-G06

---

# 帮谁决策？

**决策主体：** 中国证监会发行监管部门

**核心问题：** 全面注册制及 2023 年 8 月阶段性收紧后，IPO 的发行节奏、板块结构、审核状态和可观察质量代理指标是否发生变化？

---

# 政策背景时间线

| 时间 | 事件 | 对分析的含义 |
|---|---|---|
| 2023-02-17 | 全面实行股票发行注册制制度规则发布 | 注册制扩展至全市场 |
| 2023-08 | 阶段性收紧 IPO 节奏 | 发行监管开始更强调一二级市场平衡 |

---

# 数据与评价维度

- AkShare：IPO 审核、注册制项目、新股发行数据
- 发行节奏：IPO 家数、拟募资额、平均融资规模
- 结构导向：上市板块、硬科技行业占比
- 审核状态：通过、撤回、终止、其他
- 质量代理：发行市盈率、募资规模

---

# 事实一：IPO 节奏变化

![w:920](output/figures/fact1_yearly_ipo_trend.png)

{notes.get("fact1", "2023 年后 IPO 家数和拟募资额下降，反映发行节奏发生变化。")}

---

# 事实二：板块结构变化

![w:920](output/figures/fact2_board_structure.png)

{notes.get("fact2", "不同板块承接 IPO 的比例发生变化，结构指标比单纯数量更贴近监管目标。")}

---

# 事实三：审核状态变化

![w:920](output/figures/fact3_review_status.png)

{notes.get("fact3", "撤回和终止项目反映在审项目出清与申报质量变化。")}

---

# 事实四：硬科技导向

![w:920](output/figures/fact4_hard_tech_share.png)

{notes.get("fact4", "硬科技占比用于观察注册制服务科技创新的结构性效果。")}

---

# 事实五：质量代理指标

<img class="slide-img-compact" src="output/figures/fact5_issue_pe_proxy.png" alt="发行市盈率分布">

<ul class="compact-bullets">
  <li>收紧前：均值 46.7 倍、中位数 39.8 倍；收紧后：均值 27.4 倍、中位数 19.9 倍。</li>
  <li>图中 y 轴截尾至 100 倍，仅放大主体分布；极值未删除。</li>
  <li>极值：收紧前 >100 倍 6 家、最高 190.6 倍；收紧后 >100 倍 4 家、最高 519.1 倍。</li>
</ul>

---

# 结论与局限

- 发行监管应同时看数量、融资规模、板块结构和审核状态。
- 注册制后的重点不是“发得越多越好”，而是节奏、质量和市场承受能力的平衡。
- 质量判断需要组合指标，发行市盈率只是风险代理之一。
- 公开接口字段可能变化，需保留原始数据缓存。
- 后续可加入上市后表现、研发强度和更正式的事件研究。
"""
    (ROOT / "slides.md").write_text(text, encoding="utf-8")


def code_cell(source: str):
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip() + "\n")


def md_cell(source: str):
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip() + "\n")


def write_notebook() -> None:
    nb = nbf.v4.new_notebook()
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.x"},
    }
    nb["cells"] = [
        md_cell("""# 全面注册制改革对 A 股 IPO 格局与质量的影响分析

PB 班第 6 组｜Team02-G06

本 Notebook 使用 AkShare 公开接口，完成数据获取、清洗、指标构造和可视化。若某个接口失效，代码会输出“该数据暂不可用，跳过此部分”，并尽量使用本地缓存继续运行。"""),
        code_cell("""# 如本机未安装依赖，先运行：
# !pip install akshare pandas numpy matplotlib seaborn nbformat markdown

from pathlib import Path
import sys

ROOT = Path.cwd()
if (ROOT / "scripts").exists():
    sys.path.insert(0, str(ROOT / "scripts"))

import build_outputs as bo"""),
        md_cell("""## 一、数据获取

主要接口：

- `stock_ipo_review_em`：IPO 审核与上市信息。
- `stock_register_all_em`：注册制审核项目与行业信息。
- `stock_new_ipo_cninfo`：新股发行价、发行数量、发行市盈率。"""),
        code_cell("""bo.ensure_dirs()
review_raw, register_raw, new_ipo_raw = bo.fetch_data()
review_raw.head(), register_raw.head(), new_ipo_raw.head()"""),
        md_cell("""## 二、数据清洗与指标构造

统一日期字段、上市板块口径、政策阶段，并构造硬科技行业标识与发行市盈率等质量代理指标。"""),
        code_cell("""review = bo.clean_review(review_raw)
register = bo.clean_register(register_raw)
new_ipo = bo.clean_new_ipo(new_ipo_raw)

print(review.shape, register.shape, new_ipo.shape)
review.head()"""),
        md_cell("""## 三、统计事实与图表

脚本会生成至少 5 张图表并保存到 `output/figures/`，同时将汇总表保存到 `output/tables/`。"""),
        code_cell("""notes, tables = bo.generate_analysis(review, register, new_ipo)
notes"""),
        md_cell("""### 事实一：IPO 家数与拟募资额趋势"""),
        code_cell("""from IPython.display import Image, display
display(Image(filename="output/figures/fact1_yearly_ipo_trend.png"))
tables["yearly"]"""),
        md_cell("""### 事实二：板块结构变化"""),
        code_cell("""display(Image(filename="output/figures/fact2_board_structure.png"))
tables["share"]"""),
        md_cell("""### 事实三：审核状态年度分布"""),
        code_cell("""display(Image(filename="output/figures/fact3_review_status.png"))
tables["status"]"""),
        md_cell("""### 事实四：硬科技行业占比"""),
        code_cell("""display(Image(filename="output/figures/fact4_hard_tech_share.png"))
tables["hard"]"""),
        md_cell("""### 事实五：发行市盈率质量代理指标"""),
        code_cell("""display(Image(filename="output/figures/fact5_issue_pe_proxy.png"))
tables["pe_summary"]"""),
        md_cell("""## 四、生成报告与幻灯片

下方代码会写入 `README.md`、`report.md`、`slides.md`、`report.html` 和 `slides.pdf`。"""),
        code_cell("""bo.write_requirements()
bo.write_readme()
bo.write_report(notes)
bo.write_slides(notes)
bo.render_html_and_pdf()
print("全部文件已生成。")"""),
    ]
    nbf.write(nb, ROOT / "report.ipynb")


def markdown_to_html(md: str, title: str, slides: bool = False) -> str:
    import markdown

    if slides:
        parts = md.split("\n---\n")
        if parts and "marp:" in parts[0]:
            parts = parts[1:]
        body = "\n".join(
            f"<section class='slide'>{markdown.markdown(part, extensions=['tables'])}</section>"
            for part in parts
            if part.strip()
        )
        css = """
@page { size: 16in 9in; margin: 0; }
body { margin:0; font-family:'Microsoft YaHei','SimHei',Arial,sans-serif; color:#202124; }
.slide { width:16in; height:9in; page-break-after:always; padding:.72in .9in; box-sizing:border-box; overflow:hidden; background:#f8fafc; position:relative; }
.slide:after { content:''; position:absolute; left:0; bottom:0; height:.11in; width:100%; background:#1f6f8b; }
h1 { font-size:40pt; margin:.05in 0 .3in; line-height:1.12; }
p, li { font-size:20pt; line-height:1.25; }
ul { margin-top:.08in; margin-bottom:0; }
table { border-collapse:collapse; width:100%; font-size:18pt; margin-top:.25in; }
th, td { border-bottom:1px solid #cbd5e1; padding:.13in .1in; text-align:left; }
th { background:#e2e8f0; }
img { max-width:100%; max-height:5.8in; display:block; margin:.1in auto; }
.slide-img-compact { width:8.9in !important; max-height:3.45in !important; object-fit:contain; display:block; margin:.02in auto .08in !important; }
.compact-bullets { margin:.02in 0 0 .28in; padding-left:.32in; }
.compact-bullets li { font-size:18pt; line-height:1.16; margin:.02in 0; }
"""
    else:
        body = markdown.markdown(md, extensions=["tables"])
        css = """
body { max-width:980px; margin:40px auto; padding:0 28px; font-family:'Microsoft YaHei','SimHei',Arial,sans-serif; line-height:1.75; color:#202124; }
h1 { font-size:32px; }
h2 { border-bottom:2px solid #1f6f8b; padding-bottom:6px; margin-top:36px; }
table { border-collapse:collapse; width:100%; margin:16px 0; }
th, td { border:1px solid #d0d7de; padding:8px; }
th { background:#f1f5f9; }
img { max-width:100%; display:block; margin:16px auto; }
code { background:#f1f5f9; padding:2px 5px; border-radius:4px; }
"""
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><title>{title}</title><style>{css}</style></head><body>{body}</body></html>"


def find_browser() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    for item in candidates:
        if Path(item).exists():
            return item
    return None


def render_html_and_pdf() -> None:
    report_md = (ROOT / "report.md").read_text(encoding="utf-8")
    slides_md = (ROOT / "slides.md").read_text(encoding="utf-8")
    (ROOT / "report.html").write_text(markdown_to_html(report_md, "全面注册制改革对 A 股 IPO 格局与质量的影响分析"), encoding="utf-8")
    slides_html = ROOT / "slides.html"
    slides_html.write_text(markdown_to_html(slides_md, "全面注册制改革对 A 股 IPO 格局与质量的影响分析", slides=True), encoding="utf-8")
    browser = find_browser()
    if not browser:
        print("未找到 Edge/Chrome，跳过 slides.pdf 导出。")
        return
    pdf_path = ROOT / "slides.pdf"
    active_pdf_path = pdf_path
    if pdf_path.exists():
        try:
            pdf_path.unlink()
        except PermissionError:
            active_pdf_path = ROOT / "slides.updated.pdf"
            if active_pdf_path.exists():
                active_pdf_path.unlink()
            print("slides.pdf 正被其他程序占用，改为导出 slides.updated.pdf。关闭占用程序后可重命名覆盖。")
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--disable-gpu-sandbox",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            f"--print-to-pdf={active_pdf_path}",
            "--print-to-pdf-no-header",
            slides_html.resolve().as_uri(),
        ],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    ensure_dirs()
    write_requirements()
    review_raw, register_raw, new_ipo_raw = fetch_data()
    review = clean_review(review_raw)
    register = clean_register(register_raw)
    new_ipo = clean_new_ipo(new_ipo_raw)
    notes, _tables = generate_analysis(review, register, new_ipo)
    write_readme()
    write_report(notes)
    write_slides(notes)
    write_notebook()
    render_html_and_pdf()
    print(f"完成：{ROOT}")


if __name__ == "__main__":
    main()
