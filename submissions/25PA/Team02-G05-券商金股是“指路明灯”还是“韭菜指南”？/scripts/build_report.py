#!/usr/bin/env python3
"""Build the final gold-stock analysis report artifacts.

Outputs:
- report.md
- report.ipynb
- report.html
- report.pdf
- outputs/report_figures/*.png
"""

from __future__ import annotations

import shutil
import subprocess
import os
import re
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/mplconfig_dshw_report")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "outputs" / "report_figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)
FIG_DPI = 320

START = pd.Timestamp("2025-05-01")
END = pd.Timestamp("2026-04-30")
MONTHS = pd.period_range("2025-05", "2026-04", freq="M").astype(str).tolist()
INITIAL_CAPITAL = 1_000_000

BROKER_ORDER = ["中信建投证券", "华泰证券", "招商证券", "平安证券", "天风证券", "开源证券"]
TIER_ORDER = ["头部", "腰部", "尾部"]
TIER_MAP = {
    "中信建投证券": "头部",
    "华泰证券": "头部",
    "招商证券": "腰部",
    "平安证券": "腰部",
    "天风证券": "尾部",
    "开源证券": "尾部",
}

WIND_TO_SW = {
    "材料": ["801030", "801040", "801050", "801710"],
    "工业": ["801890", "801720", "801730", "801740"],
    "可选消费": ["801880", "801110", "801130", "801140", "801210"],
    "医疗保健": ["801150"],
    "日常消费": ["801120", "801010"],
    "公用事业": ["801160"],
    "信息技术": ["801080", "801750", "801770", "801760"],
    "金融": ["801780", "801790"],
    "房地产": ["801180"],
    "能源": ["801950", "801960"],
    "电信服务": ["801770"],
}


def configure_fonts() -> None:
    font_candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for font_path in font_candidates:
        if Path(font_path).exists():
            font_manager.fontManager.addfont(font_path)
            font_name = font_manager.FontProperties(fname=font_path).get_name()
            plt.rcParams["font.sans-serif"] = [font_name, "Arial Unicode MS", "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["ps.fonttype"] = 42
    plt.rcParams["axes.titleweight"] = "bold"
    plt.rcParams["axes.titlesize"] = 16
    plt.rcParams["axes.labelsize"] = 12
    plt.rcParams["xtick.labelsize"] = 11
    plt.rcParams["ytick.labelsize"] = 11
    plt.rcParams["legend.fontsize"] = 10.5


def fmt_pct(x: float | int | None, digits: int = 1, signed: bool = False) -> str:
    if x is None or pd.isna(x):
        return ""
    sign = "+" if signed else ""
    return f"{x:{sign}.{digits}f}%"


def fmt_num(x: float | int | None, digits: int = 1) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{x:.{digits}f}"


def fmt_wan(x: float | int | None, digits: int = 2) -> str:
    if x is None or pd.isna(x):
        return ""
    return f"{x / 10_000:.{digits}f} 万元"


def md_escape(value) -> str:
    text = "" if pd.isna(value) else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def md_table(rows: list[list], headers: list[str]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(v) for v in row) + " |")
    return "\n".join(lines)


def image_md(filename: str, alt: str) -> str:
    return f"![{alt}](outputs/report_figures/{filename})"


REPORT_COLORS = {
    "navy": "#152B45",
    "blue": "#1F5D8C",
    "red": "#A23E48",
    "green": "#2F6B5F",
    "gold": "#B3832D",
    "purple": "#5B567D",
    "gray": "#6B7280",
    "light_gray": "#F5F7FA",
    "grid": "#E6E9EF",
    "line": "#CBD5E1",
    "ink": "#111827",
}


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw_path = ROOT / "六大券商合并数据.xlsx"
    raw_all = pd.read_excel(raw_path, sheet_name="合并数据")
    raw_all["推荐月份"] = pd.to_datetime(raw_all["推荐月份"])
    raw_all["月份"] = raw_all["推荐月份"].dt.to_period("M").astype(str)
    raw_all["梯队"] = raw_all["机构名称"].map(TIER_MAP)
    df = raw_all[(raw_all["推荐月份"] >= START) & (raw_all["推荐月份"] <= END)].copy()
    df["当月涨跌幅(%)"] = pd.to_numeric(df["当月涨跌幅(%)"], errors="coerce")

    style_path = ROOT / "维度3" / "六家机构荐股风格分析.xlsx"
    style = pd.read_excel(style_path, sheet_name="推荐明细含指标")
    style["推荐月份"] = pd.to_datetime(style["推荐月份"])
    style["月份"] = style["推荐月份"].dt.to_period("M").astype(str)
    style = style[(style["推荐月份"] >= START) & (style["推荐月份"] <= END)].copy()
    style["梯队"] = style["机构名称"].map(TIER_MAP)
    for col in ["市盈率PE", "营收同比增长率%", "股利收益率%", "成长指数"]:
        style[col] = pd.to_numeric(style[col], errors="coerce")

    meta = {
        "raw_all_records": len(raw_all),
        "filtered_records": len(df),
        "dropped_records": int((raw_all["推荐月份"] < START).sum() + (raw_all["推荐月份"] > END).sum()),
        "dropped_months": ", ".join(sorted(set(raw_all.loc[raw_all["推荐月份"] < START, "月份"]))),
        "unique_stocks": df["证券代码"].nunique(),
        "months": df["月份"].nunique(),
        "industries": df["Wind一级行业"].nunique(),
    }
    return df, style, meta


def get_index_monthly_returns() -> pd.DataFrame:
    cache_path = ROOT / "outputs" / "market_index_monthly_returns.csv"
    if cache_path.exists():
        cached = pd.read_csv(cache_path)
        needed = {"上证指数", "深证成指", "创业板指"}
        if needed.issubset(set(cached["指数"])) and set(MONTHS).issubset(set(cached["月份"].astype(str))):
            cached["月份"] = cached["月份"].astype(str)
            return cached[cached["月份"].isin(MONTHS)].copy()

    import akshare as ak

    rows = []
    for symbol, name in [("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指")]:
        idx = ak.stock_zh_index_daily(symbol=symbol)
        idx["date"] = pd.to_datetime(idx["date"])
        monthly_close = idx.set_index("date").sort_index()["close"].resample("ME").last()
        monthly_ret = monthly_close.pct_change(fill_method=None) * 100
        selected = monthly_ret[monthly_ret.index.to_period("M").astype(str).isin(MONTHS)]
        for dt, ret in selected.items():
            rows.append({"月份": dt.to_period("M").strftime("%Y-%m"), "指数": name, "月收益率(%)": float(ret)})
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "market_index_monthly_returns.csv", index=False, encoding="utf-8-sig")
    return out


def get_industry_index_returns() -> pd.DataFrame:
    cache_path = ROOT / "outputs" / "industry_index_monthly_returns.csv"
    if cache_path.exists():
        cached = pd.read_csv(cache_path)
        if set(WIND_TO_SW).issubset(set(cached["Wind一级行业"])) and set(MONTHS).issubset(set(cached["月份"].astype(str))):
            cached["月份"] = cached["月份"].astype(str)
            return cached[cached["月份"].isin(MONTHS)].copy()

    import akshare as ak

    all_codes = sorted({code for codes in WIND_TO_SW.values() for code in codes})
    code_month_ret: dict[str, dict[str, float]] = {}
    for code in all_codes:
        idx = ak.index_hist_sw(symbol=code)
        idx["日期"] = pd.to_datetime(idx["日期"])
        close = idx.set_index("日期").sort_index()["收盘"].resample("ME").last()
        ret = close.pct_change(fill_method=None) * 100
        code_month_ret[code] = {
            dt.to_period("M").strftime("%Y-%m"): float(value)
            for dt, value in ret.items()
            if pd.notna(value)
        }

    rows = []
    for wind_industry, sw_codes in WIND_TO_SW.items():
        for month in MONTHS:
            values = [code_month_ret.get(code, {}).get(month) for code in sw_codes]
            values = [v for v in values if v is not None and pd.notna(v)]
            if values:
                rows.append(
                    {
                        "Wind一级行业": wind_industry,
                        "月份": month,
                        "行业指数收益率(%)": float(np.mean(values)),
                    }
                )
    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "industry_index_monthly_returns.csv", index=False, encoding="utf-8-sig")
    return out


def max_drawdown(monthly_returns_pct: pd.Series) -> float:
    returns = monthly_returns_pct.dropna() / 100
    wealth = pd.concat([pd.Series([1.0]), (1 + returns).cumprod()], ignore_index=True)
    drawdown = wealth / wealth.cummax() - 1
    return float(drawdown.min() * 100) if len(drawdown) else np.nan


def run_ols(y: pd.Series, x: pd.DataFrame) -> dict:
    data = pd.concat([y.rename("y"), x], axis=1).dropna()
    cols = data.columns[1:].tolist()
    X = np.column_stack([np.ones(len(data)), data[cols].to_numpy(float)])
    yv = data["y"].to_numpy(float)
    beta = np.linalg.lstsq(X, yv, rcond=None)[0]
    residual = yv - X @ beta
    n, k = X.shape
    sigma2 = float((residual @ residual) / (n - k))
    vcov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(vcov))
    t_values = beta / se
    ss_tot = float(((yv - yv.mean()) @ (yv - yv.mean())))
    r2 = 1 - float((residual @ residual)) / ss_tot
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k)
    table = pd.DataFrame(
        {
            "变量": ["常数"] + cols,
            "系数": beta,
            "标准误": se,
            "t值": t_values,
        }
    )
    return {"table": table, "n": n, "r2": r2, "adj_r2": adj_r2}


