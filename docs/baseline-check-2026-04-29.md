# 基线验证记录 2026-04-29

## 环境

```text
Python: 3.11.1 (.venv)
Node: v25.6.1
npm: 11.9.0
Branch: mozshop-seller-radar
```

本地虚拟环境：

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd web-ui && npm ci
```

`.venv/` 和 `web-ui/node_modules/` 通过 `.git/info/exclude` 本地忽略，不进入仓库。

## 验证结果

前端构建通过：

```bash
cd web-ui
npm run build
```

后端导入通过：

```bash
.venv/bin/python -c "import src.app; print('backend import ok')"
```

单元测试通过：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/unit -q
# 83 passed
```

服务启动和基础接口通过：

```bash
SERVER_PORT=8010 .venv/bin/python -m src.app
curl http://127.0.0.1:8010/health
curl -X POST http://127.0.0.1:8010/auth/status \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}'
```

返回结果：

```json
{"status":"healthy","message":"服务正常运行"}
{"authenticated":true,"username":"admin"}
```

根页面返回 `200 text/html`。

## 基线修复

`tests/unit/test_utils.py::test_save_to_jsonl` 初次运行失败，原因是默认 `active` 状态被注入到返回记录的内部字段 `_status`。默认状态不需要暴露给结果调用方，前端只需要识别 `hidden` 等非默认状态。

已调整 `src/services/result_storage_service.py`：仅当状态存在且不是 `active` 时才附加 `_status`。

## 尚未验证

- 未跑真实闲鱼抓取任务，因为当前未导入闲鱼登录态。
- 未测试 AI 分析，因为当前没有配置 `.env` 中的 `OPENAI_BASE_URL` 和 `OPENAI_MODEL_NAME`。
- 未安装 Playwright Chromium 浏览器；实际抓取前需要执行 `.venv/bin/python -m playwright install chromium`，或确认本机 Chrome 可被 Playwright 使用。
