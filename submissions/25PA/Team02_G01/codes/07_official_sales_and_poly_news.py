"""Fetch Guangzhou official sales data and Poly Haiyun news case facts."""

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
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
OUTPUT = ROOT / "output"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

OFFICIAL_ENDPOINTS = {
    "saleable": "https://zfcj.gz.gov.cn/ysqgk/Api/WebApi/mrxjspfksxx.ashx",
    "unsold": "https://zfcj.gz.gov.cn/ysqgk/Api/WebApi/mrxjspfwsxx.ashx",
    "signed": "https://zfcj.gz.gov.cn/ysqgk/Api/WebApi/mrxjspfqyxx.ashx",
}

POLY_NEWS = [
    {
        "source": "新浪财经/乐居财经",
        "url": "https://finance.sina.com.cn/stock/estate/zc/2026-05-10/doc-inhxmeai7686815.shtml",
    },
    {
        "source": "新浪财经/财经网",
        "url": "https://finance.sina.com.cn/roll/2026-05-11/doc-inhxnwmm1954255.shtml",
    },
    {
        "source": "财联社/界面新闻",
        "url": "https://www.cls.cn/detail/2368514",
    },
    {
        "source": "证券时报/证券日报",
        "url": "https://www.stcn.com/article/detail/3908087.html",
    },
    {
        "source": "新快报",
        "url": "https://xxsb.gz-cmc.com/pages/2026/05/10/9316ee36c2ab4a1a9648ea36537b43c9.html",
    },
    {
        "source": "东方财富",
        "url": "https://finance.eastmoney.com/a/202605153738077714.html",
    },
]


def ensure_dirs() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    CLEAN.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def setup_style() -> None:
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False
    sns.set_theme(style="whitegrid", font="Microsoft YaHei")


def fetch_official_daily_sales() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for metric, url in OFFICIAL_ENDPOINTS.items():
        raw_path = RAW / f"official_new_home_daily_{metric}.json"
        try:
            resp = requests.post(url, headers={**HEADERS, "Referer": "https://zfcj.gz.gov.cn/zfcj/tjxx/spfxstjxx/index.html"}, timeout=30)
            resp.raise_for_status()
            raw_path.write_text(resp.text, encoding="utf-8")
            payload = resp.json()
        except Exception:
            if not raw_path.exists():
                raise
            payload = requests.models.complexjson.loads(raw_path.read_text(encoding="utf-8"))
        for item in payload.get("data", []):
            rows.append({"metric": metric, **item})
        time.sleep(1)

    df = pd.DataFrame(rows)
    rename = {
        "sectionName": "district",
        "createTime": "date",
        "zhuZaiTaoShu": "residential_units",
        "zhuZaiArea": "residential_area_m2",
        "shangYeTaoShu": "commercial_units",
        "shangYeArea": "commercial_area_m2",
        "banGongTaoShu": "office_units",
        "banGongArea": "office_area_m2",
        "cheWeiTaoShu": "parking_units",
        "cheWeiArea": "parking_area_m2",
    }
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    for col in [c for c in df.columns if c.endswith("_units") or c.endswith("_m2")]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.to_csv(CLEAN / "official_guangzhou_new_home_daily_sales.csv", index=False, encoding="utf-8-sig")

    haizhu = df[df["district"] == "海珠区"].copy()
    haizhu.to_csv(CLEAN / "official_haizhu_new_home_daily_sales.csv", index=False, encoding="utf-8-sig")
    return df


