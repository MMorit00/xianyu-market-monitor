# MOZShop 闲鱼市场雷达改造计划

> 更新日期：2026-04-28

## 仓库关系

本项目是 `Usagi-org/ai-goofish-monitor` 的 fork，用于 MOZShop 的卖家版改造。

```text
origin   = https://github.com/MMorit00/xianyu-market-monitor.git
upstream = https://github.com/Usagi-org/ai-goofish-monitor.git
branch   = mozshop-seller-radar
```

本地目录：

```text
MOZShop/xianyu-market-monitor/
```

`upstream` 只用于拉取原作者更新，禁止向上游推送。

## 产品定位

第一阶段只做闲鱼站内追新，不做全网舆情系统。

目标是回答：

```text
闲鱼里最近哪些关键词、课程、资料包、工具、工作流正在增长？
我们是否应该快速跟进？
如果跟进，标题、详情、主图短句、自动回复应该怎么写？
```

边界：

- 不做自动上架。
- 不做自动私聊。
- 不替代 `xianyu-auto-reply-me`。
- 不直接处理付款、发货、确认收货。
- 不改动抓取核心，除非趋势功能必须新增字段。

## 与 MOZShop 的分工

```text
xianyu-market-monitor
  -> 闲鱼站内趋势扫描
  -> 竞品价格/标题/卖点分析
  -> 生成卖家动作建议和文案草稿

products/
  -> 我们自己的商品档案、链接、发货配置

product-copy/
  -> 对外发布用标题、详情、主图短句、回复话术

xianyu-auto-reply-me
  -> 买家消息处理、自动回复、自动发货
```

## 第一阶段 MVP

1. 保留原项目基线
   - 跑通原版后台、前端、账号登录态和一个测试监控任务。
   - 不急着改 `src/scraper.py`。
   - 状态：已完成基础构建、后端健康检查和单元/集成测试基线。

2. 卖家视角 Prompt
   - 从“是否值得购买”改成“是否值得卖家跟进”。
   - 输出竞品标题关键词、卖点、价格区间、风险词和建议动作。

3. 趋势关键词池
   - 维护一批种子词，例如 `AI课程`、`ComfyUI`、`工作流`、`提示词`、`副业资料`。
   - 定时扫描并保存每次快照。
   - 状态：已完成后端关键词池表、服务和 API，接口文档见 `docs/trend-keyword-api.md`。

4. 增长榜
   - 统计新增商品数、近 24 小时上架数、近 3 天增长、新卖家数量、想要人数和价格区间。
   - 输出“今日增长最快”“适合快速跟进”“低竞争机会”。

5. 文案草稿导出
   - 将 AI 分析结果导出到 `../product-copy/xianyu/trends/`。
   - 每个趋势生成一个 Markdown 文件，供人工确认后进入正式商品流程。

## 详细实施计划

后续实施以 `docs/mozshop-seller-radar-implementation-plan.md` 为准。

当前优先级：

1. 趋势快照：保存每次关键词扫描的结构化数据。
2. 弱竞争机会评分：输出 `A/B/C/D` 等级、理由和动作建议。
3. 趋势机会榜：让卖家每天看到“今天该测什么、继续观察什么、放弃什么”。
4. AI 竞品总结：只基于快照和商品样本做总结，不凭空选品。
5. 文案草稿导出：人工确认后再进入 `product-copy` 和 `autoreply`。

## 上游同步流程

```bash
cd /Users/panlingchuan/Downloads/My_Project/MOZShop/xianyu-market-monitor
git switch mozshop-seller-radar
git fetch upstream
git merge upstream/master
```

如冲突优先保留上游爬虫修复，再重新套用卖家版页面、Prompt、趋势服务改动。

## 改造原则

- 新功能尽量新增模块，不直接重写上游核心爬虫。
- 趋势相关服务优先放在 `src/services/`，数据库字段采用增量迁移。
- 前端新增页面优先独立路由，避免把原结果页改得难以合并上游。
- 与 `xianyu-auto-reply-me` 的打通先通过文件导出完成，不直接写它的数据库。
