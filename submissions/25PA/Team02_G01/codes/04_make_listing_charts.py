"""Create charts from the public listing sample."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
OUTPUT = ROOT / "output"


def setup_style() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUTPUT / name, dpi=220, bbox_inches="tight")
    plt.close()


def load_sample() -> pd.DataFrame:
    df = pd.read_csv(CLEAN / "fang_haizhu_secondhand_listings_sample.csv", encoding="utf-8-sig")
    df["unit_price_yuan_m2"] = pd.to_numeric(df["unit_price_yuan_m2"], errors="coerce")
    df["total_price_10k"] = pd.to_numeric(df["total_price_10k"], errors="coerce")
    df["area_m2"] = pd.to_numeric(df["area_m2"], errors="coerce")
    return df.dropna(subset=["unit_price_yuan_m2"])


def plot_unit_price_distribution(df: pd.DataFrame) -> None:
    # Keep atypical observations in the CSV, but trim extreme display range for a readable chart.
    chart_df = df[df["unit_price_yuan_m2"].between(10000, 160000)].copy()
    plt.figure(figsize=(10, 5.8))
    sns.histplot(chart_df["unit_price_yuan_m2"], bins=24, kde=True, color="#2f5597")
    plt.title("海珠区二手房公开挂牌样本单价分布")
    plt.xlabel("挂牌单价（元/平方米）")
    plt.ylabel("样本数")
    savefig("fig04_haizhu_listing_unit_price_distribution.png")


def plot_submarket_median(df: pd.DataFrame) -> None:
    sub = (
        df[df["unit_price_yuan_m2"].between(10000, 160000)]
        .groupby("submarket")
        .agg(samples=("url", "count"), median_unit_price=("unit_price_yuan_m2", "median"))
        .query("samples >= 2")
        .sort_values("median_unit_price", ascending=True)
        .reset_index()
    )
    plt.figure(figsize=(9.5, 6.2))
    sns.barplot(data=sub, y="submarket", x="median_unit_price", color="#4c78a8")
    for idx, row in sub.iterrows():
        plt.text(row["median_unit_price"], idx, f" {row['median_unit_price']:,.0f}元/㎡ n={int(row['samples'])}", va="center", fontsize=9)
    plt.title("海珠区主要板块挂牌样本中位单价")
    plt.xlabel("挂牌单价中位数（元/平方米）")
    plt.ylabel("")
    savefig("fig05_haizhu_submarket_median_unit_price.png")


def main() -> None:
    setup_style()
    df = load_sample()
    plot_unit_price_distribution(df)
    plot_submarket_median(df)
    print("Listing charts generated.")


if __name__ == "__main__":
    main()
