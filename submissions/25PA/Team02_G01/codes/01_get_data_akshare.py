"""Fetch reproducible macro housing data for the Haizhu housing decision project.

The project uses official/local Guangzhou district data as the main evidence where
available. AkShare is used for reproducible city-level and national background
series that can be downloaded by any teammate.
"""

from __future__ import annotations

from pathlib import Path

import akshare as ak
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)


def fetch_city_price_index() -> pd.DataFrame:
    """Fetch 70-city housing price index for Guangzhou and comparison cities."""
    cities = ["广州", "深圳", "北京", "上海"]
    frames = [
        ak.macro_china_new_house_price(city_first="广州", city_second="深圳"),
        ak.macro_china_new_house_price(city_first="北京", city_second="上海"),
    ]
    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    df.to_csv(RAW / "akshare_70city_house_price_index_raw.csv", index=False, encoding="utf-8-sig")

    df["日期"] = pd.to_datetime(df["日期"])
    df = df[df["城市"].isin(cities)].sort_values(["城市", "日期"]).reset_index(drop=True)
    df.to_csv(CLEAN / "city_house_price_index_guangzhou_compare.csv", index=False, encoding="utf-8-sig")
    return df


def fetch_real_estate_climate_index() -> pd.DataFrame:
    """Fetch national real estate climate index as macro background."""
    df = ak.macro_china_real_estate()
    df.to_csv(RAW / "akshare_real_estate_climate_index_raw.csv", index=False, encoding="utf-8-sig")
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").reset_index(drop=True)
    df.to_csv(CLEAN / "real_estate_climate_index.csv", index=False, encoding="utf-8-sig")
    return df


def write_source_note() -> None:
    note = """# AkShare 数据说明

本脚本用于获取可复现的宏观和城市层面房价指数数据。

- 城市房价指数：AkShare `macro_china_new_house_price()`，用于广州与北上深的新建商品住宅、二手住宅价格指数对比。
- 国房景气指数：AkShare `macro_china_real_estate()`，用于刻画全国房地产景气背景。
- 海珠区微观数据仍建议以广州市住建局、阳光家缘、广州市房地产中介协会，以及合规手工采集的贝壳/链家样本作为主补充。
"""
    (ROOT / "data" / "akshare_data_note.md").write_text(note, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    city = fetch_city_price_index()
    climate = fetch_real_estate_climate_index()
    write_source_note()
    print("AkShare data fetched.")
    print(f"City index rows: {len(city)}")
    print(f"Climate index rows: {len(climate)}")


if __name__ == "__main__":
    main()
