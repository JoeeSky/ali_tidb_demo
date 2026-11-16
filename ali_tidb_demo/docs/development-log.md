# TiDB Cloud × 阿里云百炼 Agent Demo 实施记录

> 开始日期：2026-11-16
> 当前阶段：Starter、Embedding 与百炼生成调用已获用户实测反馈；准备 MCP 工具服务
> 目标读者：需要快速集成、演示和验证 TiDB 与百炼 AI 能力的一线 SA  
> 本文性质：持续更新的真实实施记录，不是最终使用指南。最终指南将在 Demo 完成后依据实测结果整理。

## 1. 记录原则

- 明确区分**离线测试通过**、**用户云端实测通过**和**尚未验证**，不把代码骨架描述为已验证产品能力。
- 助手负责架构讲解、代码、SQL、离线测试、命令准备和故障分析。
- 用户负责控制台配置、凭证管理以及会连接云端、修改数据、部署服务或产生费用的实际操作。
- 文档不记录真实密码、API Key、Token、完整连接串、云资源内网地址或其他敏感标识。
- 每一步保留操作命令、预期结果、实际结果、问题与解决方式，为后续 SA 指南提供依据。

## 2. 当前实施范围

基础版优先打通：

```text
用户问题
→ 百炼 Agent 2.0
→ MCP 工具服务
→ TiDB Cloud Starter
→ 知识检索、销售汇总和长期偏好
→ 百炼生成有依据的回答
```

基础版包括：

- TiDB Cloud Starter TLS 连接、数据模型和演示订单。
- 百炼 `text-embedding-v4` 与 TiDB Vector 知识检索。
- MCP 知识检索、销售汇总和长期偏好工具。
- 阿里云函数计算 FC 部署与公网鉴权。
- 百炼 Agent 2.0 配置、发布和 API 调用。
- TiDB 会话、消息、长期记忆与事件记录。
- 端到端功能验收。

Filesystem、Lake、OSS 和复杂异步任务暂不阻塞基础版。基础版验收后再分别评估增强阶段；OSS 不是 Lake 分析的强制中转层。

## 3. 已确认的本地环境

| 项目 | 当前实测结果 |
|---|---|
| 操作系统 | macOS，arm64 |
| Python | 3.12.16 |
| 虚拟环境 | 项目目录 `.venv` |
| MCP Python SDK | 1.30.0 |
| OpenAI Python SDK | 2.54.0 |
| SQLAlchemy | 2.1.8 |
| PyMySQL | 1.2.4 |
| pytest | 9.2.0 |
| 依赖完整性 | `pip check` 通过 |

版本号记录的是本次开发环境，不代表其他环境只能使用这些版本。最终指南将提供可复现安装方式及兼容性说明。

## 4. 配置与安全约定

- 本机私有配置保存在项目根目录 `.env`，该文件已加入 `.gitignore`。
- `.env.example` 只提供空白模板，可以上传 GitHub。
- 真实凭证不发送到聊天，不写入源码、测试、日志或本文档。
- Demo 当前使用 `mysql+pymysql://` DSN，是因为 SQLAlchemy 需要显式选择已安装的 PyMySQL 驱动；TiDB 服务端仍使用 MySQL 兼容协议。
- 基础 `TIDB_DSN` 保留用户已经验证可用的连接配置；目标库通过独立的 `TIDB_DATABASE` 指定。模板默认建议独立 `agent_demo`，用户本次实际选择并验证的是 `demo`。
- 所有云端写入脚本要求显式添加 `--execute`，默认 dry-run。

## 5. 实施过程

### 5.1 指导手册与实施分工

- 已完成《TiDB Cloud × 阿里云百炼：高弹性 AI Agent Demo 指导手册》。手册依据官方资料编写，其中代码最初属于参考骨架，不能视为账号内实测结果。
- 用户确认采用分步学习模式：助手写代码和离线测试，用户亲手完成控制台配置和云端流程。
- 用户确认工程后续上传 GitHub，并需要面向一线 SA 的最终使用指南与各功能验证指导。

### 5.2 本地工程与配置预检

已完成：

- Python 项目与 `src` 包结构。
- `.env.example`、`.gitignore` 和依赖声明。
- 本地配置预检程序，不发起网络请求，不输出凭证内容。
- 检查 DSN、CA 文件、百炼基础配置、Embedding 模型及向量维度。

离线验证：

```text
5 passed
No broken requirements found.
```

问题与解决：

