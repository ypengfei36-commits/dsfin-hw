"""Build policy timeline and mortgage affordability outputs."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CLEAN = DATA / "clean"
OUTPUT = ROOT / "output"


def setup_style() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def monthly_payment(principal_10k: float, annual_rate_pct: float, years: int = 30) -> float:
    """Equal principal and interest monthly payment, output in yuan."""
    principal = principal_10k * 10000
    monthly_rate = annual_rate_pct / 100 / 12
    periods = years * 12
    if monthly_rate == 0:
        return principal / periods
    return principal * monthly_rate * (1 + monthly_rate) ** periods / ((1 + monthly_rate) ** periods - 1)


def build_affordability() -> pd.DataFrame:
    scenarios = []
    total_prices = [300, 400, 600, 800, 1000, 1200]
    down_payment_ratios = [0.20, 0.30]
    rates = [3.1, 3.5, 3.9]
    incomes = [20000, 30000, 40000, 60000]

    for total in total_prices:
        for dp in down_payment_ratios:
            loan = total * (1 - dp)
            for rate in rates:
                pay = monthly_payment(loan, rate)
                row = {
                    "total_price_10k": total,
                    "down_payment_ratio": dp,
                    "down_payment_10k": total * dp,
                    "loan_10k": loan,
                    "annual_rate_pct": rate,
                    "monthly_payment_yuan": round(pay, 0),
                }
                for income in incomes:
                    row[f"payment_to_income_{income}_pct"] = round(pay / income * 100, 1)
                scenarios.append(row)
    df = pd.DataFrame(scenarios)
    df.to_csv(CLEAN / "mortgage_affordability_scenarios.csv", index=False, encoding="utf-8-sig")
    return df


def plot_monthly_payment(df: pd.DataFrame) -> None:
    chart = df[(df["down_payment_ratio"] == 0.20) & (df["annual_rate_pct"] == 3.5)].copy()
    plt.figure(figsize=(9.5, 5.6))
    sns.barplot(data=chart, x="total_price_10k", y="monthly_payment_yuan", color="#4c78a8")
    for idx, row in chart.iterrows():
        plt.text(
            chart.index.get_loc(idx),
            row["monthly_payment_yuan"],
            f"{row['monthly_payment_yuan']:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    plt.title("不同总价住房的月供压力测算（首付20%，30年，年利率3.5%）")
    plt.xlabel("总价（万元）")
    plt.ylabel("等额本息月供（元/月）")
    plt.savefig(OUTPUT / "fig06_monthly_payment_by_total_price.png", dpi=220, bbox_inches="tight")
    plt.close()


def plot_payment_to_income(df: pd.DataFrame) -> None:
    chart = df[(df["down_payment_ratio"] == 0.20) & (df["annual_rate_pct"] == 3.5)].copy()
    rows = []
    for _, row in chart.iterrows():
        for income in [20000, 30000, 40000, 60000]:
            rows.append(
                {
                    "total_price_10k": row["total_price_10k"],
                    "monthly_income_yuan": income,
                    "payment_to_income_pct": row[f"payment_to_income_{income}_pct"],
                }
            )
    tidy = pd.DataFrame(rows)
    pivot = tidy.pivot(index="monthly_income_yuan", columns="total_price_10k", values="payment_to_income_pct")
    plt.figure(figsize=(9.5, 4.8))
    sns.heatmap(pivot, annot=True, fmt=".1f", cmap="RdYlGn_r", center=50, cbar_kws={"label": "月供收入比（%）"})
    plt.title("不同收入与总价情景下的月供收入比")
    plt.xlabel("住房总价（万元）")
    plt.ylabel("家庭月收入（元）")
    plt.savefig(OUTPUT / "fig07_payment_to_income_heatmap.png", dpi=220, bbox_inches="tight")
    plt.close()


def plot_policy_timeline() -> None:
    df = pd.read_csv(DATA / "policy_timeline.csv", encoding="utf-8-sig")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    x = mdates.date2num(df["date"])

    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.hlines(1, x.min(), x.max(), color="#b8c2cc", linewidth=2)
    ax.scatter(x, [1] * len(df), s=110, color="#2f5597", zorder=3)
    for i, row in enumerate(df.itertuples(index=False)):
        y = 1.18 if i % 2 == 0 else 0.78
        xpos = mdates.date2num(row.date)
        ax.text(xpos, y, row.policy, ha="center", va="center", fontsize=9)
        ax.vlines(xpos, 1, y - 0.04 if y > 1 else y + 0.04, color="#8a98a8", linewidth=1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.set_ylim(0.55, 1.42)
    ax.set_yticks([])
    ax.set_title("广州购房相关政策时间线")
    ax.set_xlabel("日期")
    plt.savefig(OUTPUT / "fig08_policy_timeline.png", dpi=220, bbox_inches="tight")
    plt.close()


def write_decision_matrix() -> None:
    rows = [
        {
            "buyer_type": "刚需自住、收入稳定",
            "recommendation": "可以积极看房，择优买入",
            "conditions": "月供收入比低于40%；通勤、学位、居住周期明确；不依赖短期转手获利",
        },
        {
            "buyer_type": "改善置换、旧房流动性较好",
            "recommendation": "谨慎推进",
            "conditions": "旧房出售周期可控；能享受卖旧买新或公积金政策；避免先买后卖造成资金链压力",
        },
        {
            "buyer_type": "投资购房",
            "recommendation": "不建议作为主策略",
            "conditions": "租金回报和转售流动性不确定；挂牌样本分化明显；不能仅凭热盘外推全区上涨",
        },
        {
            "buyer_type": "预算紧张或收入波动",
            "recommendation": "建议暂缓",
            "conditions": "月供收入比超过50%；首付后现金储备不足12个月家庭支出",
        },
    ]
    pd.DataFrame(rows).to_csv(CLEAN / "buyer_decision_matrix.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    setup_style()
    affordability = build_affordability()
    plot_monthly_payment(affordability)
    plot_payment_to_income(affordability)
    plot_policy_timeline()
    write_decision_matrix()
    print("Affordability and policy outputs generated.")


if __name__ == "__main__":
    main()
