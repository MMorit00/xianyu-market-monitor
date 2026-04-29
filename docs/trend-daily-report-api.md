# 闲鱼 AI 机会日报 API

> 更新日期：2026-04-29

第一版日报只做最小闭环：

```text
趋势快照机会榜
  -> 规则评分 Top 10
  -> AI 审核
  -> Top 5 日报
  -> Bark 推送
```

当前日报基于已经写入 `trend_snapshots` 的机会数据生成。真实关键词扫描接入后，日报会在扫描完成后消费最新快照。

基础路径：

```text
/api/trends
```

## 手动生成日报

```http
POST /api/trends/daily-report/run
Content-Type: application/json
```

Body：

```json
{
  "candidate_limit": 10,
  "push": true
}
```

说明：

- `candidate_limit`：进入 AI 审核的候选数量，范围 `1-20`。
- `push`：是否发送 Bark 推送。

返回：

```json
{
  "message": "闲鱼机会日报已生成",
  "item": {
    "id": 1,
    "report_date": "2026-04-29",
    "status": "completed",
    "candidate_snapshot_ids": [3, 2, 1],
    "ai_review": {
      "daily_summary": "今天优先看 AI 商品图方向。",
      "items": [
        {
          "snapshot_id": 3,
          "keyword": "AI商品图工作流",
          "rank": "A",
          "should_push": true,
          "why": "上新快，卖家少。",
          "sell_angle": "资料包 + 新手教程。",
          "advantages": ["标准化交付"],
          "risks": ["教程需要跑通"],
          "next_action": "建议今天查看。"
        }
      ]
    },
    "push_title": "闲鱼 AI 机会日报",
    "push_body": "【闲鱼 AI 机会日报】...",
    "push_channel": "bark",
    "push_status": "sent",
    "error_message": "",
    "created_at": "2026-04-29T01:00:00Z",
    "sent_at": "2026-04-29T01:00:02Z"
  }
}
```

## 查看最近日报

```http
GET /api/trends/daily-report/latest
```

没有日报时返回 `404`。

## 测试 Bark 日报推送

```http
POST /api/trends/daily-report/send-test
Content-Type: application/json
```

Body：

```json
{
  "title": "闲鱼 AI 机会日报测试",
  "body": "这是一条 Bark 日报测试通知。"
}
```

返回：

```json
{
  "message": "测试通知已执行",
  "result": {
    "channel": "bark",
    "success": true,
    "message": "发送成功"
  }
}
```

## Bark 配置

在 `.env` 配置：

```text
BARK_URL=https://api.day.app/你的key
```

## 定时配置

应用启动时会注册每日机会日报定时任务。

默认：

```text
TREND_DAILY_REPORT_ENABLED=true
TREND_DAILY_REPORT_CRON=0 9 * * *
```

关闭：

```text
TREND_DAILY_REPORT_ENABLED=false
```

修改为每天 21:30：

```text
TREND_DAILY_REPORT_CRON=30 21 * * *
```

## 失败兜底

- AI 未配置：使用规则评分生成日报。
- AI 返回异常：保存规则评分日报，并记录错误。
- Bark 未配置或发送失败：日报照常保存，`push_status=failed`。
- 没有机会数据：生成“今日暂无明显机会”日报。