def build_analysis(df: pd.DataFrame, style: pd.DataFrame) -> dict:
    index_monthly = get_index_monthly_returns()
    industry_monthly = get_industry_index_returns()

    df = df.merge(industry_monthly, on=["Wind一级行业", "月份"], how="left")
    sse = index_monthly[index_monthly["指数"] == "上证指数"][["月份", "月收益率(%)"]].rename(
        columns={"月收益率(%)": "上证月收益率(%)"}
    )
    df = df.merge(sse, on="月份", how="left")
    df["行业超额收益率(%)"] = df["当月涨跌幅(%)"] - df["行业指数收益率(%)"]
    df["上证超额收益率(%)"] = df["当月涨跌幅(%)"] - df["上证月收益率(%)"]
    total_recommend_count = df.groupby("证券代码")["证券代码"].transform("size")
    df["累计推荐次数_样本"] = total_recommend_count

    broker_counts = (
        df.groupby("机构名称")
        .agg(
            推荐记录数=("证券代码", "size"),
            唯一股票数=("证券代码", "nunique"),
            平均当月收益率=("当月涨跌幅(%)", "mean"),
            平均行业超额收益率=("行业超额收益率(%)", "mean"),
        )
        .reindex(BROKER_ORDER)
    )

    tier_counts = (
        df.groupby("梯队")
        .agg(
            推荐记录数=("证券代码", "size"),
            唯一股票数=("证券代码", "nunique"),
            平均当月收益率=("当月涨跌幅(%)", "mean"),
            平均行业超额收益率=("行业超额收益率(%)", "mean"),
        )
        .reindex(TIER_ORDER)
    )

    industry = (
        df.groupby("Wind一级行业")
        .agg(
            推荐次数=("证券代码", "size"),
            金股平均收益率=("当月涨跌幅(%)", "mean"),
            行业指数收益率=("行业指数收益率(%)", "mean"),
            平均行业超额收益率=("行业超额收益率(%)", "mean"),
        )
        .sort_values("推荐次数", ascending=False)
    )
    industry["推荐占比"] = industry["推荐次数"] / len(df) * 100

    broker_top3 = []
    for broker in BROKER_ORDER:
        shares = df[df["机构名称"] == broker]["Wind一级行业"].value_counts(normalize=True).head(3) * 100
        broker_top3.append(
            [
                broker,
                "、".join([f"{idx} {value:.1f}%" for idx, value in shares.items()]),
                int((df["机构名称"] == broker).sum()),
            ]
        )

    stock_counts = (
        df.groupby(["证券代码", "证券简称"])
        .size()
        .reset_index(name="累计推荐次数")
        .sort_values(["累计推荐次数", "证券代码"], ascending=[False, True])
    )
    top10 = stock_counts.head(10).copy()
    bottom10 = stock_counts[stock_counts["累计推荐次数"] >= 2].sort_values(["累计推荐次数", "证券代码"]).head(10).copy()
    once_count = int((stock_counts["累计推荐次数"] == 1).sum())
    repeat_count = int((stock_counts["累计推荐次数"] >= 2).sum())
    repeat_records = int(df[df["证券代码"].isin(stock_counts.loc[stock_counts["累计推荐次数"] >= 2, "证券代码"])].shape[0])
    top10_tech = top10[top10["证券代码"].isin(set(df.loc[df["Wind一级行业"] == "信息技术", "证券代码"]))].copy()

    def stock_group_stats(name: str, stock_list: pd.DataFrame) -> dict:
        g = df[df["证券代码"].isin(stock_list["证券代码"])].copy()
        monthly = g.groupby("月份")["当月涨跌幅(%)"].mean().reindex(MONTHS)
        active_monthly = monthly.dropna()
        return {
            "分组": name,
            "股票数": int(stock_list["证券代码"].nunique()),
            "推荐记录数": int(len(g)),
            "有效月份数": int(active_monthly.shape[0]),
            "平均收益率": float(g["当月涨跌幅(%)"].mean()),
            "相对上证Alpha": float(g["上证超额收益率(%)"].mean()),
            "正收益占比": float((g["当月涨跌幅(%)"] > 0).mean() * 100),
            "跑赢上证占比": float((g["上证超额收益率(%)"] > 0).mean() * 100),
            "月均复利收益": float(((1 + active_monthly / 100).prod() - 1) * 100),
            "monthly": monthly,
        }

    group_stats = pd.DataFrame(
        [stock_group_stats("Top10 抱团股", top10), stock_group_stats("Bottom10 冷门股", bottom10)]
    )

    top_monthly = group_stats.loc[group_stats["分组"] == "Top10 抱团股", "monthly"].iloc[0]
    bottom_monthly = group_stats.loc[group_stats["分组"] == "Bottom10 冷门股", "monthly"].iloc[0]
    sse_monthly = sse.set_index("月份")["上证月收益率(%)"].reindex(MONTHS)
    top_bottom_monthly = pd.DataFrame(
        {
            "Top10 抱团股": top_monthly,
            "Bottom10 冷门股": bottom_monthly,
            "上证指数": sse_monthly,
        }
    )

    top10_monthly_detail = (
        df[df["证券代码"].isin(top10["证券代码"])]
        .groupby("月份")
        .agg(推荐次数=("证券代码", "size"), 月均收益=("当月涨跌幅(%)", "mean"))
        .reindex(MONTHS)
    )
    toptech_monthly_detail = (
        df[df["证券代码"].isin(top10_tech["证券代码"])]
        .groupby("月份")
        .agg(推荐次数=("证券代码", "size"), 月均收益=("当月涨跌幅(%)", "mean"))
        .reindex(MONTHS)
    )
    toptech_monthly_detail["下月收益"] = toptech_monthly_detail["月均收益"].shift(-1)
    crowded_months = toptech_monthly_detail[toptech_monthly_detail["推荐次数"] >= 10]
    crowded_next_return = float(crowded_months["下月收益"].dropna().mean()) if not crowded_months.empty else np.nan
    uncrowded_months = toptech_monthly_detail[toptech_monthly_detail["推荐次数"] < 10]
    uncrowded_next_return = float(uncrowded_months["下月收益"].dropna().mean()) if not uncrowded_months.empty else np.nan
    top10_mdd = max_drawdown(top10_monthly_detail["月均收益"])
    toptech_mdd = max_drawdown(toptech_monthly_detail["月均收益"])

    event_study = pd.DataFrame(
        [
            {
                "事件组": "Top10科技股拥挤月（推荐次数≥10）",
                "月份数": int(crowded_months.shape[0]),
                "当月平均收益": float(crowded_months["月均收益"].mean()),
                "下月平均收益": crowded_next_return,
            },
            {
                "事件组": "Top10科技股未拥挤月（推荐次数<10）",
                "月份数": int(uncrowded_months.shape[0]),
                "当月平均收益": float(uncrowded_months["月均收益"].mean()),
                "下月平均收益": uncrowded_next_return,
            },
        ]
    )

    reg_df = df.merge(
        style[["机构名称", "月份", "证券代码", "成长指数"]],
        on=["机构名称", "月份", "证券代码"],
        how="left",
    )
    reg_df["头部券商"] = (reg_df["梯队"] == "头部").astype(float)
    reg_df["腰部券商"] = (reg_df["梯队"] == "腰部").astype(float)
    reg_df["信息技术行业"] = (reg_df["Wind一级行业"] == "信息技术").astype(float)
    reg_df["抱团强度ln"] = np.log1p(reg_df["累计推荐次数_样本"])
    reg_df["成长指数标准化"] = (reg_df["成长指数"] - reg_df["成长指数"].mean()) / reg_df["成长指数"].std()
    month_dummies = pd.get_dummies(reg_df["月份"], prefix="月份", drop_first=True, dtype=float)
    reg_x = pd.concat(
        [
            reg_df[["头部券商", "腰部券商", "信息技术行业", "抱团强度ln", "成长指数标准化"]],
            month_dummies,
        ],
        axis=1,
    )
    regression = run_ols(reg_df["行业超额收益率(%)"], reg_x)
    key_vars = ["头部券商", "腰部券商", "信息技术行业", "抱团强度ln", "成长指数标准化"]
    regression["key_table"] = regression["table"][regression["table"]["变量"].isin(key_vars)].copy()

    style_summary = []
    for broker in BROKER_ORDER:
        g = style[style["机构名称"] == broker]
        shares = g["风格判定"].value_counts(normalize=True) * 100
        style_summary.append(
            {
                "机构名称": broker,
                "推荐记录数": len(g),
                "成长指数": g["成长指数"].mean(),
                "成长股占比": shares.get("成长", 0.0),
                "价值股占比": shares.get("价值", 0.0),
                "均衡占比": shares.get("均衡", 0.0),
                "PE中位数": g["市盈率PE"].replace([np.inf, -np.inf], np.nan).median(),
                "营收增长中位数": g["营收同比增长率%"].median(),
                "股利收益率均值": g["股利收益率%"].mean(),
            }
        )
    style_summary = pd.DataFrame(style_summary).set_index("机构名称").reindex(BROKER_ORDER)

    style_tier = []
    for tier in TIER_ORDER:
        g = style[style["梯队"] == tier]
        shares = g["风格判定"].value_counts(normalize=True) * 100
        style_tier.append(
            {
                "梯队": tier,
                "推荐记录数": len(g),
                "成长指数": g["成长指数"].mean(),
                "成长股占比": shares.get("成长", 0.0),
                "价值股占比": shares.get("价值", 0.0),
                "均衡占比": shares.get("均衡", 0.0),
            }
        )
    style_tier = pd.DataFrame(style_tier).set_index("梯队").reindex(TIER_ORDER)

    broker_monthly = (
        df.groupby(["机构名称", "月份"])["当月涨跌幅(%)"].mean().reset_index(name="月收益率(%)")
    )
    broker_pivot = broker_monthly.pivot(index="月份", columns="机构名称", values="月收益率(%)").reindex(MONTHS)[
        BROKER_ORDER
    ]
    benchmark_pivot = (
        index_monthly.pivot(index="月份", columns="指数", values="月收益率(%)")
        .reindex(MONTHS)[["上证指数", "深证成指", "创业板指"]]
    )

    portfolio_returns = pd.concat([broker_pivot, benchmark_pivot], axis=1)
    wealth = (1 + portfolio_returns / 100).cumprod() * INITIAL_CAPITAL
    portfolio_rows = []
    for name in portfolio_returns.columns:
        r = portfolio_returns[name].dropna()
        final_value = float((1 + r / 100).prod() * INITIAL_CAPITAL)
        portfolio_rows.append(
            {
                "名称": name,
                "月均收益率": float(r.mean()),
                "月度波动率": float(r.std(ddof=1)),
                "累计收益率": float(((1 + r / 100).prod() - 1) * 100),
                "期末资产": final_value,
                "收益金额": final_value - INITIAL_CAPITAL,
                "最大回撤": max_drawdown(r),
            }
        )
    portfolio_summary = pd.DataFrame(portfolio_rows).sort_values("累计收益率", ascending=False)

    six_avg = broker_pivot.mean(axis=1)
    cyb_monthly = benchmark_pivot["创业板指"]
    cyb_compare = pd.DataFrame({"六家券商平均": six_avg, "创业板指": cyb_monthly})
    cyb_compare["相对创业板"] = cyb_compare["六家券商平均"] - cyb_compare["创业板指"]

    return {
        "df": df,
        "index_monthly": index_monthly,
        "industry_monthly": industry_monthly,
        "broker_counts": broker_counts,
        "tier_counts": tier_counts,
        "industry": industry,
        "broker_top3": broker_top3,
        "stock_counts": stock_counts,
        "top10": top10,
        "bottom10": bottom10,
        "top10_tech": top10_tech,
        "once_count": once_count,
        "repeat_count": repeat_count,
        "repeat_records": repeat_records,
        "group_stats": group_stats,
        "top_bottom_monthly": top_bottom_monthly,
        "top10_monthly_detail": top10_monthly_detail,
        "toptech_monthly_detail": toptech_monthly_detail,
        "crowded_next_return": crowded_next_return,
        "uncrowded_next_return": uncrowded_next_return,
        "event_study": event_study,
        "regression": regression,
        "top10_mdd": top10_mdd,
        "toptech_mdd": toptech_mdd,
        "style_summary": style_summary,
        "style_tier": style_tier,
        "portfolio_returns": portfolio_returns,
        "cyb_compare": cyb_compare,
        "wealth": wealth,
        "portfolio_summary": portfolio_summary,
    }


def make_figures(analysis: dict) -> None:
    palette = REPORT_COLORS.copy()
    industry = analysis["industry"]
    broker_counts = analysis["broker_counts"]
    top_bottom_monthly = analysis["top_bottom_monthly"]
    group_stats = analysis["group_stats"]
    style_summary = analysis["style_summary"]
    wealth = analysis["wealth"]
    portfolio_summary = analysis["portfolio_summary"]
    cyb_compare = analysis["cyb_compare"]

    plt.style.use("default")
    configure_fonts()
    plt.rcParams.update(
        {
            "axes.edgecolor": palette["line"],
            "axes.labelcolor": palette["ink"],
            "axes.titlecolor": palette["navy"],
            "xtick.color": "#374151",
            "ytick.color": "#374151",
            "grid.color": palette["grid"],
            "grid.linewidth": 0.8,
            "grid.alpha": 1.0,
        }
    )

    def polish(ax, xgrid=False, ygrid=True):
        ax.set_facecolor("white")
        ax.grid(False)
        if xgrid:
            ax.grid(axis="x", color=palette["grid"], linewidth=0.8)
        if ygrid:
            ax.grid(axis="y", color=palette["grid"], linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(palette["line"])
        ax.spines["bottom"].set_color(palette["line"])
        ax.tick_params(length=0)

    def add_source(fig, text="资料来源：六大券商金股数据、AkShare、申万行业指数；作者整理"):
        fig.text(0.01, 0.01, text, fontsize=8.5, color=palette["gray"])

    # Investor-facing one-page dashboard.
    cyb_row = portfolio_summary[portfolio_summary["名称"] == "创业板指"].iloc[0]
    broker_rows = portfolio_summary[portfolio_summary["名称"].isin(BROKER_ORDER)]
    beat_cyb_count = int((broker_rows["累计收益率"] > cyb_row["累计收益率"]).sum())
    top10_tech_share = analysis["top10_tech"]["累计推荐次数"].sum() / analysis["top10"]["累计推荐次数"].sum() * 100
    cards = [
        ("样本口径", f"{len(analysis['df'])} 条推荐\n2025-05 至 2026-04"),
        ("金股整体", f"+{analysis['df']['行业超额收益率(%)'].mean():.2f}%\n平均行业超额"),
        ("强基准", f"+{cyb_row['累计收益率']:.1f}%\n创业板指累计收益"),
        ("跑赢创业板", f"{beat_cyb_count}/6 家\n只有最强组合胜出"),
        ("抱团科技", f"{top10_tech_share:.1f}%\nTop10 推荐来自信息技术"),
        ("拥挤风险", f"{analysis['toptech_mdd']:.1f}%\n抱团科技最大回撤"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(13.5, 5.8))
    card_colors = ["#f8fafc", "#fff7ed", "#eef2ff", "#ecfdf5", "#f0f9ff", "#fef2f2"]
    accent_colors = ["#334155", "#b45309", "#4f46e5", "#047857", "#0369a1", "#b91c1c"]
    for ax, (title, value), bg, ac in zip(axes.ravel(), cards, card_colors, accent_colors):
        ax.set_facecolor(bg)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#d1d5db")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.text(0.06, 0.78, title, transform=ax.transAxes, fontsize=14, fontweight="bold", color="#111827")
        ax.text(0.06, 0.25, value, transform=ax.transAxes, fontsize=19, fontweight="bold", color=ac, linespacing=1.35)
    fig.suptitle("投资者一页看懂：券商金股的收益来自哪里，风险藏在哪里", fontsize=18, fontweight="bold", y=1.02)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig0_investor_dashboard.png", dpi=FIG_DPI, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    index_cols = ["上证指数", "深证成指", "创业板指"]
    idx_wealth = (1 + analysis["portfolio_returns"][index_cols] / 100).cumprod() * 100
    colors_idx = {"上证指数": "#111827", "深证成指": "#0f766e", "创业板指": "#b91c1c"}
    for col in index_cols:
        axes[0].plot(idx_wealth.index, idx_wealth[col], marker="o", linewidth=2.4, color=colors_idx[col], label=col)
    axes[0].set_title("市场环境：创业板显著跑赢，上证不是最严苛基准")
    axes[0].set_ylabel("指数化净值（2025-05=100）")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend(frameon=False)
    polish(axes[0])

    cyb_compare.plot(kind="bar", ax=axes[1], color=["#2f6f9f", "#b91c1c", "#64748b"], width=0.78)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("六家券商平均月收益 vs 创业板指")
    axes[1].set_ylabel("月收益率 / 相对收益（%）")
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].legend(frameon=False, fontsize=9)
    polish(axes[1], ygrid=True)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_market_context.png", dpi=FIG_DPI)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    top_ind = industry.sort_values("推荐次数").tail(11)
    axes[0].barh(top_ind.index, top_ind["推荐次数"], color=palette["blue"])
    axes[0].set_title("行业推荐集中度")
    axes[0].set_xlabel("推荐记录数")
    polish(axes[0], xgrid=True, ygrid=False)
    for y, (idx, row) in enumerate(top_ind.iterrows()):
        axes[0].text(row["推荐次数"] + 3, y, f"{row['推荐占比']:.1f}%", va="center", fontsize=9)

    alpha_sorted = industry.sort_values("平均行业超额收益率")
    colors = [palette["red"] if v >= 0 else palette["gray"] for v in alpha_sorted["平均行业超额收益率"]]
    axes[1].barh(alpha_sorted.index, alpha_sorted["平均行业超额收益率"], color=colors)
    axes[1].axvline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("金股相对行业指数的平均超额收益")
    axes[1].set_xlabel("超额收益率（%）")
    polish(axes[1], xgrid=True, ygrid=False)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig1_industry_concentration.png", dpi=FIG_DPI)
    plt.close(fig)

    broker_industry_share = (
        analysis["df"]
        .pivot_table(index="机构名称", columns="Wind一级行业", values="证券代码", aggfunc="count", fill_value=0)
        .reindex(BROKER_ORDER)
    )
    broker_industry_share = broker_industry_share.div(broker_industry_share.sum(axis=1), axis=0) * 100
    top_cols = industry.head(8).index.tolist()
    heat = broker_industry_share[top_cols]
    fig, ax = plt.subplots(figsize=(11, 4.9))
    im = ax.imshow(heat.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=max(45, heat.values.max()))
    ax.set_xticks(np.arange(len(top_cols)))
    ax.set_xticklabels(top_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(BROKER_ORDER)))
    ax.set_yticklabels(BROKER_ORDER)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax.text(j, i, f"{heat.iloc[i, j]:.0f}%", ha="center", va="center", fontsize=8, color="#111827")
    ax.set_title("各券商在主要行业上的推荐占比")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="占比（%）")
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig2_broker_industry_heatmap.png", dpi=FIG_DPI)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    stats = group_stats.set_index("分组")
    x = np.arange(2)
    axes[0].bar(x - 0.18, stats["平均收益率"], width=0.35, label="平均收益率", color=palette["green"])
    axes[0].bar(x + 0.18, stats["相对上证Alpha"], width=0.35, label="相对上证 Alpha", color=palette["gold"])
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(stats.index)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("%")
    axes[0].set_title("Top10 抱团股与 Bottom10 冷门股收益对比")
    axes[0].legend(frameon=False)
    polish(axes[0])
    for container in axes[0].containers:
        axes[0].bar_label(container, fmt="%.1f%%", padding=3, fontsize=9)

    top_bottom_monthly.plot(ax=axes[1], marker="o", linewidth=2)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("分组月度平均收益")
    axes[1].set_ylabel("%")
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].legend(frameon=False)
    polish(axes[1])
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3_top_bottom.png", dpi=FIG_DPI)
    plt.close(fig)

    # Herding detail: where the repeated recommendations are concentrated and how crowded tech behaves.
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    scatter = analysis["top10"].copy()
    scatter["平均收益"] = scatter["证券代码"].map(
        analysis["df"].groupby("证券代码")["当月涨跌幅(%)"].mean().to_dict()
    )
    scatter["行业"] = scatter["证券代码"].map(
        analysis["df"].drop_duplicates("证券代码").set_index("证券代码")["Wind一级行业"].to_dict()
    )
    industry_color = {
        "信息技术": "#2563eb",
        "材料": "#b45309",
        "医疗保健": "#059669",
        "可选消费": "#7c3aed",
    }
    colors = [industry_color.get(v, "#64748b") for v in scatter["行业"]]
    axes[0].scatter(scatter["累计推荐次数"], scatter["平均收益"], s=scatter["累计推荐次数"] * 26, c=colors, alpha=0.78, edgecolor="white", linewidth=1.2)
    for _, row in scatter.iterrows():
        axes[0].text(row["累计推荐次数"] + 0.35, row["平均收益"], row["证券简称"], fontsize=9, va="center")
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("抱团股：推荐越密集，越偏科技和成长")
    axes[0].set_xlabel("累计推荐次数")
    axes[0].set_ylabel("推荐当月平均收益（%）")
    polish(axes[0])

    toptech = analysis["toptech_monthly_detail"]
    axes[1].bar(toptech.index, toptech["推荐次数"], color="#dbeafe", label="推荐次数")
    ax2 = axes[1].twinx()
    ax2.plot(toptech.index, toptech["月均收益"], color="#b91c1c", marker="o", linewidth=2.4, label="抱团科技月均收益")
    ax2.axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("抱团科技股：热度上升后收益波动同步放大")
    axes[1].set_ylabel("推荐次数")
    ax2.set_ylabel("月均收益（%）")
    axes[1].tick_params(axis="x", rotation=35)
    h1, l1 = axes[1].get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    axes[1].legend(h1 + h2, l1 + l2, frameon=False, loc="upper left")
    polish(axes[1])
    ax2.grid(False)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig3b_herding_tech.png", dpi=FIG_DPI)
    plt.close(fig)

    # Bonus analysis: regression coefficients and event-study comparison.
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))
    reg_key = analysis["regression"]["key_table"].copy()
    reg_key["变量"] = pd.Categorical(
        reg_key["变量"],
        ["头部券商", "腰部券商", "信息技术行业", "抱团强度ln", "成长指数标准化"],
        ordered=True,
    )
    reg_key = reg_key.sort_values("变量")
    y_pos = np.arange(len(reg_key))
    coef_colors = ["#b91c1c" if v > 0 else "#64748b" for v in reg_key["系数"]]
    axes[0].barh(y_pos, reg_key["系数"], color=coef_colors)
    axes[0].errorbar(
        reg_key["系数"],
        y_pos,
        xerr=1.96 * reg_key["标准误"],
        fmt="none",
        ecolor="#111827",
        elinewidth=1.1,
        capsize=3,
    )
    axes[0].axvline(0, color="#111827", linewidth=0.8)
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(reg_key["变量"])
    axes[0].set_xlabel("对行业超额收益的边际影响（百分点）")
    axes[0].set_title("回归：控制月份后，哪些因素解释超额收益")
    for i, row in enumerate(reg_key.itertuples()):
        axes[0].text(row.系数 + (0.15 if row.系数 >= 0 else -0.15), i, f"t={row.t值:.1f}", va="center", ha="left" if row.系数 >= 0 else "right", fontsize=9)
    polish(axes[0], xgrid=True, ygrid=False)

    event = analysis["event_study"].set_index("事件组")
    event[["当月平均收益", "下月平均收益"]].plot(
        kind="bar",
        ax=axes[1],
        color=["#2f6f9f", "#b91c1c"],
        width=0.72,
    )
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("事件研究：Top10科技股拥挤后，次月收益转弱")
    axes[1].set_ylabel("平均收益率（%）")
    axes[1].tick_params(axis="x", rotation=15)
    axes[1].legend(frameon=False)
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt="%.1f%%", padding=3, fontsize=9)
    polish(axes[1])
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig6_bonus_reg_event.png", dpi=FIG_DPI)
    plt.close(fig)

    style_plot = style_summary[["成长股占比", "价值股占比", "均衡占比"]].copy()
    fig, ax = plt.subplots(figsize=(11, 5))
    bottom = np.zeros(len(style_plot))
    colors = [palette["red"], palette["blue"], palette["gray"]]
    for col, color in zip(style_plot.columns, colors):
        ax.bar(style_plot.index, style_plot[col], bottom=bottom, label=col.replace("占比", ""), color=color)
        bottom += style_plot[col].values
    ax2 = ax.twinx()
    ax2.plot(style_summary.index, style_summary["成长指数"], color="#111827", marker="o", linewidth=2.2, label="成长指数")
    ax.set_ylim(0, 100)
    ax2.set_ylim(50, max(76, style_summary["成长指数"].max() + 2))
    ax.set_ylabel("风格占比（%）")
    ax2.set_ylabel("成长指数")
    ax.set_title("六家券商推荐风格：成长/价值/均衡")
    ax.tick_params(axis="x", rotation=20)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, loc="upper left", ncol=4)
    polish(ax)
    ax2.grid(False)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig4_style.png", dpi=FIG_DPI)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5))
    wealth_plot = wealth / 10_000
    line_colors = ["#b23a48", "#2f6f9f", "#6b5b95", "#3f7d5c", "#9a6a2f", "#64748b", "#111827", "#0f766e", "#b91c1c"]
    for i, col in enumerate(wealth_plot.columns):
        axes[0].plot(wealth_plot.index, wealth_plot[col], marker="o", linewidth=2, label=col, color=line_colors[i])
    axes[0].set_title("100 万元等权月度跟投：期末资产曲线")
    axes[0].set_ylabel("资产规模（万元）")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].legend(frameon=False, ncol=2, fontsize=9)
    polish(axes[0])

    ordered = portfolio_summary.set_index("名称")
    bars = axes[1].barh(ordered.index[::-1], ordered["累计收益率"][::-1], color=palette["red"])
    axes[1].axvline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("12 个月累计收益率排名")
    axes[1].set_xlabel("累计收益率（%）")
    axes[1].bar_label(bars, fmt="%.1f%%", padding=3, fontsize=9)
    polish(axes[1], xgrid=True, ygrid=False)
    add_source(fig)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig5_portfolio.png", dpi=FIG_DPI)
    plt.close(fig)


