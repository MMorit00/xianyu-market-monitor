# 趋势关键词池 API

> 更新日期：2026-04-29

趋势关键词池用于维护“闲鱼站内追新”要扫描的种子词。当前阶段只做关键词管理，尚不触发实际抓取。

基础路径：

```text
/api/trends
```

## 列表

```http
GET /api/trends/keywords
GET /api/trends/keywords?include_disabled=true
```

返回：

```json
{
  "items": [
    {
      "id": 1,
      "keyword": "ComfyUI 工作流",
      "category": "AI",
      "enabled": true,
      "notes": "重点观察",
      "created_at": "2026-04-29T00:00:00Z",
      "updated_at": "2026-04-29T00:00:00Z"
    }
  ]
}
```

默认只返回启用关键词。传 `include_disabled=true` 时返回全部。

## 创建

```http
POST /api/trends/keywords
Content-Type: application/json
```

Body：

```json
{
  "keyword": "ComfyUI 工作流",
  "category": "AI",
  "enabled": true,
  "notes": "重点观察"
}
```

重复关键词返回 `409`。

## 详情

```http
GET /api/trends/keywords/{keyword_id}
```

不存在返回 `404`。

## 更新

```http
PATCH /api/trends/keywords/{keyword_id}
Content-Type: application/json
```

Body 可只传部分字段：

```json
{
  "enabled": false,
  "notes": "暂停观察"
}
```

重复关键词返回 `409`，不存在返回 `404`。

## 删除

```http
DELETE /api/trends/keywords/{keyword_id}
```

不存在返回 `404`。

## 本地健康检查

```bash
SERVER_PORT=8010 .venv/bin/python -m src.app

curl http://127.0.0.1:8010/api/trends/keywords
curl -X POST http://127.0.0.1:8010/api/trends/keywords \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"ComfyUI 工作流","category":"AI"}'
```
