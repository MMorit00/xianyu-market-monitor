# 趋势快照与机会榜 API

> 更新日期：2026-04-29

趋势快照用于记录某个关键词在某次扫描中的市场状态，并自动生成弱竞争机会评分。

基础路径：

```text
/api/trends
```

## 创建快照

```http
POST /api/trends/snapshots
Content-Type: application/json
```

可以使用关键词池里的 `keyword_id`：

```json
{
  "keyword_id": 1,
  "total_results": 12,
  "items": [
    {
      "item_id": "123",
      "title": "ComfyUI 工作流 AI绘画资料包",
      "price": "59",
      "seller_nickname": "A店",
      "want_count": "24",
      "publish_time": "2小时前",
      "link": "https://example.com/1",
      "image_key": "image-fingerprint"
    }
  ]
}
```

也可以直接传临时关键词：

```json
{
  "keyword": "副业资料包",
  "category": "资料",
  "total_results": 80,
  "new_items_24h": 1,
  "new_items_3d": 4,
  "seller_count": 45,
  "median_price": 19.9,
  "want_count_avg": 3
}
```

返回：

```json
{
  "message": "趋势快照已创建",
  "item": {
    "id": 1,
    "keyword_id": 1,
    "keyword": "ComfyUI 工作流",
    "category": "AI",
    "snapshot_time": "2026-04-29T00:00:00Z",
    "total_results": 12,
    "new_items_24h": 2,
    "new_items_3d": 4,
    "seller_count": 3,
    "median_price": 64,
    "want_count_total": 63,
    "opportunity_score": 77.3,
    "opportunity_level": "A",
    "reasons": [
      "有一定增长，需要继续观察能否延续。",
      "竞争压力暂时不高，卖家数量、标题重复或同款图压力可控。"
    ],
    "action": "今天生成上架测试稿，建议用 2-3 个标题/主图角度小流量测试。",
    "items": []
  }
}
```

## 快照列表

```http
GET /api/trends/snapshots
GET /api/trends/snapshots?keyword_id=1
GET /api/trends/snapshots?keyword=ComfyUI%20工作流&limit=20
```

默认按 `snapshot_time` 倒序返回。

## 快照详情

```http
GET /api/trends/snapshots/{snapshot_id}
GET /api/trends/snapshots/{snapshot_id}?include_items=true
```

`include_items=true` 时返回本次快照保存的商品样本。

## 机会榜

```http
GET /api/trends/opportunities
GET /api/trends/opportunities?level=A
GET /api/trends/opportunities?latest_only=false&limit=50
```

默认每个关键词只取最新快照，并按 `opportunity_score` 从高到低排序。

等级含义：

```text
A: 今天生成上架测试稿
B: 继续观察 1-3 天
C: 有热度但暂不建议立即跟
D: 暂时放弃
```

## 评分说明

机会分由五个维度组成：

```text
growth_score       增长分
competition_score  低竞争机会分，越高代表竞争越轻
profit_score       利润分
freshness_score    新鲜度
execution_score    MOZShop 可执行性
```

权重：

```text
opportunity_score =
  growth_score * 0.30
  + competition_score * 0.25
  + profit_score * 0.15
  + freshness_score * 0.15
  + execution_score * 0.15
```