- 初次预检提示 DSN 格式不符合项目要求。
- 安全诊断确认 `.env` 和三项凭证均已读取，问题是 DSN 使用 `mysql://`。
- 将项目 DSN 前缀改为 `mysql+pymysql://`，明确使用已安装的 PyMySQL。
- 用户报告预检已经通过。该结果只代表本地配置格式检查通过，不代表 Starter 或百炼 API 已连通。

### 5.3 第 1 步代码：Starter TLS 连接与数据模型

已新增：

- `src/agent_demo/db.py`：连接 URL、数据库名校验、CA 文件检查和小型连接池。
- `src/agent_demo/check_tidb.py`：只读连接与 TLS 状态检查。
- `src/agent_demo/init_db.py`：显式确认后创建数据库和数据表，并核对表清单。
- `src/agent_demo/seed_demo.py`：显式确认后写入或更新 3 笔演示订单，并核对汇总金额。
- `sql/schema.sql`：8 张 Demo 表的 DDL。
- `tests/test_db.py`：数据库标识符、SQL 文件、表数量和向量维度等离线测试。

设计要点：

- 建库时使用不指定数据库的连接，建表时切换到 `demo`。
- 连接池暂设 `pool_size=2`、`max_overflow=0`，避免本地和后续 FC 弹性实例无约束占用 Starter 连接。
- 订单写入使用参数化 SQL；数据库标识符只允许字母、数字和下划线。
- `document_chunks.embedding` 固定为 `VECTOR(1024)`，与后续百炼 Embedding 输出一致。
- 建表后通过 `information_schema.tables` 核对 8 张表，而不是只依赖 DDL 没有报错。
- 演示订单以 `order_id` 幂等更新，重复执行不会持续插入重复记录。

离线验证：

```text
10 passed in 1.19s
No broken requirements found.
Python compileall 通过
```

Dry-run 实测输出摘要：

```text
目标数据库：demo
待执行 DDL：8 条；预期数据表：8 张
当前是 dry-run，没有连接云端。

将写入或更新 3 笔订单；华东已支付订单预期合计：21400.00
当前是 dry-run，没有连接云端。
```

截至上述首次 dry-run 状态：**用户尚未反馈 Starter 连接、建表和演示订单的云端成功结果。**

### 5.4 目标数据库隔离与 DSN 配置修正

实际试用发现原有 Starter 已有 `demo` 数据库及其他业务表。共用该数据库可能遇到同名表结构冲突，种子数据也可能更新相同主键的已有记录。为避免影响现有数据，目标改为独立的 `agent_demo`。

用户同时指出不应通过反复修改 `TIDB_DSN` 来切换目标库。连接模块已调整为：

- `TIDB_DSN`：保留已经验证可用的基础连接配置，不再为了 Demo 改其数据库路径。
- `TIDB_DATABASE=agent_demo`：显式指定 Demo 目标数据库。
- 建库时由代码移除 DSN 的数据库路径；建表和查询时由代码应用 `TIDB_DATABASE`。
- 云端脚本缺少 `TIDB_DATABASE` 时直接停止，防止回退并误写已有数据库。

重构后离线验证：

```text
12 passed in 0.08s
No broken requirements found.
Python compileall 通过
```

云端初始化过程中出现过报错，但用户未提供具体异常内容，因此本记录不对失败原因作猜测。

### 5.5 第 1 步云端执行结果

用户选择继续使用现有 `demo`，并在了解清理范围后自行处理 Demo 表。2026-11-16，用户明确反馈以下命令全部执行成功：

```bash
.venv/bin/python -m agent_demo.preflight
.venv/bin/python -m agent_demo.init_db --execute
.venv/bin/python -m agent_demo.check_tidb
.venv/bin/python -m agent_demo.seed_demo --execute
```

据此记录：

- Starter TLS 只读连接检查：用户报告成功。
- `demo` 中 8 张 Demo 表初始化：用户报告成功。
- 演示订单写入及程序内汇总核对：用户报告成功。
- 华东已支付订单预期为 2 笔、21400.00，程序只有核对一致才会正常结束。
- 向量索引 DDL 已随初始化成功执行；TiFlash 副本 `AVAILABLE/PROGRESS` 和控制台交叉查询结果尚未单独提供。

上述结果来自用户的实际执行反馈，助手没有代替用户连接云端，也没有独立读取控制台状态。

### 5.6 第 2 步代码：百炼 Embedding 最小调用

已新增 `embeddings.py`、`check_embedding.py` 和对应离线测试：