def build_markdown(meta: dict, analysis: dict) -> str:
    df = analysis["df"]
    industry = analysis["industry"]
    broker_counts = analysis["broker_counts"]
    tier_counts = analysis["tier_counts"]
    top10 = analysis["top10"]
    bottom10 = analysis["bottom10"]
    group_stats = analysis["group_stats"]
    style_summary = analysis["style_summary"]
    style_tier = analysis["style_tier"]
    portfolio_summary = analysis["portfolio_summary"]

    cr1 = industry["推荐次数"].head(1).sum() / len(df) * 100
    cr3 = industry["推荐次数"].head(3).sum() / len(df) * 100
    cr5 = industry["推荐次数"].head(5).sum() / len(df) * 100
    overall_gold = df["当月涨跌幅(%)"].mean()
    overall_ind = df["行业指数收益率(%)"].mean()
    overall_alpha = df["行业超额收益率(%)"].mean()
    top_stats = group_stats[group_stats["分组"] == "Top10 抱团股"].iloc[0]
    bottom_stats = group_stats[group_stats["分组"] == "Bottom10 冷门股"].iloc[0]
    top10_share = int(top10["累计推荐次数"].sum()) / len(df) * 100
    once_share_unique = analysis["once_count"] / analysis["stock_counts"].shape[0] * 100

    broker_rows = []
    for broker, row in broker_counts.iterrows():
        broker_rows.append(
            [
                broker,
                TIER_MAP[broker],
                int(row["推荐记录数"]),
                int(row["唯一股票数"]),
                fmt_pct(row["平均当月收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    industry_rows = []
    for idx, row in industry.iterrows():
        industry_rows.append(
            [
                idx,
                int(row["推荐次数"]),
                fmt_pct(row["推荐占比"], 1),
                fmt_pct(row["金股平均收益率"], 2, True),
                fmt_pct(row["行业指数收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    tier_rows = []
    for tier, row in tier_counts.iterrows():
        tier_rows.append(
            [
                tier,
                int(row["推荐记录数"]),
                int(row["唯一股票数"]),
                fmt_pct(row["平均当月收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    top_rows = []
    for _, row in top10.iterrows():
        subset = df[df["证券代码"] == row["证券代码"]]
        top_rows.append(
            [
                row["证券代码"],
                row["证券简称"],
                int(row["累计推荐次数"]),
                subset["Wind一级行业"].mode().iat[0],
                fmt_pct(subset["当月涨跌幅(%)"].mean(), 2, True),
            ]
        )

    bottom_rows = []
    for _, row in bottom10.iterrows():
        subset = df[df["证券代码"] == row["证券代码"]]
        bottom_rows.append(
            [
                row["证券代码"],
                row["证券简称"],
                int(row["累计推荐次数"]),
                subset["Wind一级行业"].mode().iat[0],
                fmt_pct(subset["当月涨跌幅(%)"].mean(), 2, True),
            ]
        )

    group_rows = []
    for _, row in group_stats.drop(columns=["monthly"]).iterrows():
        group_rows.append(
            [
                row["分组"],
                int(row["股票数"]),
                int(row["推荐记录数"]),
                int(row["有效月份数"]),
                fmt_pct(row["平均收益率"], 2, True),
                fmt_pct(row["相对上证Alpha"], 2, True),
                fmt_pct(row["正收益占比"], 1),
                fmt_pct(row["跑赢上证占比"], 1),
            ]
        )

    style_rows = []
    for broker, row in style_summary.iterrows():
        style_rows.append(
            [
                broker,
                int(row["推荐记录数"]),
                fmt_num(row["成长指数"], 1),
                fmt_pct(row["成长股占比"], 1),
                fmt_pct(row["价值股占比"], 1),
                fmt_num(row["PE中位数"], 1),
                fmt_pct(row["营收增长中位数"], 1, True),
                fmt_pct(row["股利收益率均值"], 2),
            ]
        )

    style_tier_rows = []
    for tier, row in style_tier.iterrows():
        style_tier_rows.append(
            [
                tier,
                int(row["推荐记录数"]),
                fmt_num(row["成长指数"], 1),
                fmt_pct(row["成长股占比"], 1),
                fmt_pct(row["价值股占比"], 1),
                fmt_pct(row["均衡占比"], 1),
            ]
        )

    portfolio_rows = []
    for _, row in portfolio_summary.iterrows():
        portfolio_rows.append(
            [
                row["名称"],
                fmt_pct(row["累计收益率"], 2, True),
                fmt_wan(row["期末资产"]),
                fmt_wan(row["收益金额"]),
                fmt_pct(row["月均收益率"], 2, True),
                fmt_pct(row["月度波动率"], 2),
                fmt_pct(row["最大回撤"], 2, True),
            ]
        )

    best = portfolio_summary.iloc[0]
    sse = portfolio_summary[portfolio_summary["名称"] == "上证指数"].iloc[0]
    szse = portfolio_summary[portfolio_summary["名称"] == "深证成指"].iloc[0]
    brokers_above_szse = portfolio_summary[
        portfolio_summary["名称"].isin(BROKER_ORDER) & (portfolio_summary["累计收益率"] > szse["累计收益率"])
    ]["名称"].tolist()
    brokers_above_sse = portfolio_summary[
        portfolio_summary["名称"].isin(BROKER_ORDER) & (portfolio_summary["累计收益率"] > sse["累计收益率"])
    ]["名称"].tolist()

    md = f"""# 券商金股是“指路明灯”还是“韭菜指南”？

## 摘要

本文面向普通投资者，检验 2025 年 5 月初至 2026 年 4 月底这 12 个月内，六家券商月度金股的行业偏好、抱团效应、成长/价值风格以及等权跟投收益。原始合并表覆盖 2025-04 至 2026-04 共 {meta['raw_all_records']} 条记录，本文剔除 2025-04 的 71 条记录后，保留 {meta['filtered_records']} 条推荐、{meta['unique_stocks']} 只股票、{meta['industries']} 个 Wind 一级行业。

结论先行：券商金股不是可以无脑照买的清单，但也不能简单视作“反向指标”。12 个月里六家券商组合均跑赢上证指数，且金股平均相对行业指数有 {fmt_pct(overall_alpha, 2, True)} 的超额收益；但推荐高度集中在信息技术、工业、材料，Top10 抱团股贡献了很强收益，也带来了明显风格拥挤和回撤风险。更大的券商整体研究能力更强这一判断有一定数据支持，头部券商行业超额收益高于腰部和尾部，但单家层面并不严格单调。

## 1. 决策主体与研究目标

本报告是为个人投资者和小型投资机构写的。他们经常面对一个实际问题：每月券商发布“金股”名单后，是否应该照单买入、挑头部券商买入，或者避开被多家机构同时推荐的热门股。

研究目标不是证明某家券商永远更好，而是把“金股含金量”拆成四个可以观察的事实：推荐是否集中在少数行业，机构是否抱团推荐热门股，六家券商偏成长还是偏价值，以及 100 万元月度等权跟投到底能赚多少钱、能否跑赢上证指数和深证成指。

## 2. 市场背景

卖方研报长期面临两种评价：支持者认为券商研究能把产业趋势、盈利预测和估值变化系统化；怀疑者则认为研报大多给出买入或持有建议，存在利益协同、抱团推荐和追逐热门赛道的问题。金股名单正好把这种争议集中呈现出来，因为它把研究观点压缩成每月可交易的股票清单。

本次研究按照头部（中信建投证券、华泰证券）、腰部（招商证券、平安证券）、尾部（天风证券、开源证券）三组券商比较。投资者真正需要回答的是：大券商是否更值得跟？多家机构反复推荐的股票是否更可靠？如果收益来自同一类成长风格和热门行业，未来市场风格变化时风险会不会被放大？

## 3. 数据来源与处理

数据主要来自 `六大券商合并数据.xlsx`、维度二的 Top/Bottom 分组结果、维度三的风格指标表，以及维度四的收益率分析思路。市场基准采用 AkShare 获取的上证指数和深证成指日收盘价，并按月末收盘计算月收益；行业基准采用申万一级行业指数，并按组员 notebook 中的 Wind 行业到申万行业映射做简单平均。

关键处理如下：

- 时间口径：只保留 2025-05 至 2026-04，明确为 12 个月；剔除原始表中 2025-04 的 71 条推荐记录。
- 推荐口径：行业偏好、收益率和风格分析均按“推荐记录”统计，同一只股票被多家券商或多个月推荐会重复计入，这符合投资者每月看名单决策的场景。
- 组合口径：每家券商每月投入当期账户资产，按当月金股数量等权买入，月末按当月涨跌幅结算并滚动到下月；不考虑交易成本、冲击成本、税费和停牌流动性。
- 风格口径：沿用维度三表中的成长指数，综合 PE 百分位、营收增长百分位、低分红百分位；指数越高越偏成长。

## 4. 统计事实

### 4.1 样本规模与行业集中度

{md_table(broker_rows, ["券商", "梯队", "推荐记录数", "唯一股票数", "平均当月收益", "平均行业超额收益"])}

头部券商推荐记录数为 {int(tier_counts.loc['头部', '推荐记录数'])} 条，腰部为 {int(tier_counts.loc['腰部', '推荐记录数'])} 条，尾部为 {int(tier_counts.loc['尾部', '推荐记录数'])} 条。记录数最多的是天风证券，这说明“券商规模大”不等于“推荐数量多”；真正需要比较的是推荐后的收益和风险。

{md_table(tier_rows, ["梯队", "推荐记录数", "唯一股票数", "平均当月收益", "平均行业超额收益"])}

从行业超额收益看，头部券商为 {fmt_pct(tier_counts.loc['头部', '平均行业超额收益率'], 2, True)}，高于腰部的 {fmt_pct(tier_counts.loc['腰部', '平均行业超额收益率'], 2, True)} 和尾部的 {fmt_pct(tier_counts.loc['尾部', '平均行业超额收益率'], 2, True)}。这支持“头部研究能力更强”的方向性判断，但差距并没有大到可以忽视单家券商和市场风格的影响。

{md_table(industry_rows, ["行业", "推荐次数", "推荐占比", "金股平均收益", "行业指数收益", "平均超额收益"])}

{image_md("fig1_industry_concentration.png", "行业集中度与行业超额收益")}

行业集中度很高：信息技术单一行业占 {fmt_pct(cr1, 1)}，前三大行业信息技术、工业、材料合计占 {fmt_pct(cr3, 1)}，前五大行业占 {fmt_pct(cr5, 1)}。金股整体平均收益为 {fmt_pct(overall_gold, 2, True)}，对应行业指数平均为 {fmt_pct(overall_ind, 2, True)}，平均行业超额收益为 {fmt_pct(overall_alpha, 2, True)}；但可选消费和房地产相对行业指数为负，说明不是所有被重点覆盖的行业都能产生超额收益。

{md_table(analysis['broker_top3'], ["券商", "前三大偏好行业及占比", "推荐记录数"])}

{image_md("fig2_broker_industry_heatmap.png", "券商行业偏好热力图")}

六家券商都把信息技术放在核心位置，招商证券的信息技术占比最高，华泰证券则在材料、信息技术和工业之间更均衡。尾部券商并非简单复制头部，天风证券在可选消费占比更高，开源证券仍以信息技术、工业、材料为主。

### 4.2 抱团推荐：Top10 热门股与 Bottom10 冷门股

12 个月内共有 {analysis['stock_counts'].shape[0]} 只股票被推荐，其中只出现 1 次的股票有 {analysis['once_count']} 只，占唯一股票数的 {fmt_pct(once_share_unique, 1)}。如果直接抽取“最低频”股票，样本会被大量一次性推荐标的支配；因此收益对比采用“至少被推荐 2 次”中的最低 10 只作为 Bottom10 冷门股，同时保留一次性推荐比例作为冷门分布事实。

{md_table(top_rows, ["代码", "简称", "累计推荐次数", "主要行业", "推荐当月平均收益"])}

Top10 抱团股合计出现 {int(top10['累计推荐次数'].sum())} 次，占全部推荐记录的 {fmt_pct(top10_share, 1)}。其中中际旭创、海光信息、紫金矿业、百济神州等集中在信息技术、材料和医疗保健，说明抱团并不是随机发生，而是围绕当期热门产业线索形成。

{md_table(bottom_rows, ["代码", "简称", "累计推荐次数", "主要行业", "推荐当月平均收益"])}

{md_table(group_rows, ["分组", "股票数", "推荐记录数", "有效月份数", "平均收益率", "相对上证Alpha", "正收益占比", "跑赢上证占比"])}

{image_md("fig3_top_bottom.png", "Top10与Bottom10收益对比")}

Top10 抱团股的推荐当月平均收益为 {fmt_pct(top_stats['平均收益率'], 2, True)}，相对上证 Alpha 为 {fmt_pct(top_stats['相对上证Alpha'], 2, True)}；Bottom10 冷门股平均收益为 {fmt_pct(bottom_stats['平均收益率'], 2, True)}，相对上证 Alpha 为 {fmt_pct(bottom_stats['相对上证Alpha'], 2, True)}。这说明研究期内“抱团热门股”确实比冷门股有效，但月度曲线也显示 2026-02 和 2026-03 Top10 出现较大回撤，抱团策略的风险在于风格反转时损失会同步放大。

### 4.3 风格倾向：成长股还是价值股？

{md_table(style_rows, ["券商", "记录数", "成长指数", "成长股占比", "价值股占比", "PE中位数", "营收增长中位数", "股利收益率均值"])}

{md_table(style_tier_rows, ["梯队", "记录数", "成长指数", "成长股占比", "价值股占比", "均衡占比"])}

{image_md("fig4_style.png", "券商推荐风格")}

六家券商整体明显偏成长，所有券商成长股占比都超过 60%，招商证券最高，达到 {fmt_pct(style_summary.loc['招商证券', '成长股占比'], 1)}。成长风格并不等于低风险：这类股票通常 PE 更高、分红更低、业绩增长预期更强，一旦市场从成长切向价值或红利，金股名单的历史收益可能难以延续。

### 4.4 100 万元等权跟投收益

{md_table(portfolio_rows, ["名称", "累计收益率", "期末资产", "收益金额", "月均收益率", "月度波动率", "最大回撤"])}

{image_md("fig5_portfolio.png", "组合跟投收益")}

以 100 万元本金逐月等权跟投，华泰证券期末资产最高，为 {fmt_wan(best['期末资产'])}，累计收益 {fmt_pct(best['累计收益率'], 2, True)}。六家券商都跑赢上证指数（上证期末 {fmt_wan(sse['期末资产'])}，累计 {fmt_pct(sse['累计收益率'], 2, True)}），但只有 {len(brokers_above_szse)} 家跑赢深证成指（{', '.join(brokers_above_szse)}），天风证券略低于深证成指。由此看，金股组合在强成长行情中可以带来收益，但“跑赢宽基”并不是所有券商、所有基准下都稳健成立。

## 5. 初步结论

第一，券商金股不是“无脑跟投”的安全清单。行业 CR3 达到 {fmt_pct(cr3, 1)}，成长股占比普遍超过 60%，说明投资者买到的不只是个股观点，更是信息技术、工业、材料和成长风格的集中暴露。

第二，头部券商整体更强，但不是简单的规模决定论。头部券商行业超额收益最高，华泰证券 100 万元跟投收益也排名第一；但招商证券作为腰部券商排名第二，开源证券作为尾部券商也高于平安证券和天风证券，说明单家研究风格和市场阶段同样重要。

第三，抱团推荐在本研究期内有效，但也最需要风险提示。Top10 抱团股平均收益显著高于 Bottom10 冷门股，不过这种优势与 2025-2026 年成长和科技链行情高度相关，不能直接外推为“机构越抱团越安全”。

因此，本报告对投资者的建议是：券商金股可以作为观察产业趋势和机构共识的信号，但不应作为直接买入指令。更稳妥的使用方式是看清它暴露在哪些行业、是否与自己的持仓重复、推荐是否已经过度拥挤，再结合估值、业绩和风险承受能力决定是否参与。

## 6. 局限性说明

- 样本只覆盖 12 个月，且这一阶段 A 股成长风格和科技链表现较强，结论可能带有阶段性。
- 组合回测未计入交易成本、印花税、滑点、停牌、流动性约束和真实调仓时点差异，实际收益会低于理想等权组合。
- 行业指数采用 Wind 到申万行业的近似映射，适合比较方向，不等同于精确的成分股行业基准。
- Bottom10 冷门股存在大量同频并列，本文采用“至少推荐 2 次”的最低频股票以减少随机抽样，但仍需要更长样本检验稳健性。
- 风格指标依赖 2025 年年报与静态估值，无法完全反映推荐当月的盈利预期修正和估值切换。

## 附：复现方式

在本目录运行以下命令可重新生成报告、图表和导出文件：

```bash
/Users/wenrt/Anaconda3/anaconda3/bin/python scripts/build_report.py
```
"""
    return md


def build_markdown_v2(meta: dict, analysis: dict) -> str:
    """Investor-facing research-report version."""
    df = analysis["df"]
    industry = analysis["industry"]
    broker_counts = analysis["broker_counts"]
    tier_counts = analysis["tier_counts"]
    top10 = analysis["top10"]
    bottom10 = analysis["bottom10"]
    top10_tech = analysis["top10_tech"]
    group_stats = analysis["group_stats"]
    style_summary = analysis["style_summary"]
    style_tier = analysis["style_tier"]
    portfolio_summary = analysis["portfolio_summary"]
    cyb_compare = analysis["cyb_compare"]

    cr1 = industry["推荐次数"].head(1).sum() / len(df) * 100
    cr3 = industry["推荐次数"].head(3).sum() / len(df) * 100
    cr5 = industry["推荐次数"].head(5).sum() / len(df) * 100
    overall_gold = df["当月涨跌幅(%)"].mean()
    overall_ind = df["行业指数收益率(%)"].mean()
    overall_alpha = df["行业超额收益率(%)"].mean()
    once_share_unique = analysis["once_count"] / analysis["stock_counts"].shape[0] * 100
    repeat_share_records = analysis["repeat_records"] / len(df) * 100
    top10_share = int(top10["累计推荐次数"].sum()) / len(df) * 100
    top10_tech_share_top10 = int(top10_tech["累计推荐次数"].sum()) / int(top10["累计推荐次数"].sum()) * 100
    top10_tech_share_all = int(top10_tech["累计推荐次数"].sum()) / len(df) * 100

    top_stats = group_stats[group_stats["分组"] == "Top10 抱团股"].iloc[0]
    bottom_stats = group_stats[group_stats["分组"] == "Bottom10 冷门股"].iloc[0]
    sse = portfolio_summary[portfolio_summary["名称"] == "上证指数"].iloc[0]
    szse = portfolio_summary[portfolio_summary["名称"] == "深证成指"].iloc[0]
    cyb = portfolio_summary[portfolio_summary["名称"] == "创业板指"].iloc[0]
    best = portfolio_summary.iloc[0]
    broker_perf = portfolio_summary[portfolio_summary["名称"].isin(BROKER_ORDER)].copy()
    beat_cyb = broker_perf[broker_perf["累计收益率"] > cyb["累计收益率"]]["名称"].tolist()
    beat_sse = broker_perf[broker_perf["累计收益率"] > sse["累计收益率"]]["名称"].tolist()
    beat_szse = broker_perf[broker_perf["累计收益率"] > szse["累计收益率"]]["名称"].tolist()
    under_cyb_months = int((cyb_compare["相对创业板"] < 0).sum())
    worst_cyb_month = cyb_compare["相对创业板"].idxmin()
    best_cyb_month = cyb_compare["相对创业板"].idxmax()

    broker_rows = []
    for broker, row in broker_counts.iterrows():
        broker_rows.append(
            [
                broker,
                TIER_MAP[broker],
                int(row["推荐记录数"]),
                int(row["唯一股票数"]),
                fmt_pct(row["平均当月收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    tier_rows = []
    for tier, row in tier_counts.iterrows():
        tier_rows.append(
            [
                tier,
                int(row["推荐记录数"]),
                int(row["唯一股票数"]),
                fmt_pct(row["平均当月收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    tier_design_rows = [
        [
            "头部",
            "中信建投证券、华泰证券",
            "代表综合实力、研究资源和机构客户覆盖更强的券商；用来检验“排名越前研究越强”的市场直觉。",
            "两家公司在证监会 2020 年公开分类结果中均为 AA；2024 年上市券商财务规模和盈利能力也处于前列。",
        ],
        [
            "腰部",
            "招商证券、平安证券",
            "代表大型/中型综合券商的中间对照组；不是弱券商，而是用来观察非最头部研究资源能否复制超额收益。",
            "两家公司在证监会 2020 年公开分类结果中为 AA，但本作业按研究样本设计将其放入中间梯队。",
        ],
        [
            "尾部",
            "天风证券、开源证券",
            "代表中小或特色券商；用来观察研究资源较少时，是否通过差异化行业覆盖获得收益。",
            "证监会 2020 年公开分类结果中，天风证券为 A、开源证券为 BB，和前两组形成监管评价与规模上的梯度。",
        ],
    ]

    market_rows = []
    for name in ["创业板指", "深证成指", "上证指数"]:
        row = portfolio_summary[portfolio_summary["名称"] == name].iloc[0]
        market_rows.append(
            [
                name,
                fmt_pct(row["累计收益率"], 2, True),
                fmt_pct(row["月均收益率"], 2, True),
                fmt_pct(row["月度波动率"], 2),
                fmt_pct(row["最大回撤"], 2, True),
                "科技成长强基准" if name == "创业板指" else "宽基参照",
            ]
        )

    industry_rows = []
    for idx, row in industry.iterrows():
        industry_rows.append(
            [
                idx,
                int(row["推荐次数"]),
                fmt_pct(row["推荐占比"], 1),
                fmt_pct(row["金股平均收益率"], 2, True),
                fmt_pct(row["行业指数收益率"], 2, True),
                fmt_pct(row["平均行业超额收益率"], 2, True),
            ]
        )

    broker_top3_rows = []
    for broker in BROKER_ORDER:
        shares = df[df["机构名称"] == broker]["Wind一级行业"].value_counts(normalize=True).head(3) * 100
        broker_top3_rows.append(
            [
                broker,
                "、".join([f"{idx} {value:.1f}%" for idx, value in shares.items()]),
                fmt_pct(shares.sum(), 1),
            ]
        )

    top_rows = []
    for _, row in top10.iterrows():
        subset = df[df["证券代码"] == row["证券代码"]]
        industry_name = subset["Wind一级行业"].mode().iat[0]
        top_rows.append(
            [
                row["证券代码"],
                row["证券简称"],
                int(row["累计推荐次数"]),
                industry_name,
                "是" if industry_name == "信息技术" else "否",
                fmt_pct(subset["当月涨跌幅(%)"].mean(), 2, True),
            ]
        )

    bottom_rows = []
    for _, row in bottom10.iterrows():
        subset = df[df["证券代码"] == row["证券代码"]]
        bottom_rows.append(
            [
                row["证券代码"],
                row["证券简称"],
                int(row["累计推荐次数"]),
                subset["Wind一级行业"].mode().iat[0],
                fmt_pct(subset["当月涨跌幅(%)"].mean(), 2, True),
            ]
        )

    group_rows = []
    for _, row in group_stats.drop(columns=["monthly"]).iterrows():
        group_rows.append(
            [
                row["分组"],
                int(row["股票数"]),
                int(row["推荐记录数"]),
                int(row["有效月份数"]),
                fmt_pct(row["平均收益率"], 2, True),
                fmt_pct(row["相对上证Alpha"], 2, True),
                fmt_pct(row["正收益占比"], 1),
                fmt_pct(row["跑赢上证占比"], 1),
            ]
        )

    crowded_rows = []
    toptech = analysis["toptech_monthly_detail"].copy()
    for month, row in toptech.iterrows():
        if pd.notna(row["推荐次数"]):
            crowded_rows.append(
                [
                    month,
                    int(row["推荐次数"]),
                    fmt_pct(row["月均收益"], 2, True),
                    fmt_pct(row["下月收益"], 2, True),
                ]
            )

    style_rows = []
    for broker, row in style_summary.iterrows():
        style_rows.append(
            [
                broker,
                int(row["推荐记录数"]),
                fmt_num(row["成长指数"], 1),
                fmt_pct(row["成长股占比"], 1),
                fmt_pct(row["价值股占比"], 1),
                fmt_num(row["PE中位数"], 1),
                fmt_pct(row["营收增长中位数"], 1, True),
                fmt_pct(row["股利收益率均值"], 2),
            ]
        )

    style_tier_rows = []
    for tier, row in style_tier.iterrows():
        style_tier_rows.append(
            [
                tier,
                int(row["推荐记录数"]),
                fmt_num(row["成长指数"], 1),
                fmt_pct(row["成长股占比"], 1),
                fmt_pct(row["价值股占比"], 1),
                fmt_pct(row["均衡占比"], 1),
            ]
        )

    portfolio_rows = []
    for _, row in portfolio_summary.iterrows():
        portfolio_rows.append(
            [
                row["名称"],
                fmt_pct(row["累计收益率"], 2, True),
                fmt_wan(row["期末资产"]),
                fmt_wan(row["收益金额"]),
                fmt_pct(row["月均收益率"], 2, True),
                fmt_pct(row["月度波动率"], 2),
                fmt_pct(row["最大回撤"], 2, True),
            ]
        )

    cyb_monthly_rows = []
    for month, row in cyb_compare.iterrows():
        cyb_monthly_rows.append(
            [
                month,
                fmt_pct(row["六家券商平均"], 2, True),
                fmt_pct(row["创业板指"], 2, True),
                fmt_pct(row["相对创业板"], 2, True),
                "跑赢" if row["相对创业板"] > 0 else "跑输",
            ]
        )

    framework_rows = [
        ["1. 决策主体与研究目标", "第 1 节", "说明报告面向个人投资者/小型机构，回答金股能否跟投、头部是否更强、抱团是否有风险。"],
        ["2. 政策/市场背景", "第 2-3 节", "补充资本市场新“国九条”、券商分类评价制度、科技成长牛市和创业板强基准。"],
        ["3. 数据来源与处理", "第 4 节", "说明数据来源、12 个月清洗口径、组合收益、行业基准、风格指标和现实交易差异。"],
        ["4. 统计事实", "第 5-8 节", "覆盖规模分布、行业结构、月度趋势、梯队对比、抱团对比、创业板基准对比。"],
        ["5. 初步结论", "第 9 节", "用数据回答“金股有效吗、谁受影响、还有什么没回答”。"],
        ["6. 局限性说明", "第 13 节", "说明数据、方法和适用范围限制。"],
        ["7. 加分项", "第 10 节", "新增回归分析和事件研究，检验收益来源与拥挤风险。"],
    ]

    policy_rows = [
        [
            "国务院：资本市场新“国九条”",
            "2024-04-12",
            "“加强监管、防范风险、推动资本市场高质量发展”",
            "政策目标是提高上市公司质量、强化中介机构责任、保护投资者，研究金股是否有真实投资价值正好对应这一背景。",
        ],
        [
            "证监会：修改《证券公司分类监管规定》的决定",
            "2025-08-22 起施行",
            "“调整为《证券公司分类评价规定》”",
            "券商分类评价强调合规、风控和业务发展，说明券商分层不是拍脑袋，而是监管和市场都会关注的能力差异。",
        ],
        [
            "证监会：2020 年证券公司分类结果",
            "2020-08-26",
            "“不是对证券公司资信状况及等级的评价”",
            "本文只把公开分类结果作为研究分层参考，不把它当作投资评级。",
        ],
    ]

    indicator_rows = [
        ["行业集中度", "CR1/CR3/CR5", "衡量推荐是否集中在少数热门行业，直接对应“是否偏好热门赛道”。"],
        ["行业超额收益", "金股当月收益 - 对应行业指数月收益", "检验券商是否在行业内部有选股能力，而不只是买对行业。"],
        ["抱团强度", "单只股票 12 个月累计推荐次数、Top10 推荐占比", "衡量机构是否反复推荐同一批热门股。"],
        ["风格指标", "成长指数、成长股占比、价值股占比、PE/营收/分红", "判断券商推荐偏成长还是偏价值。"],
        ["组合收益", "100 万元本金，每月按当月金股等权买入并滚动复利", "模拟投资者实际跟投体验。"],
        ["强基准超额", "组合收益 - 创业板指收益", "检验科技成长牛市中是否真正跑赢可替代基准。"],
    ]

    regression = analysis["regression"]
    reg_key = regression["key_table"].copy()
    reg_order = ["头部券商", "腰部券商", "信息技术行业", "抱团强度ln", "成长指数标准化"]
    reg_key["变量"] = pd.Categorical(reg_key["变量"], reg_order, ordered=True)
    reg_key = reg_key.sort_values("变量")
    regression_rows = []
    for _, row in reg_key.iterrows():
        regression_rows.append(
            [
                row["变量"],
                fmt_num(row["系数"], 2),
                fmt_num(row["标准误"], 2),
                fmt_num(row["t值"], 2),
                "较强" if abs(row["t值"]) >= 2 else ("边际" if abs(row["t值"]) >= 1.65 else "不明显"),
            ]
        )

    event_rows = []
    for _, row in analysis["event_study"].iterrows():
        event_rows.append(
            [
                row["事件组"],
                int(row["月份数"]),
                fmt_pct(row["当月平均收益"], 2, True),
                fmt_pct(row["下月平均收益"], 2, True),
            ]
        )

    md = f"""# 券商金股是“指路明灯”还是“韭菜指南”？

**面向投资者的金股跟投研究报告**  
**研究区间：2025 年 5 月至 2026 年 4 月，严格 12 个月口径**

## 作业要求对照

{md_table(framework_rows, ["作业要求", "报告位置", "本版如何落实"])}

这张对照表的作用是让读者先知道：本文不是单纯展示图表，而是按“帮谁决策、在什么背景下、用哪些统计事实、得到什么结论、还有什么局限”这条作业主线展开。加分项也不是口头展望，而是在第 10 节给出可复现的回归与事件研究。

## 投资要点

{image_md("fig0_investor_dashboard.png", "投资者一页看懂")}

1. **不能无脑跟投，但也不是反向指标。** 六家券商金股 12 个月平均相对行业指数超额收益为 {fmt_pct(overall_alpha, 2, True)}，说明“金股”确实包含一定选股信息；但这种收益很大一部分来自科技成长行情和热门赛道暴露，不等于任何市场都有效。
2. **如果把创业板指作为更严格基准，结论明显降温。** 上证指数同期累计收益 {fmt_pct(sse['累计收益率'], 2, True)}，创业板指累计收益 {fmt_pct(cyb['累计收益率'], 2, True)}。六家券商全部跑赢上证，但只有 {len(beat_cyb)} 家跑赢创业板指：{", ".join(beat_cyb) if beat_cyb else "无"}。
3. **头部券商整体更强，但不是简单规模决定一切。** 头部组平均行业超额收益为 {fmt_pct(tier_counts.loc['头部', '平均行业超额收益率'], 2, True)}，高于腰部和尾部；但招商证券作为腰部组收益排名第二，说明投资者不能只看券商名气，还要看它在当期风格中的选股能力。
4. **抱团推荐非常明显，且主要集中在科技股。** Top10 抱团股占全部推荐记录 {fmt_pct(top10_share, 1)}，其中信息技术类抱团股占 Top10 推荐次数的 {fmt_pct(top10_tech_share_top10, 1)}。这既可能代表机构共识，也可能放大拥挤交易。
5. **最大的风险不是“买错一只股”，而是“买到同一个风格”。** 信息技术、工业、材料三大行业合计占 {fmt_pct(cr3, 1)}；六家券商成长股占比均超过 60%。当科技成长行情转弱时，组合会一起回撤。

## 1. 这份报告帮谁做决策？

这份报告服务的是普通个人投资者和小型投资机构。投资者每个月看到券商金股名单时，真正纠结的不是“报告写得好不好”，而是三个更现实的问题：

- 金股能不能直接买？
- 头部券商是不是一定更值得跟？
- 多家券商反复推荐的热门科技股，到底是好机会还是高位接盘风险？

因此，本报告不把金股当作神秘的“专家答案”，而是把它拆成四个投资者能看懂的维度：**买了哪些行业、有没有抱团、偏成长还是偏价值、真实跟投收益能否跑赢大盘。**

## 2. 为什么按头部、腰部、尾部券商划分？

业内有一个很常见的直觉：券商排名越靠前，研究资源越多，机构客户越强，研究能力也应当越强。这个“排名”通常不是单一榜单，而是由三类信息共同构成：

- **监管评价维度。** 证监会对证券公司实施分类评价，评价基础包括风险管理能力、持续合规状况和业务发展状况。证监会也明确说明，分类结果主要服务审慎监管，不能简单等同于信用评级或营销标签。
- **经营规模维度。** 总资产、净资本、营业收入、净利润等指标决定券商能投入多少研究、投行、销售和机构服务资源。
- **市场影响力维度。** 研究覆盖、机构客户触达、投行项目、财富管理渠道和品牌影响力，都会影响金股推荐被市场关注和传播的程度。

本报告沿用小组作业的样本设计，将六家券商分为三组。需要特别说明：**这里的头部、腰部、尾部是研究分组，不是监管结论，也不是对券商资信的评价。** 它的作用是构造一个可检验的假设：如果“规模越大、排名越靠前、研究能力越强”成立，头部组的金股应当在行业超额收益、组合收益和风险控制上表现更好。

{md_table(tier_design_rows, ["研究分组", "样本券商", "为什么这样分", "外部依据与解释"])}

这一定义让后续结论更清楚：如果头部组显著跑赢，说明行业直觉有数据支持；如果腰部或尾部表现更好，则说明金股收益并不完全由券商规模决定，市场风格和个股选择同样关键。

## 3. 政策、行业与市场背景

### 3.1 政策背景：监管鼓励高质量发展，也更重视投资者保护

2024 年国务院发布资本市场新“国九条”，政策主线是加强监管、防范风险、推动资本市场高质量发展。对于普通投资者而言，这意味着市场对“研报是否真正有价值”“中介机构是否勤勉尽责”“投资者是否被过度营销”会更加敏感。

证券公司分类评价制度也在 2025 年继续修订。证监会公告显示，关于修改《证券公司分类监管规定》的决定自 2025 年 8 月 22 日起施行，并将制度名称调整为更突出“分类评价”的表述。这个背景与本报告有关：券商研究不是孤立存在的，它与券商合规、风控、业务发展和专业服务能力都有关。

{md_table(policy_rows, ["核心文件", "发布时间/节点", "关键条款短引", "与本研究的关系"])}

从政策含义看，本报告并不是评价某一家券商“好不好”，而是站在投资者保护和市场高质量发展的角度，检验公开推荐是否能形成可验证的投资价值。政策越强调中介机构责任和投资者保护，投资者越需要知道：金股名单到底是帮助决策，还是在科技牛市中强化追热门的行为。

### 3.2 行业背景：卖方研究的争议，集中体现在“金股”上

券商研报长期存在两种评价。支持者认为，券商研究能把产业趋势、盈利预测和估值逻辑系统化，帮助投资者节省研究成本；质疑者则认为，卖方研究天然服务交易和机构客户，研报普遍偏乐观，金股容易变成热门赛道的集中推荐。

金股名单比普通研报更适合研究这个争议。原因很简单：研报可以写很多观点，金股名单最终要落到股票和收益上。投资者真正关心的是：**推荐后有没有赚钱，赚钱是靠选股，还是只是搭上了市场风格。**

### 3.3 市场背景：这 12 个月更像“科技成长牛市”

{md_table(market_rows, ["指数", "累计收益率", "月均收益率", "月度波动率", "最大回撤", "在本报告中的角色"])}

{image_md("fig_market_context.png", "市场背景：创业板与六家券商平均收益")}

如果只拿上证指数做基准，六家券商金股看起来非常优秀；但这段行情的核心不是传统蓝筹，而是科技成长。创业板指同期累计上涨 {fmt_pct(cyb['累计收益率'], 2, True)}，远高于上证指数的 {fmt_pct(sse['累计收益率'], 2, True)}。因此，本报告把创业板指作为更严格的大盘参照物：它能检验券商金股到底有“选股超额”，还是只是买到了科技成长风格。

现有问题的严重程度也可以先用几组数字概括：六家券商 {fmt_pct(cr3, 1)} 的推荐集中在前三大行业，Top10 抱团股占全部推荐 {fmt_pct(top10_share, 1)}，成长股占比全部超过 60%，而最终只有 {len(beat_cyb)} 家券商组合跑赢创业板指。也就是说，金股不是没有价值，问题在于投资者如果不拆解行业、风格和基准，很容易把“科技牛市收益”误认为“券商选股能力”。

## 4. 数据来源与处理

数据来自 `六大券商合并数据.xlsx`、维度二 Top/Bottom 分组明细、维度三成长/价值风格指标表，以及维度四收益率回测思路。市场基准采用 AkShare 获取的上证指数、深证成指、创业板指日收盘价，并按月末收盘计算月收益；行业基准采用申万一级行业指数，并按 Wind 行业到申万行业的映射做简单平均。

关键处理口径如下：

- **时间口径：** 原始合并表覆盖 2025-04 至 2026-04 共 {meta['raw_all_records']} 条记录。本文剔除 2025-04 的 71 条记录，只保留 2025-05 至 2026-04 的 {meta['filtered_records']} 条推荐，严格对应 12 个月。
- **推荐口径：** 按“推荐记录”统计。同一只股票被多个券商、多个月推荐，会重复计入，因为投资者每月看到的正是这张当月名单。
- **收益口径：** 当月买入当月金股，按表中当月涨跌幅计算收益。组合回测假设每月等权买入，当月 10 只股票就各买 10%，月末结算后滚动到下月。
- **风格口径：** 沿用维度三构造的成长指数。成长指数综合 PE、营收增长率和低分红特征，数值越高越偏成长。
- **现实差异：** 回测未扣除交易成本、税费、滑点、冲击成本、停牌和真实建仓时点差异，实际收益通常会低于理想回测。

{md_table(indicator_rows, ["构造指标", "计算方式", "回答的问题"])}

这张指标表对应后文所有图表：行业集中度回答“买了什么”，超额收益回答“有没有选股能力”，抱团强度回答“是不是集中推热门股”，组合收益回答“投资者跟投后账户会怎样”。把指标先讲清楚，可以避免读者只盯着收益率，而忽略收益背后的风格和风险来源。

关于作业框架中的“政策前后对比”：本文的核心监管背景是 2024 年资本市场新“国九条”和 2025 年证券公司分类评价制度修订。其中 2025 年制度修订施行日晚于本研究区间末，因此不适合把它作为样本内事件做政策前后收益比较。本文改用“政策背景解释研究意义 + 创业板强基准检验市场环境”的方式处理。

## 5. 维度一：行业偏好与行业收益

### 5.1 六家券商整体偏好哪些行业？

{md_table(broker_rows, ["券商", "梯队", "推荐记录数", "唯一股票数", "平均当月收益", "平均行业超额收益"])}

{md_table(tier_rows, ["梯队", "推荐记录数", "唯一股票数", "平均当月收益", "平均行业超额收益"])}

从梯队看，头部券商平均当月收益为 {fmt_pct(tier_counts.loc['头部', '平均当月收益率'], 2, True)}，行业超额收益为 {fmt_pct(tier_counts.loc['头部', '平均行业超额收益率'], 2, True)}，高于腰部和尾部。这说明“头部研究能力更强”的行业直觉有一定数据支持。但单家层面并不绝对：招商证券的组合收益很强，说明在某些市场阶段，中间梯队券商也可能凭借风格判断或选股集中度取得好成绩。

{md_table(industry_rows, ["行业", "推荐次数", "推荐占比", "金股平均收益", "行业指数收益", "平均行业超额收益"])}

{image_md("fig1_industry_concentration.png", "行业集中度与行业超额收益")}

信息技术单一行业占 {fmt_pct(cr1, 1)}，信息技术、工业、材料三大行业合计占 {fmt_pct(cr3, 1)}，前五大行业占 {fmt_pct(cr5, 1)}。这说明六家券商并没有把金股均匀分散到全市场，而是明显把火力集中在科技成长和先进制造链条。

### 5.2 这种行业集中是好事还是坏事？

好处是，在科技牛市里，行业集中能提高胜率。本研究期内，信息技术金股平均收益 {fmt_pct(industry.loc['信息技术', '金股平均收益率'], 2, True)}，相对行业指数也有 {fmt_pct(industry.loc['信息技术', '平均行业超额收益率'], 2, True)}。工业、材料同样贡献了正超额收益。

风险是，投资者以为自己买了“六家券商、很多股票”，其实可能买到的是同一个方向：科技成长。如果市场风格从成长切到红利、消费或低估值价值股，分散券商并不能真正分散风险。

{md_table(broker_top3_rows, ["券商", "前三大偏好行业及占比", "前三大行业合计占比"])}

{image_md("fig2_broker_industry_heatmap.png", "券商行业偏好热力图")}

招商证券的信息技术占比最高，华泰证券在信息技术、材料、工业之间更均衡；天风证券在可选消费上占比更高。对投资者来说，这张表的用途不是判断谁“更聪明”，而是判断自己跟投后到底暴露在哪些行业。

## 6. 维度二：抱团荐股与热门科技股风险

### 6.1 六家券商是否存在抱团推荐？

答案是：存在，而且不弱。12 个月内共有 {analysis['stock_counts'].shape[0]} 只股票被推荐，其中只出现 1 次的股票有 {analysis['once_count']} 只，占唯一股票数 {fmt_pct(once_share_unique, 1)}；但被重复推荐 2 次及以上的股票贡献了 {analysis['repeat_records']} 条推荐记录，占全部推荐的 {fmt_pct(repeat_share_records, 1)}。也就是说，一边是大量股票只被偶尔提到，另一边是少数热门股被反复推荐。

Top10 抱团股合计出现 {int(top10['累计推荐次数'].sum())} 次，占全部推荐记录的 {fmt_pct(top10_share, 1)}。其中信息技术抱团股贡献 {int(top10_tech['累计推荐次数'].sum())} 次，占 Top10 推荐次数的 {fmt_pct(top10_tech_share_top10, 1)}，占全部推荐记录的 {fmt_pct(top10_tech_share_all, 1)}。

{md_table(top_rows, ["代码", "简称", "累计推荐次数", "主要行业", "是否科技股", "推荐当月平均收益"])}

这张表有两个很直观的信号。第一，抱团股不是随机的，主要集中在中际旭创、新易盛、海光信息、生益科技等科技成长链条。第二，抱团并不保证每只股票都赚钱：海光信息、百济神州在推荐当月平均收益为负，而中际旭创、新易盛收益非常突出。投资者不能只看“被推荐次数多”，还要看推荐时点和估值位置。

### 6.2 抱团股收益更好吗？

{md_table(bottom_rows, ["代码", "简称", "累计推荐次数", "主要行业", "推荐当月平均收益"])}

{md_table(group_rows, ["分组", "股票数", "推荐记录数", "有效月份数", "平均收益率", "相对上证Alpha", "正收益占比", "跑赢上证占比"])}

{image_md("fig3_top_bottom.png", "Top10与Bottom10收益对比")}

Top10 抱团股推荐当月平均收益为 {fmt_pct(top_stats['平均收益率'], 2, True)}，相对上证 Alpha 为 {fmt_pct(top_stats['相对上证Alpha'], 2, True)}；Bottom10 冷门股平均收益为 {fmt_pct(bottom_stats['平均收益率'], 2, True)}，相对上证 Alpha 为 {fmt_pct(bottom_stats['相对上证Alpha'], 2, True)}。在本研究期内，抱团热门股明显比冷门股有效。

但这个结论要加一句重要限制：**它成立的背景是科技成长牛市。** 如果市场环境换成价值股占优，热门科技抱团股的优势可能迅速消失。

### 6.3 抱团推荐会不会带来资本市场抱团效应？

本报告不能证明“券商推荐直接导致股价上涨”，因为股价还受业绩、产业趋势、资金面和宏观风险共同影响。但数据说明，券商推荐至少会强化三种市场机制：

- **注意力集中。** 多家券商反复推荐同一批股票，会让这些股票持续出现在投资者视野中。
- **研究共识强化。** 当推荐逻辑相似时，投资者更容易把它理解为“机构一致看好”。
- **交易拥挤。** 如果大量资金都沿着同一条科技成长线买入，行情上涨时收益会被放大，风格反转时回撤也会同步放大。

{image_md("fig3b_herding_tech.png", "抱团科技股收益与回撤")}

### 6.4 集中推荐后，科技抱团股会不会短期大幅回调？

数据给出的答案是：**不是每次集中推荐后都会立刻大跌，但拥挤后的波动显著加大。**

{md_table(crowded_rows, ["月份", "Top10科技股推荐次数", "当月平均收益", "下月平均收益"])}

Top10 科技抱团股在 2025-08 当月平均收益达到 {fmt_pct(toptech.loc['2025-08', '月均收益'], 2, True)}，随后 2025-09 仍为正，但收益降至 {fmt_pct(toptech.loc['2025-09', '月均收益'], 2, True)}，2025-10 进一步降至 {fmt_pct(toptech.loc['2025-10', '月均收益'], 2, True)}。当推荐次数进入高位（10 次及以上）后，下月平均收益约为 {fmt_pct(analysis['crowded_next_return'], 2, True)}。2026-02 和 2026-03，抱团科技股连续出现 {fmt_pct(toptech.loc['2026-02', '月均收益'], 2, True)} 和 {fmt_pct(toptech.loc['2026-03', '月均收益'], 2, True)}，Top10 抱团股月度组合最大回撤达到 {fmt_pct(analysis['top10_mdd'], 2, True)}。

这对投资者的启发很直接：看到多家券商集中推荐科技热门股，不能只理解为“机构共识强”，也要理解为“交易已经拥挤”。越是热门的金股，越需要反问三个问题：估值是否已经反映预期？业绩兑现是否跟得上？如果下个月风格回调，我能承受多大亏损？

## 7. 维度三：成长股还是价值股？

{md_table(style_rows, ["券商", "记录数", "成长指数", "成长股占比", "价值股占比", "PE中位数", "营收增长中位数", "股利收益率均值"])}

{md_table(style_tier_rows, ["梯队", "记录数", "成长指数", "成长股占比", "价值股占比", "均衡占比"])}

{image_md("fig4_style.png", "券商推荐风格")}

六家券商整体明显偏成长，所有券商成长股占比都超过 60%，招商证券最高，达到 {fmt_pct(style_summary.loc['招商证券', '成长股占比'], 1)}。成长股通常有三个特征：估值更高、分红更低、业绩增长预期更强。这样的股票在科技牛市里弹性更大，但也更依赖预期，一旦业绩不及预期或市场利率、风险偏好变化，回撤会比传统价值股更快。

这解释了为什么金股组合在 2025-08、2026-04 这类成长行情强势月份表现亮眼，也解释了为什么 2026-03 市场调整时，多数券商组合一起回撤。

## 8. 维度四：100 万元跟投，能否跑赢大盘？

{md_table(portfolio_rows, ["名称", "累计收益率", "期末资产", "收益金额", "月均收益率", "月度波动率", "最大回撤"])}

{image_md("fig5_portfolio.png", "组合跟投收益")}

以 100 万元本金逐月等权跟投，华泰证券期末资产最高，为 {fmt_wan(best['期末资产'])}，累计收益 {fmt_pct(best['累计收益率'], 2, True)}。如果用上证指数作基准，六家券商全部跑赢；如果用深证成指作基准，{len(beat_szse)} 家跑赢；如果用更贴近科技成长行情的创业板指作基准，只有 {len(beat_cyb)} 家跑赢，即 {", ".join(beat_cyb) if beat_cyb else "无"}。

所以，“券商金股能不能跑赢大盘”要看你把大盘定义成什么：

- 对稳健宽基投资者来说，金股组合大概率提供了比上证更高的收益，但波动也更大。
- 对本来就会买创业板或科技成长 ETF 的投资者来说，只有最强的券商组合才真正跑赢了可替代基准。
- 对追求稳定回撤控制的投资者来说，创业板指最大回撤只有 {fmt_pct(cyb['最大回撤'], 2, True)}，部分券商组合最大回撤超过 10%，开源证券达到 {fmt_pct(portfolio_summary[portfolio_summary['名称']=='开源证券'].iloc[0]['最大回撤'], 2, True)}，风险并不低。

### 8.1 哪些月份跑赢或跑输创业板？

{md_table(cyb_monthly_rows, ["月份", "六家券商平均", "创业板指", "相对创业板", "结果"])}

六家券商平均收益有 {under_cyb_months} 个月跑输创业板。跑输最明显的是 {worst_cyb_month}，相对创业板为 {fmt_pct(cyb_compare.loc[worst_cyb_month, '相对创业板'], 2, True)}；跑赢最明显的是 {best_cyb_month}，相对创业板为 {fmt_pct(cyb_compare.loc[best_cyb_month, '相对创业板'], 2, True)}。

跑输的主要原因有三点：

1. **创业板在科技主升浪中弹性更强。** 2025-08 和 2025-09 创业板指分别上涨 {fmt_pct(cyb_compare.loc['2025-08', '创业板指'], 2, True)}、{fmt_pct(cyb_compare.loc['2025-09', '创业板指'], 2, True)}，六家券商虽然偏科技，但并不是满仓创业板科技股，还配置了材料、工业、消费、金融等行业。
2. **金股组合存在分散收益被稀释的问题。** 分散能降低单股风险，但在最强主题行情中，也会稀释龙头科技股带来的收益。
3. **热门股回调会拖累组合。** 2026-03 六家券商平均收益 {fmt_pct(cyb_compare.loc['2026-03', '六家券商平均'], 2, True)}，弱于创业板指的 {fmt_pct(cyb_compare.loc['2026-03', '创业板指'], 2, True)}，与此前科技抱团股的连续回撤有关。

跑赢的原因也很清楚：当市场不是单边拉升创业板，而是结构扩散到材料、工业、消费或个股 Alpha 时，券商金股能通过主动选股获得更好表现。例如 2025-11 创业板调整，而部分券商组合受益于非创业板或非纯科技标的，六家平均相对创业板跑赢 {fmt_pct(cyb_compare.loc['2025-11', '相对创业板'], 2, True)}。

## 9. 初步结论：问题有多严重，谁受影响？

**第一，背景中描述的“金股是否值得跟投”不是小问题。** 从样本看，{meta['filtered_records']} 条推荐覆盖 {meta['unique_stocks']} 只股票，但前三大行业已经吸收 {fmt_pct(cr3, 1)} 的推荐，Top10 抱团股吸收 {fmt_pct(top10_share, 1)} 的推荐，说明投资者面对的不是分散的全市场建议，而是高度风格化的推荐清单。

**第二，主要影响对象是喜欢照单买金股的个人投资者。** 如果投资者只看“券商推荐”四个字，很容易在同一个月买入多只科技成长股，实际风险暴露比自己以为的更集中。对小型机构而言，金股更适合作为行业热度和研究共识指标，而不是直接替代内部投研。

**第三，还有三个问题需要进一步分析。** 一是更长周期里，科技牛市之外金股是否仍能跑赢创业板；二是扣除交易成本、滑点和真实买入延迟后收益会下降多少；三是券商推荐本身是否会影响股价，这需要更严格的事件研究和日度数据验证。下一节用现有月度数据先做两个加分项：回归和事件研究。

## 10. 加分项：进一步分析

### 10.1 回归分析：收益来自券商层级，还是来自成长风格？

为了避免只看分组均值，本报告构造了一个简单回归：被解释变量是每条推荐的“行业超额收益率”，解释变量包括头部券商、腰部券商、信息技术行业、抱团强度、成长指数，并加入月份虚拟变量控制市场月度波动。尾部券商是基准组，因此头部/腰部系数表示相对尾部的差异。

{md_table(regression_rows, ["变量", "系数", "标准误", "t值", "信号强度"])}

{image_md("fig6_bonus_reg_event.png", "加分项：回归与事件研究")}

回归结果说明两点。第一，成长指数标准化后的系数为正，且 t 值超过 2，说明在控制月份后，越偏成长的金股越容易取得行业超额收益；这与本轮科技成长行情一致。第二，抱团强度系数为正但只是边际显著，说明“被更多机构推荐”确实可能包含信息，但它不是稳健的安全垫；头部券商系数为正但不显著，意味着头部优势存在于描述统计中，但用月度样本控制风格后，统计显著性还不够强。

这个回归的调整 R2 只有 {fmt_num(regression['adj_r2'] * 100, 2)}%，也很重要：金股收益受市场情绪、产业催化、个股公告和估值变化影响很大，不能指望用券商层级、行业和风格几个变量完全解释。

### 10.2 事件研究：科技股拥挤推荐后，次月表现如何？

事件定义为：Top10 抱团科技股当月推荐次数达到 10 次及以上，视为“拥挤月”；低于 10 次视为“未拥挤月”。我们比较事件月当月收益和下月收益，观察集中推荐后是否存在短期回调风险。

{md_table(event_rows, ["事件组", "月份数", "当月平均收益", "下月平均收益"])}

事件研究给出一个投资者很容易理解的信号：科技抱团股未拥挤时，当月和下月都保持较高弹性；一旦进入拥挤月，当月平均收益降至 {fmt_pct(analysis['event_study'].iloc[0]['当月平均收益'], 2, True)}，下月平均收益变为 {fmt_pct(analysis['event_study'].iloc[0]['下月平均收益'], 2, True)}。这不是严格因果证明，但可以作为风险预警规则：**当同一批科技股已经被反复推荐到很高频时，投资者不宜继续追涨，而应优先检查估值、业绩兑现和仓位集中度。**

## 11. 对投资者的实际建议

### 11.1 买入券商金股的好处

- **节省研究时间。** 金股可以作为每月重点行业和重点公司的观察清单。
- **捕捉机构共识。** 多家券商共同推荐的股票，通常对应当期产业趋势和盈利预期变化。
- **在成长行情中提高弹性。** 本研究期内，金股明显偏科技成长，因此在牛市阶段收益较高。

### 11.2 买入券商金股的风险

- **容易买成风格单押。** 看似买了很多券商，实际可能都在买科技成长。
- **抱团股不适合追高。** 推荐次数越多，说明共识越强，也可能说明预期越充分、交易越拥挤。
- **跑赢上证不等于跑赢真正机会成本。** 如果投资者本来可以买创业板 ETF，那么多数券商金股组合并没有跑赢创业板指。
- **回测收益高于真实收益。** 现实交易存在税费、滑点、买入时点和执行纪律，尤其热门股波动大，实际体验会差于表格收益。

### 11.3 更稳妥的使用方式

投资者不宜把券商金股当成“买入指令”，更适合把它当成“研究线索”。建议采用三步法：

1. **先看行业暴露。** 如果你的持仓已经很多科技股，再买金股可能不是分散，而是加杠杆式集中。
2. **再看拥挤程度。** 同一只股票被多家券商连续推荐时，要检查估值和短期涨幅，避免在情绪最热时追入。
3. **最后看替代基准。** 如果你的目标是跑赢上证，金股可能有吸引力；如果目标是跑赢创业板或科技 ETF，就要更谨慎，只选择真正有个股逻辑的标的。

## 12. 总结

本研究的核心回答是：券商金股既不是“指路明灯”，也不是简单的“韭菜指南”。在 2025-05 至 2026-04 的科技成长牛市里，六家券商金股整体跑赢上证，头部券商整体相对更强，抱团科技股也贡献了显著收益。但当我们把创业板指作为更严格基准后，只有华泰证券真正跑赢，说明很多收益来自市场风格，而不是纯粹来自券商选股。

对投资者来说，最重要的不是问“要不要相信券商”，而是问“我到底买到了什么风险”。如果你买到的是科技成长、热门抱团和高估值预期，就应该用成长股的风险管理方式来对待它：控制仓位、避免追高、关注业绩兑现，并准备承受较大波动。

## 13. 局限性与风险提示

- 样本只有 12 个月，且处在科技成长行情中，结论有明显市场阶段性。
- 行业指数采用近似映射，适合观察方向，不等同于严格行业归因模型。
- 抱团分析只能证明推荐集中和收益波动共存，不能证明券商推荐直接导致股价涨跌。
- 回测未考虑交易成本、税费、滑点、停牌、成交量约束和实际买入时间差。
- 风格指标基于静态财务数据，不能完全反映推荐当月的盈利预测修正。

## 参考资料

- [国务院：关于加强监管防范风险推动资本市场高质量发展的若干意见](https://www.gov.cn/zhengce/content/202404/content_6944877.htm)
- [中国证监会：关于修改《证券公司分类监管规定》的决定](https://www.csrc.gov.cn/xiamen/c105635/c7585630/content.shtml)
- [中国证监会：2020 年证券公司分类结果](https://www.csrc.gov.cn/csrc/c100028/c1000712/content.shtml)
- [天风证券向特定对象发行 A 股股票募集说明书，含 2024 年行业经营指标对比](https://static.cninfo.com.cn/finalpage/2025-06-07/1223804036.PDF)

## 附：复现方式

在本目录运行以下命令可重新生成报告、图表和导出文件：

```bash
/Users/wenrt/Anaconda3/anaconda3/bin/python scripts/build_report.py
```
"""
    return md


def write_notebook(markdown_text: str) -> None:
    import nbformat as nbf

    nb = nbf.v4.new_notebook()
    chunks = []
    current = []
    for line in markdown_text.splitlines():
        if line.startswith("## ") and current:
            chunks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    nb.cells = [nbf.v4.new_markdown_cell(chunk) for chunk in chunks if chunk]
    nb.cells.append(
        nbf.v4.new_code_cell(
            "# 复现方式：在项目根目录运行\n"
            "# /Users/wenrt/Anaconda3/anaconda3/bin/python scripts/build_report.py\n"
        )
    )
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {"name": "python", "pygments_lexer": "ipython3"}
    nbf.write(nb, ROOT / "report.ipynb")


def write_fallback_pdf(markdown_text: str) -> None:
    from matplotlib.backends.backend_pdf import PdfPages

    configure_fonts()
    output_pdf = ROOT / "report.pdf"
    page_w, page_h = 8.27, 11.69
    margin_x = 0.55
    top_y = 11.15
    line_h = 0.27
    max_lines = 38

    def clean_inline(text: str) -> str:
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        return text

    def add_text_page(pdf: PdfPages, lines: list[str], page_title: str = "") -> None:
        fig = plt.figure(figsize=(page_w, page_h))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        y = top_y
        if page_title:
            ax.text(margin_x, y, page_title, fontsize=15, fontweight="bold", va="top")
            y -= 0.45
        for line in lines:
            ax.text(margin_x, y, line, fontsize=9.2, va="top", family="sans-serif")
            y -= line_h
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    def add_image_page(pdf: PdfPages, image_path: Path, title: str) -> None:
        if not image_path.exists():
            return
        img = plt.imread(image_path)
        fig = plt.figure(figsize=(page_w, page_h))
        ax = fig.add_axes([0.06, 0.08, 0.88, 0.84])
        ax.imshow(img)
        ax.axis("off")
        fig.text(0.06, 0.95, title, fontsize=14, fontweight="bold", va="top")
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

    title = "券商金股是“指路明灯”还是“韭菜指南”？"
    buffer: list[str] = []
    current_title = title

    def flush(pdf: PdfPages) -> None:
        nonlocal buffer, current_title
        if not buffer:
            return
        while buffer:
            page_lines = buffer[:max_lines]
            buffer = buffer[max_lines:]
            add_text_page(pdf, page_lines, current_title)
            current_title = ""

    with PdfPages(output_pdf) as pdf:
        for raw_line in markdown_text.splitlines():
            line = raw_line.rstrip()
            image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line)
            if image_match:
                flush(pdf)
                add_image_page(pdf, ROOT / image_match.group(2), image_match.group(1) or "图表")
                continue

            if line.startswith("# "):
                current_title = clean_inline(line.lstrip("# ").strip())
                continue
            if line.startswith("## "):
                flush(pdf)
                current_title = clean_inline(line.lstrip("# ").strip())
                continue
            if line.startswith("### "):
                buffer.append("")
                buffer.append(clean_inline(line.lstrip("# ").strip()))
                continue
            if not line.strip():
                buffer.append("")
                continue
            if line.startswith("|"):
                wrapped = textwrap.wrap(clean_inline(line), width=94) or [""]
            elif line.startswith("- ") or re.match(r"\d+\. ", line):
                wrapped = textwrap.wrap(clean_inline(line), width=58, subsequent_indent="  ") or [""]
            else:
                wrapped = textwrap.wrap(clean_inline(line), width=50) or [""]
            buffer.extend(wrapped)
        flush(pdf)


def write_polished_pdf(meta: dict, analysis: dict) -> None:
    """Create a visually designed PDF directly, avoiding browser print issues."""
    from matplotlib.backends.backend_pdf import PdfPages

    configure_fonts()
    output_pdf = ROOT / "report.pdf"
    page_size = (11.69, 8.27)  # A4 landscape
    navy = REPORT_COLORS["navy"]
    blue = REPORT_COLORS["blue"]
    red = REPORT_COLORS["red"]
    green = REPORT_COLORS["green"]
    gray = REPORT_COLORS["gray"]
    light = REPORT_COLORS["light_gray"]
    line = REPORT_COLORS["line"]
    pale_blue = "#F3F7FB"
    pale_red = "#FBF4F5"
    pale_green = "#F3F8F6"

    def wrap(text: str, width: int = 42) -> str:
        return "\n".join(textwrap.wrap(str(text), width=width))

    def new_page(title: str, subtitle: str = ""):
        fig = plt.figure(figsize=page_size)
        fig.patch.set_facecolor("white")
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        ax.add_patch(plt.Rectangle((0.0, 0.965), 1.0, 0.012, transform=ax.transAxes, facecolor=navy, edgecolor="none"))
        ax.add_patch(plt.Rectangle((0.05, 0.89), 0.012, 0.055, transform=ax.transAxes, facecolor=red, edgecolor="none"))
        ax.text(0.07, 0.94, title, fontsize=20, fontweight="bold", color=navy, va="top", transform=ax.transAxes)
        if subtitle:
            ax.text(0.07, 0.895, subtitle, fontsize=10.5, color=gray, va="top", transform=ax.transAxes)
        ax.plot([0.05, 0.95], [0.865, 0.865], color=line, lw=0.9, transform=ax.transAxes)
        return fig, ax

    def add_footer(ax, page_no: int):
        ax.plot([0.05, 0.95], [0.055, 0.055], color="#E5E7EB", lw=0.6, transform=ax.transAxes)
        ax.text(0.05, 0.032, "券商金股研究报告 | 2025-05 至 2026-04 | 资料来源：六大券商金股数据、AkShare、申万指数", fontsize=7.8, color=gray, transform=ax.transAxes)
        ax.text(0.95, 0.032, f"{page_no}", fontsize=8.2, color=gray, ha="right", transform=ax.transAxes)

    def draw_card(ax, x, y, w, h, title, value, note="", color=blue, bg=light):
        rect = plt.Rectangle((x, y), w, h, transform=ax.transAxes, facecolor=bg, edgecolor=line, linewidth=0.8)
        ax.add_patch(rect)
        ax.add_patch(plt.Rectangle((x, y + h - 0.008), w, 0.008, transform=ax.transAxes, facecolor=color, edgecolor="none"))
        ax.text(x + 0.024, y + h - 0.044, title, transform=ax.transAxes, fontsize=10.5, color=navy, fontweight="bold", va="top")
        ax.text(x + 0.024, y + h * 0.47, value, transform=ax.transAxes, fontsize=21, color=color, fontweight="bold", va="center")
        if note:
            ax.text(x + 0.024, y + 0.048, wrap(note, 28), transform=ax.transAxes, fontsize=8.2, color=gray, va="bottom")

    def draw_bullets(ax, bullets, x=0.06, y=0.80, width=50, line_gap=0.065, color=navy):
        yy = y
        for bullet in bullets:
            lines = textwrap.wrap(bullet, width=width)
            ax.text(x, yy, "•", fontsize=13, color=blue, va="top", transform=ax.transAxes)
            ax.text(x + 0.025, yy, "\n".join(lines), fontsize=10.5, color=color, va="top", transform=ax.transAxes, linespacing=1.35)
            yy -= line_gap * max(1, len(lines)) + 0.02

    def add_table(ax, rows, cols, bbox, font_size=8.5, header_color="#E8EEF5", col_widths=None):
        table = ax.table(cellText=rows, colLabels=cols, bbox=bbox, cellLoc="center", colLoc="center", colWidths=col_widths)
        table.auto_set_font_size(False)
        table.set_fontsize(font_size)
        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor(line)
            cell.set_linewidth(0.6)
            if r == 0:
                cell.set_facecolor(header_color)
                cell.set_text_props(fontweight="bold", color=navy)
            else:
                cell.set_facecolor("white" if r % 2 else "#FAFBFC")
        return table

    def add_image(fig, path: Path, rect, title: str = ""):
        if not path.exists():
            return
        ax_img = fig.add_axes(rect)
        ax_img.imshow(plt.imread(path))
        ax_img.axis("off")
        for spine in ax_img.spines.values():
            spine.set_visible(True)
            spine.set_edgecolor("#E5E7EB")
            spine.set_linewidth(0.6)
        if title:
            fig.text(rect[0], rect[1] + rect[3] + 0.015, title, fontsize=11, fontweight="bold", color=navy)

    df = analysis["df"]
    industry = analysis["industry"]
    tier_counts = analysis["tier_counts"]
    style_summary = analysis["style_summary"]
    portfolio_summary = analysis["portfolio_summary"]
    cyb_compare = analysis["cyb_compare"]
    top10 = analysis["top10"]
    top10_tech = analysis["top10_tech"]
    cr3 = industry["推荐次数"].head(3).sum() / len(df) * 100
    overall_alpha = df["行业超额收益率(%)"].mean()
    cyb = portfolio_summary[portfolio_summary["名称"] == "创业板指"].iloc[0]
    sse = portfolio_summary[portfolio_summary["名称"] == "上证指数"].iloc[0]
    beat_cyb = portfolio_summary[
        portfolio_summary["名称"].isin(BROKER_ORDER) & (portfolio_summary["累计收益率"] > cyb["累计收益率"])
    ]["名称"].tolist()
    top10_share = int(top10["累计推荐次数"].sum()) / len(df) * 100
    top10_tech_share = int(top10_tech["累计推荐次数"].sum()) / int(top10["累计推荐次数"].sum()) * 100

    with PdfPages(output_pdf) as pdf:
        p = 1
        fig, ax = new_page("券商金股是“指路明灯”还是“韭菜指南”？", "面向投资者的金股跟投研究报告")
        ax.text(0.05, 0.77, "研究区间：2025 年 5 月至 2026 年 4 月（严格 12 个月口径）", fontsize=14, color=navy, transform=ax.transAxes)
        ax.text(0.05, 0.70, "核心结论：金股不是无脑跟投清单。收益主要来自科技成长行情、行业集中和少数热门股弹性；真正严格的比较基准应当是创业板指。", fontsize=12, color=gray, transform=ax.transAxes)
        cards = [
            ("样本规模", f"{meta['filtered_records']} 条", "剔除 2025-04 后的推荐记录", blue, pale_blue),
            ("行业超额", fmt_pct(overall_alpha, 2, True), "金股平均相对行业指数", green, "#eef8f1"),
            ("强基准", fmt_pct(cyb["累计收益率"], 1, True), "创业板指同期累计收益", red, pale_red),
            ("跑赢创业板", f"{len(beat_cyb)}/6 家", "只有华泰证券真正胜出", blue, pale_blue),
            ("抱团科技", fmt_pct(top10_tech_share, 1), "Top10 推荐来自信息技术", green, "#eef8f1"),
            ("拥挤回撤", fmt_pct(analysis["toptech_mdd"], 1, True), "抱团科技最大回撤", red, pale_red),
        ]
        xs = [0.05, 0.365, 0.68]
        ys = [0.43, 0.19]
        for i, (title, value, note, color, bg) in enumerate(cards):
            draw_card(ax, xs[i % 3], ys[i // 3], 0.27, 0.18, title, value, note, color, bg)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("一、作业框架与决策主体", "先说明为谁做、解决什么问题，再说明如何满足作业要求")
        draw_bullets(ax, [
            "决策主体：普通个人投资者和小型投资机构，他们每月面对是否跟投券商金股、是否选择头部券商、是否追热门科技股的决策。",
            "研究目标：用行业偏好、抱团效应、成长/价值风格、组合收益四个维度，拆解金股的收益来源和风险来源。",
            "加分项：在描述统计之外，加入回归分析和事件研究，检验收益是否来自成长风格，以及拥挤推荐后是否有短期回调风险。",
        ], width=65)
        framework_rows = [
            ["决策主体", "第 1 节", "投资者是否跟投金股"],
            ["政策/市场背景", "第 2-3 节", "监管、券商分层、科技牛市"],
            ["数据来源与处理", "第 4 节", "12 个月口径、指标构造"],
            ["统计事实", "第 5-8 节", "行业、抱团、风格、收益"],
            ["初步结论", "第 9 节", "问题严重度与影响对象"],
            ["局限性", "第 13 节", "数据/方法/适用范围"],
            ["加分项", "第 10 节", "回归与事件研究"],
        ]
        add_table(ax, framework_rows, ["作业要求", "报告位置", "落实方式"], [0.08, 0.12, 0.84, 0.34], font_size=9.5)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("二、为什么按头部、腰部、尾部券商划分？", "分层是为了检验“排名越前，研究能力越强”的市场直觉")
        add_table(ax, [
            ["头部", "中信建投、华泰", "研究资源和机构客户覆盖更强；检验头部优势"],
            ["腰部", "招商、平安", "大型/中型综合券商对照组；观察非最头部能否复制超额"],
            ["尾部", "天风、开源", "中小或特色券商；观察差异化行业覆盖能否胜出"],
        ], ["研究分组", "样本券商", "研究含义"], [0.08, 0.54, 0.84, 0.23], font_size=10)
        draw_bullets(ax, [
            "外部依据包括证监会证券公司分类评价、经营规模、净资本、营业收入、净利润和市场影响力。",
            "本文的分组是研究设计，不是监管结论，也不是对券商资信等级的评价。",
            "如果头部组显著跑赢，说明行业直觉有数据支持；如果腰部/尾部跑赢，则说明市场风格和个股选择同样关键。",
        ], x=0.08, y=0.43, width=78)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("三、政策与市场背景", "监管强调高质量发展；本轮行情更像科技成长牛市")
        add_table(ax, [
            ["新“国九条”", "2024-04-12", "加强监管、防范风险、推动资本市场高质量发展"],
            ["证券公司分类评价规定", "2025-08-22", "突出分类评价，服务审慎监管"],
            ["2020 年分类结果", "2020-08-26", "分类结果不是资信评级，但可作分层参考"],
        ], ["核心文件", "时间", "关键条款短引"], [0.06, 0.56, 0.88, 0.22], font_size=9.5)
        add_image(fig, FIG_DIR / "fig_market_context.png", [0.09, 0.08, 0.82, 0.40], "市场基准：创业板显著强于上证")
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("四、数据来源、处理与指标", "所有分析统一为 2025-05 至 2026-04 的 12 个月口径")
        add_table(ax, [
            ["推荐记录", "六大券商合并数据.xlsx", f"{meta['filtered_records']} 条，{meta['unique_stocks']} 只股票"],
            ["风格指标", "维度3 风格分析表", "PE、营收增长、股利收益率、成长指数"],
            ["市场基准", "AkShare/缓存 CSV", "上证指数、深证成指、创业板指"],
            ["行业基准", "申万一级行业指数", "Wind 行业映射到申万行业均值"],
        ], ["数据", "来源", "用途"], [0.06, 0.56, 0.88, 0.22], font_size=9.5)
        add_table(ax, [
            ["行业集中度", "CR1/CR3/CR5", "是否集中在少数热门行业"],
            ["行业超额收益", "金股收益 - 行业指数收益", "是否有行业内部选股能力"],
            ["抱团强度", "累计推荐次数/Top10 占比", "是否反复推荐热门股"],
            ["组合收益", "100 万元月度等权跟投", "投资者账户体验"],
            ["强基准超额", "组合收益 - 创业板收益", "是否跑赢可替代基准"],
        ], ["指标", "计算方式", "回答的问题"], [0.06, 0.12, 0.88, 0.34], font_size=9.5)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("五、维度一：行业集中度与行业超额收益", f"前三大行业占 {fmt_pct(cr3,1)}，金股不是全市场均匀分散")
        add_image(fig, FIG_DIR / "fig1_industry_concentration.png", [0.05, 0.20, 0.90, 0.58])
        top_ind_rows = []
        for idx, row in industry.head(6).iterrows():
            top_ind_rows.append([idx, int(row["推荐次数"]), fmt_pct(row["推荐占比"], 1), fmt_pct(row["平均行业超额收益率"], 2, True)])
        add_table(ax, top_ind_rows, ["行业", "推荐次数", "推荐占比", "行业超额"], [0.08, 0.05, 0.84, 0.13], font_size=8.5)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("六、维度一延伸：券商之间的行业偏好差异", "投资者需要知道自己跟投后到底暴露在哪些行业")
        add_image(fig, FIG_DIR / "fig2_broker_industry_heatmap.png", [0.07, 0.18, 0.86, 0.58])
        draw_bullets(ax, [
            "招商证券的信息技术占比最高，华泰证券在信息技术、材料、工业之间更均衡。",
            "天风证券在可选消费上占比更高，说明尾部券商并非简单复制头部。",
            "对投资者而言，分散券商不一定等于分散风险，因为行业和风格可能高度重合。",
        ], x=0.08, y=0.16, width=88, line_gap=0.045)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("七、维度二：抱团股与冷门股对比", f"Top10 抱团股占全部推荐 {fmt_pct(top10_share,1)}")
        add_image(fig, FIG_DIR / "fig3_top_bottom.png", [0.06, 0.25, 0.88, 0.50])
        gs = analysis["group_stats"].drop(columns=["monthly"])
        add_table(ax, [[r["分组"], int(r["推荐记录数"]), fmt_pct(r["平均收益率"], 2, True), fmt_pct(r["相对上证Alpha"], 2, True)] for _, r in gs.iterrows()],
                  ["分组", "推荐记录数", "平均收益", "相对上证Alpha"], [0.12, 0.08, 0.76, 0.12], font_size=9.5)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("八、抱团科技股：收益弹性与拥挤风险", "推荐越密集，越需要警惕交易拥挤和短期回撤")
        add_image(fig, FIG_DIR / "fig3b_herding_tech.png", [0.06, 0.20, 0.88, 0.58])
        event_rows = [[r["事件组"].replace("Top10科技股", ""), int(r["月份数"]), fmt_pct(r["当月平均收益"], 1, True), fmt_pct(r["下月平均收益"], 1, True)] for _, r in analysis["event_study"].iterrows()]
        add_table(ax, event_rows, ["事件组", "月份数", "当月", "下月"], [0.12, 0.05, 0.76, 0.12], font_size=9)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("九、维度三：成长股还是价值股？", "六家券商整体明显偏成长，风险来自高估值和低分红")
        add_image(fig, FIG_DIR / "fig4_style.png", [0.08, 0.28, 0.84, 0.46])
        style_rows = []
        for broker in BROKER_ORDER:
            r = style_summary.loc[broker]
            style_rows.append([broker, fmt_num(r["成长指数"], 1), fmt_pct(r["成长股占比"], 1), fmt_num(r["PE中位数"], 1), fmt_pct(r["营收增长中位数"], 1, True)])
        add_table(ax, style_rows, ["券商", "成长指数", "成长占比", "PE中位数", "营收增长中位数"], [0.08, 0.07, 0.84, 0.17], font_size=8.5)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("十、维度四：100 万元跟投收益", "跑赢上证不等于跑赢真正的机会成本")
        add_image(fig, FIG_DIR / "fig5_portfolio.png", [0.06, 0.25, 0.88, 0.50])
        port_rows = []
        for _, r in portfolio_summary.head(9).iterrows():
            port_rows.append([r["名称"], fmt_pct(r["累计收益率"], 1, True), fmt_wan(r["期末资产"], 1), fmt_pct(r["最大回撤"], 1, True)])
        add_table(ax, port_rows, ["名称", "累计收益", "期末资产", "最大回撤"], [0.12, 0.04, 0.76, 0.17], font_size=8.3)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("十一、创业板强基准：哪些月份跑输？", "六家券商平均有 6 个月跑输创业板")
        monthly_rows = []
        for month, r in cyb_compare.iterrows():
            monthly_rows.append([month, fmt_pct(r["六家券商平均"], 1, True), fmt_pct(r["创业板指"], 1, True), fmt_pct(r["相对创业板"], 1, True), "跑赢" if r["相对创业板"] > 0 else "跑输"])
        add_table(ax, monthly_rows, ["月份", "六家平均", "创业板", "相对创业板", "结果"], [0.08, 0.28, 0.84, 0.48], font_size=8.5)
        draw_bullets(ax, [
            "跑输主因：创业板在科技主升浪中弹性更强，而金股组合还配置了材料、工业、消费、金融等行业。",
            "跑赢月份：当行情从单一科技主题扩散到其他行业或个股 Alpha 时，券商主动选股更容易胜出。",
        ], x=0.08, y=0.21, width=88, line_gap=0.05)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("十二、加分项：回归分析与事件研究", "检验收益来源与拥挤风险，而不仅仅做描述统计")
        add_image(fig, FIG_DIR / "fig6_bonus_reg_event.png", [0.06, 0.28, 0.88, 0.46])
        reg_rows = []
        reg_key = analysis["regression"]["key_table"].copy()
        reg_order = ["头部券商", "腰部券商", "信息技术行业", "抱团强度ln", "成长指数标准化"]
        reg_key["变量"] = pd.Categorical(reg_key["变量"], reg_order, ordered=True)
        reg_key = reg_key.sort_values("变量")
        for _, r in reg_key.iterrows():
            reg_rows.append([r["变量"], fmt_num(r["系数"], 2), fmt_num(r["t值"], 2), "较强" if abs(r["t值"]) >= 2 else ("边际" if abs(r["t值"]) >= 1.65 else "不明显")])
        add_table(ax, reg_rows, ["变量", "系数", "t值", "信号"], [0.16, 0.06, 0.68, 0.16], font_size=8.8)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("十三、初步结论与投资启示", "金股可以作为研究线索，但不应作为直接买入指令")
        draw_bullets(ax, [
            f"问题严重度：推荐高度集中。前三大行业占 {fmt_pct(cr3,1)}，Top10 抱团股占 {fmt_pct(top10_share,1)}，成长股占比普遍超过 60%。",
            "主要影响对象：喜欢照单买金股的个人投资者，以及把券商共识当作持仓依据的小型机构。",
            "头部优势存在但不绝对：头部组行业超额更高，但招商证券等非头部样本也有强表现。",
            "投资建议：先看行业暴露，再看拥挤程度，最后看替代基准。能跑赢上证不代表能跑赢创业板或科技 ETF。",
        ], x=0.08, y=0.78, width=88, line_gap=0.055)
        draw_card(ax, 0.12, 0.15, 0.34, 0.18, "适合怎么用？", "研究线索", "用来发现产业趋势与机构共识", blue, pale_blue)
        draw_card(ax, 0.54, 0.15, 0.34, 0.18, "不适合怎么用？", "无脑跟投", "尤其不要追高拥挤科技股", red, pale_red)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1

        fig, ax = new_page("十四、局限性与进一步研究", "本研究解释的是一个科技成长行情中的 12 个月样本")
        draw_bullets(ax, [
            "数据局限：样本期只有 12 个月，且处在科技成长行情中，结论有阶段性。",
            "方法局限：行业指数映射是近似处理；回归调整 R2 较低，说明收益还受很多不可观测因素影响。",
            "交易局限：回测没有计入交易成本、滑点、停牌、成交量约束和真实买入时点差异。",
            "因果局限：抱团分析只能证明推荐集中和收益波动共存，不能证明券商推荐直接导致股价涨跌。",
            "后续方向：使用更长时间窗口、日度事件研究和真实调仓成本，继续检验金股是否稳定创造超额收益。",
        ], x=0.08, y=0.78, width=90, line_gap=0.06)
        add_footer(ax, p); pdf.savefig(fig); plt.close(fig); p += 1
def write_html_and_pdf() -> None:
    header = ROOT / "outputs" / "report_header.html"
    header.write_text(
        """
<style>
body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Heiti SC", "STHeiti", sans-serif; line-height: 1.65; color: #111827; max-width: 980px; margin: 36px auto; padding: 0 28px; }
h1 { font-size: 30px; line-height: 1.25; margin-bottom: 20px; }
h2 { border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; margin-top: 34px; }
h3 { margin-top: 28px; }
table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 14px 0 20px; }
th, td { border: 1px solid #d1d5db; padding: 7px 8px; vertical-align: top; }
th { background: #f3f4f6; font-weight: 700; }
img { max-width: 100%; margin: 10px 0 20px; }
code { background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }
pre code { display: block; padding: 12px; overflow-x: auto; }
blockquote { border-left: 4px solid #9ca3af; padding-left: 14px; color: #4b5563; }
@page { size: A4; margin: 14mm 12mm; }
@media print { body { margin: 0 auto; max-width: 100%; font-size: 12px; } h2 { page-break-after: avoid; } img, table { page-break-inside: avoid; } }
</style>
""".strip(),
        encoding="utf-8",
    )

    pandoc = shutil.which("pandoc") or "/Users/wenrt/Anaconda3/anaconda3/bin/pandoc"
    if Path(pandoc).exists() or shutil.which("pandoc"):
        subprocess.run(
            [
                pandoc,
                str(ROOT / "report.md"),
                "--from=gfm",
                "--to=html5",
                "--standalone",
                "--embed-resources",
                "--metadata",
                "title=券商金股分析报告",
                "--include-in-header",
                str(header),
                "-o",
                str(ROOT / "report.html"),
            ],
            cwd=ROOT,
            check=True,
        )

    # PDF rendering is handled by scripts/render_research_pdf.py so the final
    # PDF keeps the full Markdown content and avoids browser-print instability.


def write_research_pdf() -> None:
    pdf_python = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "bin" / "python3"
    renderer = ROOT / "scripts" / "render_research_pdf.py"
    if pdf_python.exists() and renderer.exists():
        subprocess.run(
            [
                str(pdf_python),
                str(renderer),
                str(ROOT / "report.md"),
                str(ROOT / "report.pdf"),
            ],
            cwd=ROOT,
            check=True,
        )
    else:
        write_fallback_pdf((ROOT / "report.md").read_text(encoding="utf-8"))


def main() -> None:
    configure_fonts()
    df, style, meta = load_data()
    analysis = build_analysis(df, style)
    make_figures(analysis)
    markdown_text = build_markdown_v2(meta, analysis)
    (ROOT / "report.md").write_text(markdown_text, encoding="utf-8")
    write_notebook(markdown_text)
    write_html_and_pdf()
    write_research_pdf()


if __name__ == "__main__":
    main()
