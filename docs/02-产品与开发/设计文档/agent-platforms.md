# Web AI 销售助手：开源 Agent 平台与工作流框架调研

## 一、哪些平台和框架适合本项目

### Takeaway

建议采用“自建销售业务 Web 前端与业务服务 + LangGraph 工作流 + 自有产品能力库”的架构。Dify、FastGPT、RAGFlow、Langflow 适合作为独立知识/编排服务或原型参照；不建议整站 fork 后强行改造成录音销售工作台。该结论是针对本项目的工程判断，并非官方性能排名。

### Cited Findings

调研基准为 2026-10-15、Asia/Shanghai。下表覆盖 14 个项目，均实取其官方仓库 README、LICENSE 与仓库 API；每个项目的“适用判断”属于本调研推论，功能和许可事实以所附官方来源为准。

| 项目 | 官方能力事实与本项目可复用部分 | 许可事实 | 本项目适用判断 | 官方文档/依据 |
|---|---|---|---|---|
| Dify | 可视化 AI workflow、知识 RAG、模型与工具集成、观测；支持 Docker Compose 和自托管 | 修改版 Apache-2.0；多租户环境需要授权；使用其前端时不得移除/修改品牌及版权，完全不涉及其前端的使用有品牌条款例外 | 适合内部试验、知识检索/生成 API 服务；不宜默认拿其管理前端去品牌化销售，也不能认为换自有前端即可绕过多租户限制 | [README](https://github.com/langgenius/dify/blob/main/README.md)、[LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)、[自托管文档](https://docs.dify.ai/getting-started/install-self-hosted) |
| FastGPT | 官方定位为知识驱动平台，覆盖文档处理、RAG 检索及可视化 AI 工作流；提供 Docker 自部署 | Apache-2.0 附加条件；类似 FastGPT 的多租户 SaaS 需书面授权；不得移除/修改控制台 LOGO/版权 | 国内知识应用原型候选；适合以 API 接入产品知识，SaaS 和品牌二开需先审查许可 | [README](https://github.com/labring/FastGPT/blob/main/README.md)、[LICENSE](https://github.com/labring/FastGPT/blob/main/LICENSE)、[部署](https://doc.fastgpt.io/self-host/deploy/docker) |
| RAGFlow | 深度文档理解、复杂版式知识提取、Agentic retrieval、可视化工作流、引用；README 列出 PDF/扫描件、Word、PPT、Excel 等文档；可部署 Docker | Apache-2.0 | 若自有产品手册/历史方案的表格和扫描件很多，可用独立检索服务；先测资源和真实检索质量，再决定是否引入整套部署 | [README](https://github.com/infiniflow/ragflow/blob/main/README.md)、[LICENSE](https://github.com/infiniflow/ragflow/blob/main/LICENSE)、[文档](https://ragflow.io/docs/dev/) |
| Flowise | 历史上提供可视化 Agent 构建及自托管；当前 README 顶部明确“Flowise has been archived”，API 的 archived=true | 核心 Apache-2.0；enterprise 目录及带明确商业版权文件适用商业许可；不能只看 README 底部 Apache 简写 | 可借鉴节点交互，不作为新平台的核心依赖；归档状态须在选型时明确呈现 | [README](https://github.com/FlowiseAI/Flowise/blob/main/README.md)、[仓库 API](https://api.github.com/repos/FlowiseAI/Flowise)、[LICENSE](https://github.com/FlowiseAI/Flowise/blob/main/LICENSE.md)、[商业许可](https://github.com/FlowiseAI/Flowise/blob/main/packages/server/src/enterprise/LICENSE.md)、[官方未来说明](https://github.com/FlowiseAI/Flowise/discussions/6727) |
| Langflow | 可视化作者工具，内置 API 与 MCP server，可将 workflow 暴露为应用可调用工具；支持主要模型、向量库、工具，自托管 | MIT | 适合让技术人员试验检索链和工具；开发者画布不是销售用户工作台，建议后台使用 | [README](https://github.com/langflow-ai/langflow/blob/main/README.md)、[LICENSE](https://github.com/langflow-ai/langflow/blob/main/LICENSE)、[文档](https://docs.langflow.org/) |
| LangGraph | 面向长时间、带状态工作流，支持持久化、人工中断、恢复、streaming；有 Python 与 JS 实现，可独立于 LangChain 使用 | 本次审阅 Python 仓库为 MIT；LangSmith 部署/观测服务是不同产品边界，不能从 MIT 推定商业托管服务免费 | 推荐主编排候选：事实提取→校核→产品检索→方案/清单→一致性检查→人工确认→导出；采用持久 PostgreSQL checkpointer | [README](https://github.com/langchain-ai/langgraph/blob/main/README.md)、[LICENSE](https://github.com/langchain-ai/langgraph/blob/main/LICENSE)、[持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) |
| OpenAI Agents SDK | Agent、工具、handoff、guardrails、tracing、voice pipeline；README 声明 provider agnostic；Sessions 可保持多轮历史，RunState 可序列化暂停的运行 | Python SDK MIT；模型服务、托管工具和 tracing 服务不由 SDK 开源许可证免除费用与数据处理条件 | 轻量替代方案；适合少量工具/明确流程；会话历史、审批状态和业务任务重试仍需显式设计，不因 Sessions 而自动获得录音持久化 | [README](https://github.com/openai/openai-agents-python/blob/main/README.md)、[LICENSE](https://github.com/openai/openai-agents-python/blob/main/LICENSE)、[Sessions](https://openai.github.io/openai-agents-python/sessions/)、[人工介入](https://openai.github.io/openai-agents-python/human_in_the_loop/) |
| Pydantic AI | 基于类型的 Agent、工具参数验证与结构化输出；官方 durable execution 支持 Temporal、DBOS、Prefect、Restate 等运行时；官方明确“Durability is not storage” | MIT | 若希望重视需求清单字段验证，可作为主 SDK 替代 LangGraph 内部 Agent 层；首版也可只采用普通 Pydantic 数据验证，避免叠加两个编排框架 | [README](https://github.com/pydantic/pydantic-ai/blob/main/README.md)、[LICENSE](https://github.com/pydantic/pydantic-ai/blob/main/LICENSE)、[结构化输出](https://pydantic.dev/docs/ai/core-concepts/output/)、[持久执行](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/) |
| Agno | Agent runtime、API/SSE/WebSocket、会话/知识/trace 存储、工具集成、人工确认、JWT RBAC、多租户隔离及容器部署是其 README 列明能力 | Apache-2.0 | 偏完整 Agent runtime，可用作独立后端候选；仍需自建会议与产品业务模型，不能以框架宣称替代租户隔离测试 | [README](https://github.com/agno-agi/agno/blob/main/README.md)、[LICENSE](https://github.com/agno-agi/agno/blob/main/LICENSE)、[文档](https://docs.agno.com) |
| Mastra | TypeScript 框架，支持图式 workflow、then/branch/parallel、suspend/resume、storage、RAG、模型与 Web UI 集成；配置的 storage 保存 snapshot 可跨重启恢复 | 核心 Apache-2.0；所有 ee/ 目录适用 Enterprise License，生产使用需有效书面协议和 License Key | 全 TypeScript 团队的主备选；不可把整个仓库标为无条件 Apache，也不能直接把企业权限模块当免费功能 | [README](https://github.com/mastra-ai/mastra/blob/main/README.md)、[LICENSE](https://github.com/mastra-ai/mastra/blob/main/LICENSE.md)、[EE 许可](https://github.com/mastra-ai/mastra/blob/main/ee/LICENSE)、[暂停恢复](https://mastra.ai/docs/workflows/suspend-and-resume) |
| AutoGen | 当前 README 明确 Maintenance Mode：不再新增特性、由社区维护，并建议新用户使用 Microsoft Agent Framework | 根 LICENSE 为 CC-BY-4.0；代码 LICENSE-CODE 为 MIT，不能把 GitHub 自动识别的 CC 许可直接当全部代码许可 | 排除新建主框架；仅作为多 Agent 模式及迁移资料来源 | [README](https://github.com/microsoft/autogen/blob/main/README.md)、[LICENSE](https://github.com/microsoft/autogen/blob/main/LICENSE)、[代码许可](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE) |
| Microsoft Agent Framework | .NET/Python Agent 与图工作流；顺序/并行/handoff/group 等模式、checkpoint、streaming、human in the loop；AutoGen README 称其为生产稳定继任者 | MIT | 若后续主要接入微软/.NET 企业系统，可作为主框架备选；首版 Python 销售助手不需要为多语言而增加复杂度 | [README](https://github.com/microsoft/agent-framework/blob/main/README.md)、[LICENSE](https://github.com/microsoft/agent-framework/blob/main/LICENSE)、[工作流文档](https://learn.microsoft.com/en-us/agent-framework/workflows/overview) |
| CrewAI | Python 角色协作 Agent 和事件驱动 Flows；任务支持 output_pydantic/output_json；README 将精确流程控制与协作 Agent 区分 | MIT；另售的企业控制平面不因此自动免费 | 适合研究/分工任务；本项目主线是有证据的确定步骤，若采用应以 Flow 为主，限制自主讨论次数 | [README](https://github.com/crewAIInc/crewAI/blob/main/README.md)、[LICENSE](https://github.com/crewAIInc/crewAI/blob/main/LICENSE)、[文档](https://docs.crewai.com) |
| Haystack | Python AI 编排、模块化 pipeline、检索/排序/过滤/路由、工具调用、memory、evaluation；可自定义透明 RAG 流程 | Apache-2.0；另有 Haystack Enterprise Platform 托管/自托管产品 | 若重点是可测量检索而不是低代码平台，适合作产品库检索实现层；不承担会议录音底层可靠性 | [README](https://github.com/deepset-ai/haystack/blob/main/README.md)、[LICENSE](https://github.com/deepset-ai/haystack/blob/main/LICENSE)、[文档](https://docs.haystack.deepset.ai/docs/intro) |

维护状态只陈述本次 API/README 快照：Flowise archived=true；AutoGen README 明确维护模式；其余 12 个本次 API 快照 archived=false。`pushed_at` 是仓库任意推送时间，并不代表正式发布、安全修复、服务承诺或代码质量；原始时间存于对应 `.firecrawl/20261015-agent-{name}-meta.json`，不能据此声称某框架“生产最稳定”。[GitHub 仓库 API 示例：Flowise](https://api.github.com/repos/FlowiseAI/Flowise)、[AutoGen 状态声明](https://github.com/microsoft/autogen/blob/main/README.md)

### Inferences

- 优先选“能将业务流程表达为明确状态、检查点和人工确认”的框架，不以 Agent 数量、星数、演示视频作为选型指标。
- 本项目首页、历史纪要、产品库、工作台均是销售业务界面。平台的开发者管理控制台不能直接代替，建议自有 UI 统一呈现录音、保存、事实来源、生成与下载状态。
- 产品库应储存企业自有真实产品、已核实能力、限制、集成前提、交付方式、有效版本与材料来源；不是插件市场。检索服务只是读取业务产品库的一条路径。
- 推荐主组合为 React/Next.js 前端、FastAPI 业务后端、PostgreSQL + 对象存储、异步作业 worker、LangGraph + Pydantic schema；复杂产品文档可选择 RAGFlow 或 Haystack 之一，无须同时安装全部平台。
- 主方案只使用 LangGraph 作为文档编排引擎，直接通过模型适配层调用模型；不同时叠加 Agents SDK、Pydantic AI、CrewAI、Mastra。这里的 Pydantic schema 指普通数据验证库，不是第二个 Agent 框架。
- 轻量备选是“PostgreSQL 持久步骤表 + 普通异步 worker + Agents SDK”；仅当生成流程能保持短线性步骤、无需图状态修改/检查点重放、团队愿意负责步骤恢复代码，且断电重启/重复消息/人工确认后继续测试全部通过时改用该方案。若已经选轻量方案，出现长时间人工等待、多个分支重跑或修改事实后只重算受影响节点等需求时，再通过适配层切到 LangGraph。框架切换不会替换会议/产品/版本等业务表。
- 同为工具 schema 并不意味着工具权限已实现。工具参数中的 tenant_id/project_id 必须由服务端用户会话注入并校验，不能接受模型自行扩大范围。

### Gaps

- 未对 14 个项目做同机性能、漏洞、代码量、部署成本或中文方案质量实测；不提供无依据的优劣分数和硬件承诺。
- Flowise 官方 future discussion 链接已从 README 发现，但该讨论正文未读取；本报告仅使用已验证的归档状态，不推断归档原因。
- 未逐个审计仓库所有依赖、模型权重、插件与镜像许可；本文只核对列出的根许可及发现的商业目录，实施前应锁定版本再做依赖清单审查。

## 二、如何将 Agent 能力放入销售会议平台

### Takeaway

将持续录音、实时转写、持久业务事实、生成作业和文档产物分成不同责任边界。Agent 的 checkpoint 恢复只覆盖其工作流状态，不等于麦克风音频已经安全保存；音频和转写可靠性应由业务数据管线单独保障。

### Cited Findings

- LangGraph 将 checkpointer 的线程状态持久化与 Store 的跨线程数据持久化区分；InMemorySaver 只在内存，重启即丢失，官方建议生产使用持久 PostgresSaver。[持久化说明](https://docs.langchain.com/oss/python/langgraph/persistence)
- LangGraph 的 checkpoint 有 `exit`、`async`、`sync` 三种 durability；`exit` 不能覆盖运行中进程崩溃，`async` 存在写入窗口，`sync` 在下一步执行前完成保存。重放 checkpoint 后面的节点会重新执行模型/API 请求，不能假定业务副作用恰好一次。[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)
- LangGraph 提供节点重试、超时和错误处理；官方节点 retry 的默认处理范围是具体异常规则，不能推导出任意业务错误会自动修复。[Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- OpenAI Agents SDK Sessions 保存特定会话的对话历史；RunState 支持把暂停审批状态序列化到数据库或队列并在之后恢复，这两者是不同状态对象。[Sessions](https://openai.github.io/openai-agents-python/sessions/)、[Human in the loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- Pydantic AI 官方专门强调“Durability is not storage”，说明运行跨崩溃恢复与聊天会话存取是两个问题；输出类型验证也只保证符合数据约束，不能推出业务事实真实。[持久执行](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)、[输出验证](https://pydantic.dev/docs/ai/core-concepts/output/)
- Mastra 的 suspend/resume 需要配置 storage 来保存工作流 snapshot，官方描述其可跨部署与应用重启恢复。[Suspend and resume](https://mastra.ai/docs/workflows/suspend-and-resume)

### Inferences

建议的确定性流程如下；每个节点均属于本项目设计建议，非已实现能力：

1. 会议服务建立会议 ID 与录音会话 ID，录音/上传不等待模型调用；实时转写与音频存储解耦。
2. 录音数据分片和已落盘确认状态由业务服务维护，Agent 工作流只引用不可变的音频/转写版本，不把音频二进制塞进 workflow state。
3. 会议结束或用户触发生成时，冻结转写校对版本，抽取 `meeting_facts`、`decisions`、`requirements`、`open_questions`，每项保留 segment_id/time range/source revision。
4. 按已确认产品版本检索能力/限制/案例依据；历史方案与样板只用于组织方式或已授权参考，不自动成为当前客户事实。
5. 需求匹配输出“可满足 / 有前提 / 需定制评估 / 不支持 / 待确认”及来源，方案中严格区分会议结论、产品事实和乙方建议。
6. 生成会议纪要、售前解决方案、需求清单、甲方资料/权限/规则确认清单；默认单版，只有当前会议明确要求分期才进入分期模式。
7. 规则节点检查事实来源、未确认价格/排期、擅自分期、产品能力夸大、清单与正文编号不一致等问题；错误需修订，重要未确认项保留在讨论稿。
8. 以 `meeting_revision + product_revision + template_revision + generator_version` 作为产物版本键；每个生成节点有 operation_id/幂等键，重试不能重复创建“新版本”或产生重复附件。
9. 用户可直接预览和下载带“待确认”状态的纪要 PDF；正式客户方案与关键结论的发布遵守已有输出规范，确认动作写入审计，不能将 AI 初稿标记成甲方已批准。
10. Markdown/结构化 JSON 保留源稿，PDF 由受控模板导出；PDF Worker 状态和文件校验单独持久化，刷新后仍能下载同一版本，不重新跑整个 Agent。

业务数据库应是事实与文档版本的权威来源；图检查点记录处理进度。推荐首版只采用一种主编排方式：LangGraph 管文档节点、普通异步 worker 管转写/排版；若之后引入 Temporal，需明确它是总作业协调还是单个 durable backend，不应让多层引擎无边界重试同一外部动作。

任务入队建议采用业务数据库事务 outbox：先在同一事务写入业务变更和 outbox 事件，发布器可重试投递；worker 按 operation_id 去重，并在数据库中记录执行结果。LangGraph checkpointer 不替代该机制；调用 ASR/模型、写对象存储和导出文件的副作用都需要幂等键或结果复用，不能宣称跨数据库/队列/模型服务天然 exactly-once。

产物关联建议：一场会议关联多个录音 segment、转写 revision、事实快照、需求、产品证据、作业、Markdown/PDF/XLSX 文件；更新转写不静默覆盖旧纪要，发起重新生成并保留变更记录。产品知识检索时先做租户、项目、产品可见性、有效状态过滤，再做相似度/重排序，服务端校验引用仍有权限。

### Gaps

- 本子题没有验证浏览器分片容器、IndexedDB、ASR 供应商接续能力；这些属于另一个实时音频专项，本文不许诺“完全不丢数据”。
- 未实测中文 PDF 排版与 Excel 模板渲染；既有规范规定的低饱和配色、方案章节、默认单版、来源标记应保留，本次不产生源码。
- 会议截止时间、生成超时、并发、失败恢复和产品检索质量应以真实现场录音/产品资料做验收，不能以框架宣传替代。

## 三、检索过程、许可边界和证据可复查性

### Takeaway

本次优先核验原始官方仓库和许可证。Firecrawl 未认证后使用直接 HTTPS 取证；备用检索的失败、无关返回及 SPA 空壳均已保留，未把这些内容当作有效证据。

### Cited Findings

- 已执行 `npx.cmd --yes firecrawl-cli --status`，CLI v1.26.3 返回 Not authenticated。未进行登录、未读取/输出密钥。后续取证使用 Node 内置 fetch 获取官方 GitHub API、原始许可证、README 和官方文档；这是受当前工具状态影响的备用方法。
- 官方根许可证中，Dify 是带品牌与多租户约束的修改版 Apache；FastGPT 是 Apache 附加多租户 SaaS 与 LOGO 条款，均不应在商业架构报告里缩写为无条件 Apache-2.0。[Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)、[FastGPT LICENSE](https://github.com/labring/FastGPT/blob/main/LICENSE)
- Flowise enterprise 商业条款限制生产使用；Mastra 任意 ee/ 目录适用企业许可，当前 EE 许可版本标明 2026-09-22 生效，生产使用需要书面约定及 License Key。是否可以内部免费商用须按实际使用目录判断，不能从“source available”推断免费。[Flowise 商业条款](https://github.com/FlowiseAI/Flowise/blob/main/packages/server/src/enterprise/LICENSE.md)、[Mastra 根许可](https://github.com/mastra-ai/mastra/blob/main/LICENSE.md)、[Mastra EE 许可](https://github.com/mastra-ai/mastra/blob/main/ee/LICENSE)
- AutoGen API 自动识别 root LICENSE 为 CC-BY-4.0，但其代码许可另在根 LICENSE-CODE，实取正文为 MIT；这说明只读取 API license.spdx_id 不足以审计复杂仓库。[根许可](https://github.com/microsoft/autogen/blob/main/LICENSE)、[代码许可](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE)

### Inferences

证据目录均为工作区 `.firecrawl/20261015-agent-*`。记录了 14 仓库 × README/许可/API 的 42 个基础 URL，加上 16 个官方文档/许可证补充获取 URL、8 个发现检索 URL，共 66 个初始请求 URL，其中 62 个 HTTP 200、2 个 404、2 个 403。官方证据部分为 54 个去重的有效正文/API 来源：58 个官方初始 URL 中剔除 2 个 404、1 个 SPA 空壳、1 个重定向到已抓取的正文。8 个检索请求的结果单独说明，不计入这 54 个官方来源。不以请求量冒充资料质量。

每个仓库缓存结构：

- `20261015-agent-{name}-meta.json`：包含 GitHub 返回 `archived`、`pushed_at`、默认分支和描述；官方源为 `https://api.github.com/repos/{owner}/{repo}`。
- `20261015-agent-{name}-readme.json` 与 `-license.json`：GitHub contents 返回，含 html_url、git_url、sha 与 Base64 content；分别关联上述表格原始官方文件。
- `20261015-agent-{name}-readme.md` 与 `-license.md`：将 content 解码，便于复核；并非另外的独立资料源。
- `20261015-agent-source-manifest.json`：记录取证 UTC 时间、客户端研究日期、缓存文件字节数与 SHA-256；不存 API key。文件修改后应重算 hash，不能把陈旧 hash 当完整性结论。

补充检索轨迹：

| 检索/获取 | 本次观察 | 处理 |
|---|---|---|
| [GitHub 搜索 Agent workflow framework](https://api.github.com/search/repositories?q=agent%20workflow%20framework%20stars%3A%3E5000%20archived%3Afalse&sort=stars&per_page=12) | 403 rate limit | 留存 `discovery-frameworks.json`，不据此断言搜索无结果 |
| [GitHub 搜索 RAG knowledge assistant](https://api.github.com/search/repositories?q=RAG%20knowledge%20assistant%20stars%3A%3E5000%20archived%3Afalse&sort=stars&per_page=12) | 403 rate limit | 留存 `discovery-rag.json`，改以官方项目逐项核验 |
| [GitHub 搜索 meeting transcription minutes agent](https://api.github.com/search/repositories?q=meeting%20transcription%20minutes%20agent%20stars%3A%3E100%20archived%3Afalse&sort=stars&per_page=12) | 返回 bitwize-ai/Logue，描述为 macOS/MLX 本地工作区 | 仅发现，不纳入 Web 核心框架表，不推定其正文已验证 |
| [Bing 搜索 Dify FastGPT RAGFlow](https://www.bing.com/search?q=Dify%20FastGPT%20RAGFlow) | 返回 Dify 官网、GitHub、官方 docs，亦含第三方文章 | 用于发现/交叉定位，核心事实使用已读取官方 README/LICENSE |
| Bing 的宽查询、LangGraph/PydanticAI 组合查询 | 宽查询只返回 open 相关站点，后两者异常返回 Outlook/Restream 等无关条目 | 缓存 `search-*.html`，全部弃用作事实来源，不把 HTTP 200 当检索成功 |
| LangGraph durable-execution 文档 URL | 200 并重定向到 persistence | 用最终 persistence、checkpointers 与 fault-tolerance 正文，明确去重 |
| RAGFlow http_api_reference | 200，337 字节 SPA 空壳 | 不引用其中未读取的 API 细节，功能来源用 README |
| MAF workflows/checkpointing-and-resuming | 404 | 不作为正文证据；改取已验证的 workflows/overview 与 README |
| AutoGen python/LICENSE-CODE | 404 | 改取根 LICENSE-CODE 200，已上表引用 |

### Gaps

- 本次不是穷尽全网评测；搜索服务与 GitHub 限流使发现范围受限，已通过 14 个官方项目及深度工作流文档补足主要技术候选。
- 获取时的时间戳和仓库维护快照只代表本次实际返回；正式实施必须锁定 commit/tag 后重新检查许可和关键 API，不能默认 `main` 永久不变。
- `54 个有效正文/API URL` 是本稿的取证分类统计，原始缓存计数包含解码副本和失败文件，应以 manifest 与上表去重，不能把 108 个缓存文件说成 108 个独立来源。
