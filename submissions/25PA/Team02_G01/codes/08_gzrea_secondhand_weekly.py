"""Fetch Guangzhou Real Estate Intermediary Association weekly second-hand data."""

from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin

import matplotlib.pyplot as plt
import pandas as pd
import requests
import seaborn as sns
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
OUTPUT = ROOT / "output"
BASE = "https://www.gzrea.org.cn/website/"
LIST_URL = "https://www.gzrea.org.cn/website/website_scyj_scyjTabsList.action?pdid=205&type=0"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://www.gzrea.org.cn/website/website_scyj_scyjList.action?pdid=205",
}


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def setup_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def fetch_list() -> pd.DataFrame:
    resp = requests.get(LIST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    (RAW / "gzrea_secondhand_weekly_list.html").write_text(resp.text, encoding="utf-8")
    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for li in soup.select("li"):
        a = li.select_one("a[href]")
        if not a:
            continue
        title = a.get_text(" ", strip=True)
        if "二手住宅网签数据" not in title:
            continue
        date_text = ""
        date_match = re.search(r"(20\d{2}-\d{2}-\d{2})", li.get_text(" ", strip=True))
        if date_match:
            date_text = date_match.group(1)
        rows.append(
            {
                "publish_date": date_text,
                "title": title,
                "url": urljoin(BASE, a.get("href", "")),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(CLEAN / "gzrea_secondhand_weekly_links.csv", index=False, encoding="utf-8-sig")
    return df


def parse_detail(row: pd.Series) -> dict[str, object]:
    url = row["url"]
    detail_id = re.search(r"id=(\d+)", url)
    slug = detail_id.group(1) if detail_id else re.sub(r"\W+", "_", row["title"])
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text
    raw_path = RAW / f"gzrea_secondhand_weekly_detail_{slug}.html"
    raw_path.write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    title = soup.select_one("h3.title_r5")
    title_text = title.get_text(" ", strip=True) if title else row["title"]

    week_match = re.search(r"(\d{1,2}月\d{1,2}日-\d{1,2}月\d{1,2}日)", title_text)
    units = None
    for pattern in [
        r"二手住宅网签[^0-9]{0,12}([\d,]+)宗",
        r"二手住宅共计?网签([\d,]+)宗",
        r"二手住宅网签量为([\d,]+)宗",
        r"全市二手住宅[^0-9]{0,12}([\d,]+)宗",
        r"二手住宅共计?成交([\d,]+)宗",
        r"二手住宅共成交([\d,]+)宗",
        r"增长至([\d,]+)宗",
        r"回升至([\d,]+)宗",
        r"达到([\d,]+)宗",
    ]:
        match = re.search(pattern, text)
        if match:
            units = int(match.group(1).replace(",", ""))
            break

    haizhu_note = ""
    match = re.search(r"海珠区[^。；;]{0,30}(?:超过|达|为)?\d+宗|番禺区和海珠区[^。；;]{0,40}", text)
    if match:
        haizhu_note = match.group(0)

    image_urls = []
    for img in soup.select("img[src]"):
        src = img.get("src", "")
        if "/upload/editor/" in src:
            full = urljoin(url, src)
            image_urls.append(full)
    for idx, img_url in enumerate(image_urls, start=1):
        try:
            img_resp = requests.get(img_url, headers=HEADERS, timeout=30)
            img_resp.raise_for_status()
            suffix = Path(img_url).suffix or ".png"
            (RAW / f"gzrea_secondhand_weekly_{slug}_table{idx}{suffix}").write_bytes(img_resp.content)
        except Exception:
            pass

    return {
        "publish_date": row.get("publish_date", ""),
        "week": week_match.group(1) if week_match else title_text,
        "title": title_text,
        "secondhand_residential_signed_units": units,
        "haizhu_note": haizhu_note,
        "url": url,
        "raw_html": str(raw_path.relative_to(ROOT)),
        "evidence_image_count": len(image_urls),
    }


def fetch_details(limit: int = 10) -> pd.DataFrame:
    links = fetch_list()
    rows = []
    for _, row in links.head(limit).iterrows():
        rows.append(parse_detail(row))
        time.sleep(1.2)
    df = pd.DataFrame(rows)
    df.to_csv(CLEAN / "gzrea_secondhand_weekly_signed_units.csv", index=False, encoding="utf-8-sig")
    return df


def plot_weekly_units(df: pd.DataFrame) -> None:
    chart = df.dropna(subset=["secondhand_residential_signed_units"]).copy()
    chart = chart.iloc[::-1].reset_index(drop=True)
    plt.figure(figsize=(10.5, 5.8))
    sns.lineplot(data=chart, x="week", y="secondhand_residential_signed_units", marker="o", linewidth=2.2, color="#2f5597")
    for idx, row in chart.iterrows():
        plt.text(idx, row["secondhand_residential_signed_units"], f"{int(row['secondhand_residential_signed_units'])}", ha="center", va="bottom", fontsize=9)
    plt.title("广州市二手住宅周度网签宗数")
    plt.xlabel("周期")
    plt.ylabel("二手住宅网签宗数")
    plt.xticks(rotation=35, ha="right")
    plt.savefig(OUTPUT / "fig11_gzrea_secondhand_weekly_signed_units.png", dpi=220, bbox_inches="tight")
    plt.close()


def main() -> None:
    ensure_dirs()
    setup_style()
    df = fetch_details(limit=10)
    plot_weekly_units(df)
    print("GZREA weekly second-hand data updated.")
    print(f"Rows: {len(df)}")


if __name__ == "__main__":
    main()