def fetch_existing_home_monthly_links() -> pd.DataFrame:
    url = "https://zfcj.gz.gov.cn/xysj/fwxx/clfjydjtjxx/index.html"
    raw_path = RAW / "official_existing_home_monthly_index.html"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        raw_path.write_text(resp.text, encoding="utf-8")
        html = resp.text
    except Exception:
        if raw_path.exists():
            html = raw_path.read_text(encoding="utf-8")
        else:
            fallback = RAW / "official_zfcj_gz_gov_cn_xysj_fwxx_clfjydjtjxx_index_html.html"
            if not fallback.exists():
                raise
            html = fallback.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for li in soup.select("div.pageList li"):
        a = li.select_one("a[title]")
        t = li.select_one("span.time")
        if not a:
            continue
        rows.append(
            {
                "title": a.get("title", "").strip(),
                "publish_date": t.get_text(strip=True) if t else "",
                "url": urljoin(url, a.get("href", "")),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(CLEAN / "official_existing_home_monthly_links.csv", index=False, encoding="utf-8-sig")
    return df


def plot_official_new_home_sales(df: pd.DataFrame) -> None:
    signed = df[df["metric"] == "signed"].copy()
    signed = signed.sort_values("residential_units", ascending=False)
    plt.figure(figsize=(10.5, 5.8))
    colors = ["#c75f4f" if d == "海珠区" else "#4c78a8" for d in signed["district"]]
    sns.barplot(data=signed, x="district", y="residential_units", palette=colors, hue="district", legend=False)
    for i, row in enumerate(signed.itertuples(index=False)):
        plt.text(i, row.residential_units, f"{row.residential_units:.0f}", ha="center", va="bottom", fontsize=9)
    date_value = signed["date"].iloc[0] if not signed.empty else ""
    plt.title(f"广州市各区新建商品住宅每日签约套数（{date_value}）")
    plt.xlabel("")
    plt.ylabel("住宅签约套数")
    plt.xticks(rotation=35, ha="right")
    plt.savefig(OUTPUT / "fig09_official_new_home_signed_units_by_district.png", dpi=220, bbox_inches="tight")
    plt.close()

    stock = df[df["district"] == "海珠区"].copy()
    label_map = {"saleable": "可售", "unsold": "未售", "signed": "签约"}
    stock["metric_cn"] = stock["metric"].map(label_map)
    plt.figure(figsize=(7.5, 5.2))
    sns.barplot(data=stock, x="metric_cn", y="residential_units", color="#4c78a8")
    for i, row in enumerate(stock.itertuples(index=False)):
        plt.text(i, row.residential_units, f"{row.residential_units:.0f}", ha="center", va="bottom", fontsize=9)
    plt.title(f"海珠区新建商品住宅可售、未售与签约套数（{stock['date'].iloc[0]}）")
    plt.xlabel("")
    plt.ylabel("住宅套数")
    plt.savefig(OUTPUT / "fig10_official_haizhu_new_home_status.png", dpi=220, bbox_inches="tight")
    plt.close()


def clean_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return title, text


def extract_poly_facts(text: str) -> dict[str, object]:
    facts: dict[str, object] = {}
    patterns = {
        "launch_date": r"5月10日",
        "sold_out_time": r"(90秒|两分半钟|2分半钟|150秒|两分钟)",
        "units": r"(超?300多套|300余套|超300套|300套)",
        "sales_amount": r"(18\.2亿元|18亿元|约18亿元|认购金额约18\.2亿元|首日认购金额达18亿元)",
        "avg_price": r"(5\.97万元/平方米|5\.97万元/㎡|成交均价约5\.97万元/平方米)",
        "price_range": r"(5\.5万[元至到\\-—]+6\.4万元/平方米|5\.5-6\.5万元/㎡|5\.5万至6\.4万元/平方米)",
        "total_price_range": r"(510-1100万元|总价区间510-1100万元|总价510万元起)",
        "subscription": r"(认筹超过700组|认筹量就已突破700组|前期获超700组认筹)",
        "location": r"(海珠区南泰路|位于海珠区南泰路|海珠西)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        facts[key] = match.group(1) if match and match.groups() else (match.group(0) if match else "")
    return facts


def fetch_poly_news() -> pd.DataFrame:
    rows = []
    for item in POLY_NEWS:
        url = item["url"]
        source = item["source"]
        slug = re.sub(r"[^A-Za-z0-9]+", "_", source).strip("_")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=35)
            if resp.encoding is None or resp.encoding.lower() in {"iso-8859-1", "latin-1"}:
                resp.encoding = resp.apparent_encoding
            status = resp.status_code
            if "sina.com.cn" in url:
                html = resp.content.decode("utf-8", errors="replace")
            else:
                html = resp.text
            (RAW / f"poly_haiyun_news_{slug}.html").write_text(html, encoding="utf-8")
            title, text = clean_text(html)
            facts = extract_poly_facts(text)
            rows.append(
                {
                    "source": source,
                    "url": url,
                    "http_status": status,
                    "title": title,
                    "text_length": len(text),
                    **facts,
                }
            )
        except Exception as exc:  # noqa: BLE001 - keep crawl status visible
            rows.append({"source": source, "url": url, "http_status": "ERROR", "title": str(exc), "text_length": 0})
        time.sleep(1.5)

    df = pd.DataFrame(rows)
    df.to_csv(CLEAN / "poly_haiyun_news_summary.csv", index=False, encoding="utf-8-sig")

    key_facts = {
        "开盘日期": "2026年5月10日",
        "项目位置": "广州市海珠区南泰路/海珠西片区",
        "首推房源": "超300套/300多套",
        "售罄用时": "约90秒至2分半钟，不同媒体表述略有差异",
        "销售金额": "约18亿至18.2亿元",
        "价格区间": "主流售价约5.5万-6.4万元/平方米，总价约510万-1100万元",
        "认筹热度": "开盘前认筹超过700组",
        "解释口径": "热销说明优质项目和改善需求集中释放，不代表海珠区所有房源普涨",
    }
    pd.DataFrame([{"fact": k, "value": v} for k, v in key_facts.items()]).to_csv(
        CLEAN / "poly_haiyun_key_facts.csv", index=False, encoding="utf-8-sig"
    )
    return df


def main() -> None:
    ensure_dirs()
    setup_style()
    official = fetch_official_daily_sales()
    fetch_existing_home_monthly_links()
    plot_official_new_home_sales(official)
    news = fetch_poly_news()
    print("Official and Poly Haiyun data updated.")
    print(f"Official rows: {len(official)}")
    print(f"News rows: {len(news)}")


if __name__ == "__main__":
    main()
