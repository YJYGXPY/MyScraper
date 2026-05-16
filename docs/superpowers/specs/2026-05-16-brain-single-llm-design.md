# Brain 模块单一 LLM 配置设计

## 1. 目标与范围

本设计用于将 `brain.py` 从“多 provider 概念”收敛为“单一 LLM 配置”模型，并统一命名为：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

本次只涉及配置与命名体系重构，不改变分析 schema 与业务目标，不改动 `scrape.py` 的抓取行为。

## 2. 现状问题

当前 `brain.py` 存在以下不一致：

1. 运行时实际上只使用一个后端，但代码接口仍保留 `provider` 参数与 `LLM_CONFIG["ark"]` 结构。
2. 环境变量采用 `ARK_*` 命名，表达的是“特定厂商”而非“通用 LLM 配置”。
3. README 中参数说明仍与旧命名耦合，增加使用者理解成本。

这些问题导致“概念上支持多 provider，但实践上只有一个 provider”的认知偏差。

## 3. 设计决策

### 3.1 配置模型

采用单一扁平配置对象，不再按 provider 嵌套：

- `api_key <- LLM_API_KEY`
- `base_url <- LLM_BASE_URL`
- `model <- LLM_MODEL`

缺失任意一项时立即抛出明确错误，并在错误文案中仅提示 `LLM_*` 变量。

### 3.2 接口模型

去除 provider 概念后，统一函数签名：

- `chat(prompt: str) -> str`
- `_call_llm_json(prompt: str, max_retry: int = 2) -> dict[str, Any]`
- `generate_keywords(keyword: str) -> list[str]`
- `analyze_data(data_path: str) -> str`

删除所有 `provider` 参数与其传递链路。

### 3.3 文档模型

README 的 `.env` 示例统一为：

```env
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://your-openai-compatible-endpoint/v1
LLM_MODEL=your_model_name
```

README 中删除 provider/ark 相关描述，改为“当前使用单一 LLM 配置”。

## 4. 数据流与行为保持

重构后调用数据流如下：

1. `generate_keywords()` / `analyze_data()` 进入 LLM 调用路径。
2. `chat()` 加载单一 LLM 配置并创建 OpenAI 兼容 client。
3. `_call_llm_json()` 负责 JSON 输出校验与重试。
4. 结果继续沿用现有 Markdown 渲染与落盘路径。

业务行为保持不变：

- 关键词派生逻辑不变。
- 分析 schema 不变。
- 报告落盘路径与命名不变。

## 5. 错误处理设计

### 5.1 配置错误

- 场景：`LLM_API_KEY/LLM_BASE_URL/LLM_MODEL` 缺失
- 策略：在配置加载阶段直接抛错，明确列出缺失字段

### 5.2 模型输出错误

- 场景：模型未返回可解析 JSON
- 策略：保持现有重试策略，追加“仅返回合法 JSON”约束再试

### 5.3 向后兼容策略

本次按确认方案执行“硬切换”：

- 不读取 `ARK_*`
- 不保留 provider 回退分支

目的：保持命名唯一来源，避免双轨配置长期并存。

## 6. 实施边界

### 6.1 需要修改

- `brain.py`：配置读取、函数签名、provider 相关代码删除
- `README.md`：`.env` 配置与说明更新
- `.env`（本地开发环境）：变量名迁移到 `LLM_*`

### 6.2 不需要修改

- `scrape.py` 抓取流程
- `main.py` 执行顺序与参数策略
- 分析报告 schema 结构

## 7. 验收标准

满足以下条件即视为完成：

1. `brain.py` 中不再出现 `provider` 参数与多 provider 配置结构。
2. 代码仅使用 `LLM_API_KEY / LLM_BASE_URL / LLM_MODEL`。
3. README 与代码配置命名一致，不再出现 `ARK_*` 使用指引。
4. 以 `LLM_*` 配置运行时，关键词派生与分析链路可用。

## 8. 风险与回滚

### 8.1 风险

- 本地仍使用旧 `ARK_*` 的环境会在升级后立即报配置缺失。

### 8.2 回滚

- 若上线后需要临时兼容旧环境，可在单独变更中增加一次性兼容读取（优先 `LLM_*`，回退 `ARK_*`），但该方案不在本次实现范围内。