- 固定 `text-embedding-v4` 和 1024 维，与 TiDB `VECTOR(1024)` 一致。
- OpenAI 兼容接口每批最多 10 条，23 条输入在测试中拆为 10、10、3。
- 校验返回数量、向量维度、数值类型和有限值，避免异常向量进入 TiDB。
- 可选业务空间通过 `X-DashScope-WorkSpace` 请求头发送，不记录其具体值。
- 最小真实调用需要用户显式添加 `--execute`，默认 dry-run 不消耗 API 额度。
- 输出向量数量和维度，并计算相似文本与无关文本的余弦相似度；不以任意固定阈值判断 API 成败。
- 测试期间发现 `load_dotenv` 会从真实 `.env` 回填被测试删除的变量，已通过隔离 dotenv 修正测试环境，避免测试结果依赖本机配置。

离线验证：

```text
19 passed in 0.42s
No broken requirements found.
Python compileall 通过
check_embedding dry-run 通过
```

真实百炼 API 调用：用户于 2026-11-16 报告调用成功。助手未独立查看百炼控制台调用记录。

### 5.7 第 3 步代码：知识导入与 TiDB Vector 检索

已新增 3 篇明确标注为演示语料的 Markdown 文档，以及知识分块、导入和检索代码：

- `return-policy.md`：退换货规则，用于验证语义知识检索与来源返回。
- `tidb-overview.md`：TiDB、HTAP 与向量维度说明。
- `sales-metric.md`：销售指标口径及 21400.00 的原始推导。
- 文档按字符分块，默认 500 字符、50 字符重叠；当前 3 篇短文档各形成 1 个分块。
- 文档 ID 由租户和相对路径确定，内容使用 SHA-256；相同内容且分块数量一致时跳过 Embedding。
- 内容变化时，在同一 TiDB 事务中更新文档并替换该文档的旧分块。
- 向量以 JSON 写入 `VECTOR(1024)`，模型名随分块保存。
- 检索 SQL 在分块和文档连接中均校验租户，使用 `VEC_COSINE_DISTANCE` 排序并返回标题、来源、原文和距离。
- 每次真实检索还使用同一查询向量检查 `sa-isolation-check` 租户，预期返回 0 条。

离线验证：

```text
25 passed in 0.42s
No broken requirements found.
Python compileall 通过
ingest_knowledge dry-run：3 篇文档、3 个分块
search_knowledge dry-run 通过
```

真实知识写入和检索：用户已获操作命令，尚未向助手反馈实际检索输出。

### 5.8 直接 RAG：TiDB 检索后接入百炼生成式模型

用户确认希望在 MCP/Agent 之前先验证生成式模型基于检索资料总结回答。已新增 `generation.py` 和 `answer_question.py`，形成最直观的直接 RAG 链路：

```text
问题 → text-embedding-v4 → TiDB Vector → qwen-max → 带来源回答
```

设计要点：

- 先打印 TiDB 实际返回的资料数量、标题、来源和距离，再打印模型回答，便于区分检索与生成问题。
- 系统提示词限制模型只能依据检索资料，不得用模型记忆补充数字或政策。
- 检索文档放在明确分隔符中，并声明文档指令不是系统命令。
- 要求关键结论使用【资料1】等引用，末尾列出实际使用的标题和 `source_uri`。
- 没有检索结果时直接返回固定降级文案，不调用生成式模型。
- Chat 模型通过 `.env` 中的 `BAILIAN_CHAT_MODEL=qwen-max` 显式配置，脚本不再提供模型默认值；真实账号可用性由用户调用验证。
- `EMBEDDING_MODEL`、`EMBEDDING_DIMENSIONS` 和 `BAILIAN_CHAT_MODEL` 均为预检必填项，所有调用脚本从 `.env` 读取模型定义，避免逐脚本修改或默认值不一致。
- 用户实际 `BAILIAN_BASE_URL` 为新加坡专属 endpoint。Embedding 与生成客户端均强制读取该配置，不在缺失时回退北京；dry-run 会显示实际 URL，文档不记录专属地址。
- 该直接 RAG 程序用于理解基础原理，后续百炼 Agent 2.0 将复用 TiDB 检索能力并通过 MCP 调用。

离线验证：

```text
30 passed in 0.43s
No broken requirements found.
Python compileall 通过
answer_question dry-run 通过
```

真实直接 RAG 调用：用户于 2026-11-16 报告百炼已经验证，记录为生成式模型调用成功。用户尚未提供完整回答文本，因此“7 个自然日”的事实一致性、引用格式和来源列表未由助手独立核验。

## 6. 当前云端验证步骤

以下步骤由用户审查后亲手执行。若上一步失败，先停止并排查，不继续执行后续写入。

### 6.1 只读连接检查

```bash
.venv/bin/python -m agent_demo.check_tidb
```

预期：

- `SELECT 1` 返回 1。
- 当前数据库为 `demo`。
- 能读取 TiDB 版本。
- 能确认 TLS cipher，或根据实际返回进一步检查 TLS 状态。

