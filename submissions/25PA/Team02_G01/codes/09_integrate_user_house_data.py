"""Integrate user-provided Lianjia and Beike Haizhu housing samples."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUTPUT = ROOT / "output"


SECONDHAND_RAW = RAW / "lianjia_haizhu_secondhand_user.csv"
NEWHOME_RAW = RAW / "beike_haizhu_newhome_user.csv"


def setup_style() -> None:
    CLEAN.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def read_csv_with_fallback(path: Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def savefig(name: str) -> None:
    plt.tight_layout()
    plt.savefig(OUTPUT / name, dpi=220, bbox_inches="tight")
    plt.close()


def clean_secondhand() -> pd.DataFrame:
    df = read_csv_with_fallback(SECONDHAND_RAW)
    clean = pd.DataFrame(
        {
            "source": "链家",
            "listing_id": df.get("房源 ID"),
            "project_or_community": df.get("板块房源"),
            "total_price_10k": pd.to_numeric(df.get("挂牌总价 (万)"), errors="coerce"),
            "unit_price_yuan_m2": pd.to_numeric(df.get("单价 (元 /㎡)"), errors="coerce"),
            "area_m2": pd.to_numeric(df.get("建筑面积 (㎡)"), errors="coerce"),
            "layout": df.get("户型"),
            "orientation": df.get("朝向"),
            "floor": df.get("楼层"),
            "decoration": df.get("装修情况"),
            "building_type": df.get("建筑类型"),
            "build_year": df.get("建成年份"),
            "property_right": df.get("交易权属"),
            "usage": df.get("房屋用途"),
            "listing_date": pd.to_datetime(df.get("挂牌时间"), errors="coerce"),
            "url_or_title": df.get("房源链接"),
            "price_band_10k": df.get("价格区间（万）"),
        }
    )
    clean = clean.dropna(subset=["total_price_10k", "unit_price_yuan_m2", "area_m2"], how="all")
    clean.to_csv(CLEAN / "lianjia_haizhu_secondhand_user_clean.csv", index=False, encoding="utf-8-sig")
    return clean


def clean_newhome() -> pd.DataFrame:
    df = read_csv_with_fallback(NEWHOME_RAW)
    clean = pd.DataFrame(
        {
            "source": "贝壳",
            "project_or_community": df.get("楼盘"),
            "project_avg_unit_price_yuan_m2": pd.to_numeric(df.get("楼盘参考均价(元 /㎡)"), errors="coerce"),
            "project_total_price_range_10k": df.get("楼盘整体总价参考（(万/套)）"),
            "sample_total_price_10k": pd.to_numeric(df.get("本套参考总价 (万)"), errors="coerce"),
            "sample_area_m2": pd.to_numeric(df.get("本套建筑面积 (㎡)"), errors="coerce"),
            "layout": df.get("户型"),
            "orientation": df.get("朝向"),
            "address": df.get("楼盘地址"),
            "price_band_10k": df.get("价格区间（万）"),
            "features": df.get("项目特色"),
        }
    )
    clean = clean.dropna(
        subset=["project_avg_unit_price_yuan_m2", "sample_total_price_10k", "sample_area_m2"],
        how="all",
    )
    clean.to_csv(CLEAN / "beike_haizhu_newhome_user_clean.csv", index=False, encoding="utf-8-sig")
    return clean


def make_summary(secondhand: pd.DataFrame, newhome: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "dataset": "链家海珠二手房源样本",
            "records": len(secondhand),
            "median_unit_price_yuan_m2": secondhand["unit_price_yuan_m2"].median(),
            "median_total_price_10k": secondhand["total_price_10k"].median(),
            "median_area_m2": secondhand["area_m2"].median(),
            "min_total_price_10k": secondhand["total_price_10k"].min(),
            "max_total_price_10k": secondhand["total_price_10k"].max(),
        },
        {
            "dataset": "贝壳海珠一手房样本",
            "records": len(newhome),
            "median_unit_price_yuan_m2": newhome["project_avg_unit_price_yuan_m2"].median(),
            "median_total_price_10k": newhome["sample_total_price_10k"].median(),
            "median_area_m2": newhome["sample_area_m2"].median(),
            "min_total_price_10k": newhome["sample_total_price_10k"].min(),
            "max_total_price_10k": newhome["sample_total_price_10k"].max(),
        },
    ]
    summary = pd.DataFrame(rows)
    summary.to_csv(CLEAN / "user_house_data_summary.csv", index=False, encoding="utf-8-sig")
    return summary


def plot_secondhand_distribution(secondhand: pd.DataFrame) -> None:
    chart_df = secondhand.dropna(subset=["unit_price_yuan_m2"]).copy()
    plt.figure(figsize=(9.5, 5.6))
    sns.histplot(chart_df["unit_price_yuan_m2"], bins=12, kde=True, color="#2f5597")
    median = chart_df["unit_price_yuan_m2"].median()
    plt.axvline(median, color="#c44e52", linestyle="--", linewidth=1.8, label=f"中位数 {median:,.0f} 元/㎡")
    plt.title("链家海珠区二手房源样本单价分布")
    plt.xlabel("挂牌单价（元/平方米）")
    plt.ylabel("样本数")
    plt.legend()
    savefig("fig12_lianjia_secondhand_unit_price_distribution.png")


def plot_newhome_price_bands(newhome: pd.DataFrame) -> None:
    band = (
        newhome["price_band_10k"]
        .fillna("未分组")
        .value_counts()
        .rename_axis("price_band_10k")
        .reset_index(name="records")
    )
    band["sort_key"] = band["price_band_10k"].str.extract(r"(\d+)").astype(float)
    band = band.sort_values(["sort_key", "price_band_10k"]).drop(columns="sort_key")

    plt.figure(figsize=(9.5, 5.4))
    sns.barplot(data=band, x="price_band_10k", y="records", color="#59a14f")
    for idx, row in band.iterrows():
        plt.text(idx, row["records"], f"{int(row['records'])}", ha="center", va="bottom", fontsize=10)
    plt.title("贝壳海珠区一手房样本总价区间分布")
    plt.xlabel("总价区间（万元/套）")
    plt.ylabel("样本数")
    savefig("fig13_beike_newhome_total_price_band.png")


def plot_new_vs_secondhand(summary: pd.DataFrame) -> None:
    chart_df = summary[["dataset", "median_unit_price_yuan_m2", "median_total_price_10k", "median_area_m2"]].copy()
    chart_df["label"] = chart_df["dataset"].str.replace("海珠", "\n海珠", regex=False)

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.8))
    metrics = [
        ("median_unit_price_yuan_m2", "中位单价\n（元/㎡）", "#4c78a8"),
        ("median_total_price_10k", "中位总价\n（万元）", "#f28e2b"),
        ("median_area_m2", "中位面积\n（㎡）", "#76b7b2"),
    ]
    for ax, (metric, title, color) in zip(axes, metrics):
        sns.barplot(data=chart_df, x="label", y=metric, ax=ax, color=color)
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("")
        for patch in ax.patches:
            value = patch.get_height()
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                value,
                f"{value:,.0f}",
                ha="center",
                va="bottom",
                fontsize=9,
            )
    fig.suptitle("链家二手样本与贝壳一手样本核心指标对比", y=1.03, fontsize=14)
    savefig("fig14_user_house_sample_comparison.png")


def main() -> None:
    setup_style()
    secondhand = clean_secondhand()
    newhome = clean_newhome()
    summary = make_summary(secondhand, newhome)
    plot_secondhand_distribution(secondhand)
    plot_newhome_price_bands(newhome)
    plot_new_vs_secondhand(summary)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
