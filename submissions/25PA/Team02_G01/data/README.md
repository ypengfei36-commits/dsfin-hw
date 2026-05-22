# 数据来源与获取方案

## 1. 官方与可复现数据源

| 数据 | 用途 | 获取方式 | 备注 |
|---|---|---|---|
| 国家统计局房地产开发投资、商品房销售、70 城房价指数 | 全国房地产背景、广州价格指数 | 国家统计局官网或 AkShare | 可复现，适合报告主线 |
| AkShare `macro_china_new_house_price()` | 广州新房/二手房价格指数，与北上深对比 | `codes/01_get_data_akshare.py` | 城市级，不能到海珠区 |
| AkShare `macro_china_real_estate()` | 国房景气指数 | `codes/01_get_data_akshare.py` | 宏观背景指标 |
| 广州市住建局/阳光家缘 | 广州一手住宅网签、楼盘信息 | 手动查询、截图或整理表格 | 推荐作为广州/海珠新房主数据 |
| 广州市房地产中介协会 | 广州二手住宅月度网签、市场运行简报 | 手动整理公开文章/报告 | 推荐作为二手房市场主数据 |
| 用户补充链家海珠二手房源 CSV | 海珠区二手房挂牌价、面积、户型、楼龄等微观样本 | `data/raw/lianjia_haizhu_secondhand_user.csv` | 30 条样本，代表挂牌报价，不等于成交价 |
| 用户补充贝壳海珠一手房 CSV | 海珠区一手项目参考均价、总价、户型和地址 | `data/raw/beike_haizhu_newhome_user.csv` | 31 条样本，代表平台参考价 |

## 2. 链家/贝壳数据可行性

链家和贝壳适合作为海珠区二手房挂牌样本与楼盘案例补充，但不建议作为唯一主数据源。

可行做法：

1. **贝壳开放平台**：如果能申请或获得接口权限，可以使用授权接口或 RealData 产品获取更稳定的数据。
2. **手工样本采集**：在贝壳/链家公开页面人工记录 30-50 个海珠区挂牌样本，包括小区、板块、面积、总价、单价、户型、楼龄、采集日期和 URL。
3. **案例采集**：记录保利海韵、琶洲南 TOD、海珠西等新盘公开报道中的推盘数量、开盘价格、去化情况。

不建议做法：

- 不建议大规模自动化抓取链家/贝壳网页，因为页面结构、反爬机制和网站条款可能导致不可复现或合规风险。
- 不建议直接把挂牌价等同于成交价。报告中必须说明“挂牌价代表卖方预期，不代表最终成交价格”。

## 2.1 平台自动采集尝试结果

本项目尝试访问以下公开页面，结果记录在 `data/clean/platform_scrape_status.csv`。

| 平台 | 结果 | 后续处理 |
|---|---|---|
| 链家 | 返回登录页 | 不继续自动化采集，建议手工样本或授权接口 |
| 贝壳 | 返回 CAPTCHA 页面 | 不绕过验证码，建议开放平台授权接口或手工样本 |
| 58 同城 | 返回验证码/短页面 | 不继续自动化采集 |
| 安居客 | 返回短壳页面 | 不继续自动化采集 |
| 房天下 | 海珠区公开列表页可解析 | 低频采集前 2 页，得到 120 条挂牌样本 |

已生成样本文件：`data/clean/fang_haizhu_secondhand_listings_sample.csv`。

## 2.2 用户补充链家/贝壳样本

用户补充的两份 CSV 已纳入项目：

- 链家海珠二手房源：`data/raw/lianjia_haizhu_secondhand_user.csv`
- 贝壳海珠一手房：`data/raw/beike_haizhu_newhome_user.csv`

清洗脚本为 `codes/09_integrate_user_house_data.py`，输出：

- `data/clean/lianjia_haizhu_secondhand_user_clean.csv`
- `data/clean/beike_haizhu_newhome_user_clean.csv`
- `data/clean/user_house_data_summary.csv`
- `output/fig12_lianjia_secondhand_unit_price_distribution.png`
- `output/fig13_beike_newhome_total_price_band.png`
- `output/fig14_user_house_sample_comparison.png`

## 3. 建议采集字段

### 贝壳/链家手工样本字段

| 字段 | 说明 |
|---|---|
| source | 贝壳/链家 |
| collection_date | 采集日期 |
| district | 区，例如海珠 |
| submarket | 板块，例如琶洲、赤岗、江南西、工业大道等 |
| community | 小区或楼盘名称 |
| total_price_10k | 总价，万元 |
| unit_price_yuan_m2 | 单价，元/平方米 |
| area_m2 | 建筑面积 |
| rooms | 户型 |
| build_year | 建成年份 |
| url | 页面链接 |

## 4. 本报告的数据主线

建议采用“三层证据”：

1. 全国与广州宏观：国家统计局/AkShare。
2. 广州和海珠成交热度：住建局、阳光家缘、广州市房地产中介协会。
3. 海珠区微观样本：用户补充链家/贝壳样本 + 房天下挂牌样本 + 保利海韵案例。