实际结果：待用户执行并记录。

### 6.2 初始化数据表

先审查 `sql/schema.sql`，再执行：

```bash
.venv/bin/python -m agent_demo.init_db --execute
```

预期：

- 目标数据库 `demo` 可用。
- 8 条 DDL 执行成功。
- 通过 `information_schema.tables` 核对 8 张表。

实际结果：待用户执行并记录。

### 6.3 写入并核对演示订单

```bash
.venv/bin/python -m agent_demo.seed_demo --execute
```

原始数据：

| order_id | tenant_id | region | amount | status | ordered_at |
|---|---|---|---:|---|---|
| o-001 | demo | 华东 | 12800.00 | paid | 2026-11-01 10:00:00 |
| o-002 | demo | 华东 | 8600.00 | paid | 2026-11-02 11:00:00 |
| o-003 | demo | 华南 | 6900.00 | paid | 2026-11-02 12:00:00 |

华东已支付销售额的推导：

```text
12800.00 + 8600.00 = 21400.00
```

预期：`华东订单核对：2 笔，销售额 21400.00`。

实际结果：待用户执行并记录。

### 6.4 控制台交叉验证

用户可在 TiDB Cloud SQL Editor 执行：

```sql
USE demo;

SHOW TABLES;

SELECT region, COUNT(*) AS order_count, SUM(amount) AS revenue
FROM sales_orders
WHERE tenant_id = 'demo' AND status = 'paid'
GROUP BY region
ORDER BY region;
```

预期华东为 2 笔、21400.00；华南为 1 笔、6900.00。

实际结果：待用户执行并记录。

## 7. 验证状态总表

| 能力 | 离线验证 | 云端实测 | 备注 |
|---|---|---|---|
| 工程依赖与导入 | 通过 | 不适用 | 10 项测试通过 |
| 本地配置预检 | 通过 | 不适用 | 用户报告通过 |
| Starter TLS 连接 | 已准备脚本 | 用户报告成功 | 已实际执行 `check_tidb` |
| 数据库与 8 张表初始化 | dry-run 通过 | 用户报告成功 | 已实际执行 `init_db --execute` |
| 向量索引创建 | 已准备 DDL | 用户报告 DDL 成功 | TiFlash 副本状态仍待单独检查 |
| 演示订单写入与汇总 | dry-run 通过 | 用户报告成功 | 程序已核对华东 2 笔、21400.00 |
| 百炼 Embedding | 通过 | 用户报告成功 | 1024 维最小调用已验证 |
| TiDB Vector 检索 | 39 项总测试通过 | 用户实测成功 | MCP 检索首选退换货政策，距离 0.21127326723673234 |
| 直接 RAG 生成回答 | 32 项总测试通过 | 用户报告百炼验证成功 | 回答事实与引用细节未独立核验 |
| MCP 工具 | 39 项总测试通过 | 用户实测成功 | initialize/list_tools/三个 call_tool 均成功；偏好待 SQL 交叉核对 |
| 百炼 Agent 2.0 | 尚未开始 | 尚未开始 | 控制台配置由用户完成 |
| 会话与长期记忆 | 尚未开始 | 尚未开始 | 区分百炼临时会话与 TiDB 持久记录 |

## 8. 后续记录与最终指南安排

后续每完成一步，在本文补充：

1. 代码和配置变更。
2. 关键原理及设计取舍。
3. 离线测试命令和真实结果。
4. 用户执行的云端步骤和实际结果。
5. 报错、原因、修复和仍需注意的限制。
6. 可转化为 SA 演示的验证问题及预期输出。

Demo 完成后，另行整理详细工程使用指南，计划包含：快速启动、架构说明、目录与模块、配置项、控制台操作、本地运行、FC 部署、百炼 Agent 配置、逐功能验证、故障排查、安全与成本边界、清理资源和常见演示话术。最终指南只收录经过实际验证或明确标注验证边界的操作。

## 9. 本地 MCP 三工具服务（2026-11-16）

新增 `mcp_server.py` 和 `verify_mcp.py`，使用当前已安装的 MCP Python SDK / FastMCP，通过 Streamable HTTP 暴露 `/mcp`。模块导入时不创建数据库连接；TiDB Engine 和百炼 Embedder 在首次调用工具时延迟初始化。

三个工具的边界：

