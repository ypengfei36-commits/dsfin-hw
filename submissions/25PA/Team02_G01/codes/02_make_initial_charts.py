"""Create initial charts for the Haizhu housing decision report."""

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


def plot_guangzhou_price_index() -> None:
    df = pd.read_csv(CLEAN / "city_house_price_index_guangzhou_compare.csv", encoding="utf-8-sig")
    df["日期"] = pd.to_datetime(df["日期"])
    gz = df[df["城市"] == "广州"].copy()
    gz = gz[gz["日期"] >= "2019-01-01"]

    plt.figure(figsize=(10.5, 5.8))
    plt.plot(gz["日期"], gz["新建商品住宅价格指数-同比"], label="新建商品住宅同比指数", linewidth=2.2)
    plt.plot(gz["日期"], gz["二手住宅价格指数-同比"], label="二手住宅同比指数", linewidth=2.2)
    plt.axhline(100, color="#666666", linewidth=1, linestyle="--")
    plt.title("广州新房与二手房价格指数走势（2019-2026）")
    plt.xlabel("日期")
    plt.ylabel("价格指数（上年同月=100）")
    plt.legend(frameon=True)
    savefig("fig01_guangzhou_price_index.png")


def plot_city_comparison() -> None:
    df = pd.read_csv(CLEAN / "city_house_price_index_guangzhou_compare.csv", encoding="utf-8-sig")
    df["日期"] = pd.to_datetime(df["日期"])
    df = df[df["日期"] >= "2021-01-01"].copy()

    plt.figure(figsize=(10.5, 5.8))
    sns.lineplot(data=df, x="日期", y="二手住宅价格指数-同比", hue="城市", linewidth=2)
    plt.axhline(100, color="#666666", linewidth=1, linestyle="--")
    plt.title("一线城市二手住宅价格同比指数对比（2021-2026）")
    plt.xlabel("日期")
    plt.ylabel("二手住宅价格指数（上年同月=100）")
    plt.legend(frameon=True, ncol=4)
    savefig("fig02_first_tier_secondhand_price_compare.png")


def plot_real_estate_climate() -> None:
    df = pd.read_csv(CLEAN / "real_estate_climate_index.csv", encoding="utf-8-sig")
    df["日期"] = pd.to_datetime(df["日期"])
    df = df[df["日期"] >= "2018-01-01"].copy()

    plt.figure(figsize=(10.5, 5.8))
    plt.plot(df["日期"], df["最新值"], color="#2f5597", linewidth=2.2)
    plt.title("国房景气指数走势（2018-2025）")
    plt.xlabel("日期")
    plt.ylabel("国房景气指数")
    savefig("fig03_real_estate_climate_index.png")


def main() -> None:
    setup_style()
    plot_guangzhou_price_index()
    plot_city_comparison()
    plot_real_estate_climate()
    print("Initial charts generated.")


if __name__ == "__main__":
    main()
