# MOZShop 闲鱼卖家雷达实施计划

> 更新日期：2026-04-29

## 目标判断

`xianyu-market-monitor` 的目标不是做一个通用爬虫，也不是做全网舆情系统，而是做 MOZShop 的闲鱼站内选品决策系统。

它每天需要回答四个问题：

1. 闲鱼站内哪些关键词或商品形态正在增长？
2. 哪些增长机会还没有被大量卖家卷烂？
3. MOZShop 是否具备快速上架测试的能力？
4. 如果要跟进，标题、详情、主图短句、咨询钩子和自动回复应该怎么写？

第一阶段的核心指标不是“热度”，而是“弱竞争爆品机会”。

## 系统边界

当前阶段只做：

- 闲鱼站内关键词追新。
- 搜索结果快照沉淀。
- 弱竞争机会评分。
- 竞品标题、价格、卖点分析。
- 文案草稿导出。

当前阶段不做：

- 全网舆情分析。
- 自动上架。
- 自动私聊陌生买家。
- 自动改价。
- 付费推广自动化。
- 直接写入 `xianyu-auto-reply-me` 数据库。

`xianyu-auto-reply-me` 只接收经过人工确认的成熟商品话术，不能直接接收未验证趋势。

## 仓库分工

```text
xianyu-market-monitor
  -> 站内追新、竞品分析、机会评分、动作建议

product-copy/
  -> 已确认可发布的商品标题、详情、主图短句、回复话术

products/
  -> MOZShop 自有商品档案、交付资料、发货配置

xianyu-auto-reply-me/
  -> 买家咨询处理、自动回复、自动发货
```

推荐链路：

```text
趋势关键词池
  -> 趋势快照
  -> 弱竞争机会评分
  -> 候选品池
  -> AI 文案草稿
  -> 人工确认
  -> product-copy
  -> 成熟商品接入 autoreply
```

## 阶段一：趋势快照

现状：已经完成趋势关键词池。

下一步需要为每个关键词保存连续快照。单次搜索只能说明“当前情况”，连续快照才能说明“增长趋势”。

### trend_snapshots

每次扫描一个关键词，生成一条快照：

```text
keyword_id
keyword
category
snapshot_time
total_results
new_items_24h
new_items_3d
seller_count
new_seller_count
min_price
max_price
median_price
want_count_total
want_count_avg
title_terms_json
title_repetition_rate
same_image_count
low_price_item_ratio
opportunity_score
opportunity_level
growth_score
competition_score
profit_score
freshness_score
execution_score
reasons_json
action
raw_metrics_json
```

说明：

- `competition_score` 表示“低竞争机会分”，分数越高代表竞争越轻。
- `opportunity_level` 使用 `A/B/C/D`。
- `raw_metrics_json` 保存尚未结构化但以后可能有用的数据，避免频繁改表。

### trend_items

每条快照保留若干商品样本：

```text
snapshot_id
item_id
title
price
price_display
seller_nickname
want_count
publish_time
link
image_key
raw_json
```

商品样本用于后续 AI 竞品总结，不直接等同于正式商品库。

## 阶段二：弱竞争机会评分

机会评分拆成五个维度：

```text
增长分 growth_score
竞争分 competition_score
利润分 profit_score
新鲜度 freshness_score
可执行性 execution_score
```

建议权重：

```text
opportunity_score =
  growth_score * 0.30
  + competition_score * 0.25
  + profit_score * 0.15
  + freshness_score * 0.15
  + execution_score * 0.15
```

等级：

```text
A: 75-100  今天生成上架测试稿
B: 60-74   继续观察 1-3 天
C: 45-59   有热度但不建议立即跟
D: 0-44    暂时放弃
```

评分要输出理由，而不是只输出分数。例如：

```text
增长较快，近 24 小时上新明显
卖家数量还不高，标题重复度低
价格带健康，暂未被低价打穿
适合 MOZShop 快速做成资料包或教程
```

## 阶段三：趋势增长榜

后端提供三个视角：

```text
今日增长最快
低竞争机会
建议上架测试
```

前端页面不急着复杂化，先做一个能筛选和排序的表：

```text
关键词
分类
机会等级
机会分
新增商品数
卖家数
价格中位数
想要数
建议动作
最近扫描时间
```

## 阶段四：AI 竞品总结

AI 只在有数据基础后介入，不直接凭空选品。

输入：

```text
趋势快照
商品样本
标题高频词
价格分布
卖家包装信息
```

输出：

```text
为什么火
谁在买
同行主打卖点
同行弱点
MOZShop 切入角度
风险词
建议上架形态
```

## 阶段五：文案草稿导出

高机会趋势生成 Markdown 草稿，导出到：

```text
../product-copy/xianyu/trends/
```

草稿结构：

```text
# 趋势机会：关键词

## 机会判断
## 竞品观察
## 推荐商品形态
## 标题备选
## 主图短句
## 详情页草稿
## 咨询钩子
## 自动回复草稿
## 风险词提醒
## 是否建议接入 autoreply
```

导出后必须人工确认，确认后才进入正式 `product-copy`。

## 阶段六：候选品池

趋势不是商品。趋势只有进入候选品池后，才开始成为运营对象。

状态：

```text
watching
suggested
drafted
listed
validating
scaling
rejected
archived
```

候选品记录：

```text
来源关键词
趋势快照
竞品样本
AI 分析
文案草稿路径
上架时间
曝光
浏览
询单
成交
是否进入 autoreply
```

## 阶段七：漏斗反馈

后续需要让系统看见自己的商品表现：

```text
曝光 -> 浏览 -> 询单 -> 成交 -> 好评
```

初期可以人工录入数据。系统根据漏斗判断问题：

```text
曝光高、浏览低：主图或标题问题
浏览高、询单低：详情页、价格、咨询钩子问题
询单高、成交低：回复话术或信任感问题
长期无曝光：关键词或类目问题
```

## 当前落实顺序

第一轮落实只做后端闭环：

1. 新增 `trend_snapshots` 和 `trend_items` 表。
2. 新增趋势快照 Pydantic 模型。
3. 新增趋势快照服务。
4. 创建快照时自动计算基础指标。
5. 创建快照时自动生成机会评分、等级、理由和动作建议。
6. 新增快照 API 和机会榜 API。
7. 补充单元测试和集成测试。

暂不做前端页面和真实抓取调度，避免过早耦合上游爬虫。