- `search_knowledge(query, limit)`：百炼生成查询向量后调用 TiDB Vector 检索，返回标题、来源、原文和距离；只读。
- `summarize_sales(region, start, end)`：固定 `status='paid'` 的参数化聚合 SQL，时间区间左闭右开；只读，不开放任意 SQL。
- `remember_preference(user_id, preference)`：仅在用户明确要求时保存非敏感偏好；根据租户、用户和内容生成稳定 `memory_id`，重复验证幂等更新。
- 三个工具均不接收 `tenant_id`，服务端从 `DEMO_TENANT_ID` 读取，避免模型自行切换数据边界。

离线验证：

```text
39 passed
Python compileall 通过
verify_mcp dry-run 通过
FastMCP 工具注册检查通过
内存 MCP initialize / list_tools / 三次 call_tool 通过（模拟后端，无云端连接）
```

验证脚本通过真实 MCP `initialize`、`list_tools` 和 `call_tool` 调用，而不是把普通 Python 函数测试冒充协议验证。真实云端调用由用户执行。

### 9.1 用户真实 MCP 验证结果

用户于 2026-11-16 提供完整成功输出：

- MCP 初始化成功，服务名为 `tidb-enterprise-agent`，工具列表完整包含三个工具。
- `search_knowledge` 返回 3 条资料。第一条为《Demo 企业退换货政策》，来源 `demo://data/knowledge/return-policy.md`，包含“7 个自然日”，余弦距离为 `0.21127326723673234`；其余两条距离分别为 `0.5703428983688323` 和 `0.7416867978888866`。首条距离最小，与预期语义排序一致。
- `summarize_sales` 对华东、`[2026-11-01, 2026-12-01)`、`paid` 返回 `order_count=2`、`revenue="21400.00"`，与原始订单 `12800.00 + 8600.00 = 21400.00` 一致。
- `remember_preference` 返回 `status="saved"`、`memory_id="mem-277f917cec20e63b781eee8f"`，保存用户 `sa-demo-user` 的“先展示收入，再展示订单量。”偏好。
- 工具返回值证明 MCP 调用和事务路径完成；仍需用户在 TiDB SQL Editor 查询该行，完成独立于应用程序的交叉核对。

## 10. Function AI 托管与百炼注册准备（2026-11-16）

用户希望使用百炼 MCP 能力托管。官方文档核实结果：

- 百炼“脚本部署 → uvx”会把 Python stdio MCP 部署到函数计算；官方 FAQ 对自研 Python 包说明的正式路径是发布到公共 PyPI。
- 为避免额外发布 PyPI，本工程选择官方支持的另一条路径：Function AI 绑定 GitHub、云端构建 Python 工程，将 stdio MCP 代理为 HTTPS/SSE，再由百炼通过 HTTP 注册并统一管理。
- Function AI 可生成只读 Bearer Token；服务变量支持加密。部署地域和可用功能以用户控制台实际显示为准，不能照搬文档中的北京示例。
- FC 无固定出口公网 IP；如 TiDB 或其他远程资源设置来源白名单，需要按官方文档配置 FC 白名单或 VPC 网络，不能假设本地连接成功就代表 FC 可连接。

代码与配置变更：

- `mcp_server.py` 新增 `--transport stdio|streamable-http`，本地默认 HTTP，Function AI 启动命令显式使用 stdio。
- `pyproject.toml` 新增 `tidb-agent-mcp` 可安装命令；Function AI 构建命令使用 `pip install -t . .`，依赖在 Linux 云端安装，避免 macOS arm64 本地二进制包不兼容。
- 新增 `deploy/bailian-mcp-http.example.json`，使用 `type=sse` 和占位 URL / Bearer Token；真实 Token 不写入文件或 Git。
- `.env.example` 新增 `MCP_TRANSPORT=streamable-http`，真实 `.env` 仍只用于本机，不上传。

离线结果：

```text
40 passed
Python compileall 通过
verify_mcp dry-run 通过
pip install --dry-run --no-deps . 通过
```

云端 Function AI 部署、工具测试、百炼注册和 Agent 挂载均待用户按步骤执行。未执行前不声称托管成功。

### 10.1 GitHub 发布方式调整（2026-11-16）

- 用户工作机不允许本地安装 Git、不允许本地上传，已放弃 `git push` 路线，本地未创建提交、未推送任何内容。
- 改为在本地生成干净副本 `github-upload/ali_tidb_demo/`（31 个文件），由用户通过 GitHub 网页拖拽上传。
- 副本已排除 `.env`、`.venv`、`.git`、缓存和构建产物；敏感信息扫描未发现真实 API Key、TiDB 主机、专属百炼 endpoint 或 Token，仅文档中出现 "Bearer Token" 字样说明。
- `.env.example` 与 `deploy/bailian-mcp-http.example.json` 均为空白模板，可公开上传；真实凭证仍只留在用户本机 `.env`。
