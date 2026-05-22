"""Try to collect public second-hand housing listing samples.

This script is intentionally conservative:
- it only requests public list pages;
- it does not bypass login, CAPTCHA, anti-bot checks, or hidden APIs;
- it records blocked/unavailable platforms in a status log;
- it uses the scraped data only as listing-price samples, not transaction prices.
"""

from __future__ import annotations

import csv
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

PLATFORMS = [
    ("链家", "https://gz.lianjia.com/ershoufang/haizhu/"),
    ("贝壳", "https://gz.ke.com/ershoufang/haizhu/"),
    ("58同城", "https://gz.58.com/haizhu/ershoufang/"),
    ("安居客", "https://guangzhou.anjuke.com/sale/haizhu/"),
    ("房天下", "https://gz.esf.fang.com/house-a074/"),
]


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)


def request_page(url: str) -> tuple[int | str, str, str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        title = ""
        match = re.search(r"<title>(.*?)</title>", resp.text, flags=re.I | re.S)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip()
        return resp.status_code, title, resp.text
    except Exception as exc:  # noqa: BLE001 - status log should keep every failure
        return "ERROR", str(exc), ""


def write_platform_status() -> None:
    rows = []
    for platform, url in PLATFORMS:
        status, title, html = request_page(url)
        html_path = RAW / f"{platform}_haizhu_page1.html"
        if html:
            html_path.write_text(html, encoding="utf-8")
        if platform in {"链家", "贝壳", "58同城", "安居客"}:
            blocked = any(keyword in title.upper() for keyword in ["登录", "CAPTCHA", "验证码"]) or len(html) < 2000
        else:
            blocked = False
        rows.append(
            {
                "platform": platform,
                "url": url,
                "http_status": status,
                "title_or_error": title,
                "html_length": len(html),
                "usable_for_auto_parse": platform == "房天下" and status == 200 and not blocked,
                "note": "公开页面可解析" if platform == "房天下" and status == 200 else "返回登录/验证码/壳页面或连接失败，未继续自动采集",
            }
        )
        time.sleep(1.5)
    pd.DataFrame(rows).to_csv(CLEAN / "platform_scrape_status.csv", index=False, encoding="utf-8-sig")


def parse_fang_html(html: str, page_url: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for item in soup.select("div.shop_list dl.clearfix"):
        title_node = item.select_one("h4 a[title]")
        info_node = item.select_one("p.tel_shop")
        add_node = item.select_one("p.add_shop")
        price_node = item.select_one("dd.price_right span.red b")
        unit_node = item.select_one("dd.price_right span:not(.red)")

        title = title_node.get("title", "").strip() if title_node else ""
        href = title_node.get("href", "") if title_node else ""
        info_parts = [
            re.sub(r"\s+", " ", text).strip()
            for text in info_node.stripped_strings
            if text.strip() != "|"
        ] if info_node else []

        community = ""
        submarket = ""
        address = ""
        if add_node:
            community_node = add_node.select_one("a")
            community = community_node.get_text(strip=True) if community_node else ""
            spans = [s.get_text(" ", strip=True) for s in add_node.select("span")]
            if spans:
                add_text = re.sub(r"\s+", " ", spans[0]).strip()
                pieces = add_text.split(" ", 1)
                submarket = pieces[0] if pieces else ""
                address = pieces[1] if len(pieces) > 1 else ""

        area_m2 = None
        for part in info_parts:
            match = re.search(r"([\d.]+)\s*㎡", part)
            if match:
                area_m2 = float(match.group(1))
                break

        total_price_10k = None
        if price_node:
            try:
                total_price_10k = float(price_node.get_text(strip=True))
            except ValueError:
                pass

        unit_price = None
        if unit_node:
            match = re.search(r"([\d,]+)\s*元/㎡", unit_node.get_text(strip=True))
            if match:
                unit_price = int(match.group(1).replace(",", ""))

        rows.append(
            {
                "source": "房天下",
                "collection_date": date.today().isoformat(),
                "district": "海珠",
                "submarket": submarket,
                "community": community,
                "title": title,
                "rooms": info_parts[0] if len(info_parts) > 0 else "",
                "area_m2": area_m2,
                "floor": info_parts[2] if len(info_parts) > 2 else "",
                "orientation": info_parts[4] if len(info_parts) > 4 else "",
                "total_price_10k": total_price_10k,
                "unit_price_yuan_m2": unit_price,
                "address": address,
                "url": urljoin(page_url, href),
                "page_url": page_url,
                "notes": "公开挂牌样本，挂牌价不等于成交价",
            }
        )
    return rows


def scrape_fang(max_pages: int = 2) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for page in range(1, max_pages + 1):
        url = "https://gz.esf.fang.com/house-a074/" if page == 1 else f"https://gz.esf.fang.com/house-a074/i3{page}/"
        status, title, html = request_page(url)
        (RAW / f"fang_haizhu_page{page}.html").write_text(html, encoding="utf-8")
        if status != 200 or "海珠二手房" not in title:
            break
        rows.extend(parse_fang_html(html, url))
        time.sleep(2)
    df = pd.DataFrame(rows).drop_duplicates(subset=["url"])
    df.to_csv(CLEAN / "fang_haizhu_secondhand_listings_sample.csv", index=False, encoding="utf-8-sig")
    return df


def write_summary(df: pd.DataFrame) -> None:
    summary_path = CLEAN / "secondhand_listing_collection_summary.md"
    if df.empty:
        summary = "# 二手房挂牌样本采集摘要\n\n未能合规采集到可解析挂牌样本。\n"
    else:
        by_submarket = (
            df.groupby("submarket", dropna=False)
            .agg(samples=("url", "count"), median_unit_price=("unit_price_yuan_m2", "median"))
            .reset_index()
            .sort_values("samples", ascending=False)
        )
        table = by_submarket.to_markdown(index=False)
        summary = f"""# 二手房挂牌样本采集摘要

- 采集日期：{date.today().isoformat()}
- 可解析来源：房天下
- 样本数量：{len(df)}
- 价格口径：公开挂牌价，不代表真实成交价

## 板块样本概览

{table}
"""
    summary_path.write_text(summary, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    write_platform_status()
    df = scrape_fang(max_pages=2)
    write_summary(df)
    print(f"Parsed Fang listings: {len(df)}")
    print(CLEAN / "fang_haizhu_secondhand_listings_sample.csv")
    print(CLEAN / "platform_scrape_status.csv")


if __name__ == "__main__":
    main()
