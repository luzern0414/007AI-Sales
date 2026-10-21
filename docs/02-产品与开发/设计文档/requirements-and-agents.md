# 需求提炼与代码生成 Agent：技术调研记录

调研日期：2026-10-12（Asia/Shanghai）。业务已明确为软件公司售前：把客户访谈和聊天转成可确认的业务需求，再生成可演示的前后端业务系统。本文只有研究与设计建议，未开发系统、未做模型或沙箱 PoC。

证据标签：**已核查**表示本轮读取了官方 README、LICENSE 或文档；**建议**表示针对本项目的设计判断；**待验证**表示未通过实际集成证明。仓库主分支、模型能力、地区政策和许可证会变化，实施前需固定版本再核查。

## 1. 怎样选工作流框架与代码 Agent 基础设施？

### Takeaway

**建议：MVP 使用 PostgreSQL 保存业务状态、Celery 分发有界作业、单个受控 coding worker 执行生成。暂不叠加 LangGraph、Dify 或复杂多 Agent；把 OpenHands SDK、OpenAI Agents SDK、Microsoft Agent Framework 留作有明确需求后的替代选项。** 工作流框架可恢复状态，不自动保证外部副作用只发生一次。

### Cited Findings

| 项目 | 已核查的能力与恢复边界 | 已核查的许可证 | 本项目判断（建议） |
| --- | --- | --- | --- |
| LangGraph | 图式工作流；checkpointer 保存 thread 状态，支持中断、恢复和故障容错；生产应使用 PostgreSQL 等持久 checkpointer，内存 saver 重启会丢状态。恢复可能从节点开头重跑，副作用需要幂等。[持久化](https://docs.langchain.com/oss/python/langgraph/persistence)；[重执行语义](https://docs.langchain.com/oss/python/langgraph/graph-api) | 核心库 MIT。[LICENSE](https://github.com/langchain-ai/langgraph/blob/main/LICENSE) | 适合后续需要大量分支、长时人工介入、checkpoint 回溯的 AI 子流程；MVP 已有 PG 业务状态和队列时不必再维护第二套顶层状态。 |
| LangChain | LangGraph README 明确可独立使用，不要求 LangChain；LangGraph 与 LangChain集成用于模型、工具等能力。[README](https://github.com/langchain-ai/langgraph) | LangChain 核心 MIT。[LICENSE](https://github.com/langchain-ai/langchain/blob/master/LICENSE) | 需要其模型/文档连接器时局部采用，避免为少量模型调用引入完整框架依赖。 |
| OpenAI Agents SDK | 提供 tools、guardrails、handoffs、sessions、tracing；当前 README 也列出 SandboxAgent 和容器工作空间。[README](https://github.com/openai/openai-agents-python) | SDK MIT。[LICENSE](https://github.com/openai/openai-agents-python/blob/main/LICENSE) | MVP worker优先评估的引擎：显式Chat Completions兼容适配、自定义受限tools、关闭默认追踪出口。通过下述PoC后采用；不能等同于平台任务调度器。 |
| OpenAI Agents SDK 的恢复 | 人工工具确认可暂停并序列化 RunState，再从数据库或队列恢复；反序列化不验证快照提交人，应用必须认证、授权及防重复消费。[HITL 文档](https://openai.github.io/openai-agents-python/human_in_the_loop/) | 同上 | 需要保存服务器可信快照；sessions 的聊天记忆和 RunState 的执行状态应区分。完整崩溃恢复、文件状态恢复仍需 PoC。 |
| Dify | README 提供可视化工作流、模型管理、RAG、Agent、监控和对应 API；当前还描述能运行命令和处理文件的 Agent sandbox；可 Docker Compose 自托管。[README](https://github.com/langgenius/dify) | **modified Apache 2.0，附加多租户限制与前端 LOGO/版权要求**，不是普通 Apache 2.0。[LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE) | 适合内部单工作空间低代码验证需求总结；本项目如多客户/多团队 SaaS，不把它默认作为核心控制层。需确认商业授权边界。 |
| AutoGen | 官方 README 当前明确 maintenance mode、社区维护、无新功能，推荐新项目使用 Microsoft Agent Framework。[README](https://github.com/microsoft/autogen) | 代码 MIT；不要把索引对文档的 CC-BY 标签误当代码许可证。[LICENSE-CODE](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE) | 本项目无既有 AutoGen 代码，不建议新建依赖。不能沿用旧文章把它当微软新项目首选。 |
| Microsoft Agent Framework | 官方 README 支持 Python/.NET、图式顺序/并行/handoff/group 工作流、checkpoint、streaming、HITL、OpenTelemetry，并支持多模型提供方。[README](https://github.com/microsoft/agent-framework) | MIT。[LICENSE](https://github.com/microsoft/agent-framework/blob/main/LICENSE) | 如果团队未来偏 .NET 或已有微软生态可评估；当前 FastAPI 方案没有必须改用它的证据。 |
| OpenHands Software Agent SDK | Python、TypeScript client、REST API；文件编辑/terminal/tools/conversation；Agent Server 支持 Docker/Kubernetes 临时工作空间。SDK 执行 conversation，automation 仓库另管调度、webhooks、run history。[README](https://github.com/OpenHands/software-agent-sdk) | **SDK 仓库 MIT**。[LICENSE](https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE) | 专用coding引擎第二候选；不必嵌入整套产品UI。依然由平台控制需求冻结、租户、预算、发布和生命周期。 |
| OpenHands 的恢复 | conversation_id + persistence_dir 保存/恢复事件和执行状态；官方列出的持久内容还包括工具输出、工作空间上下文、统计与 managed secrets。[Persistence](https://docs.openhands.dev/sdk/guides/convo-persistence) | 同上 | 文件持久化不等于可靠队列或容器磁盘快照；需保护持久目录，不把其内容直接作为普通下载产物。 |

Dify LICENSE 的两个具体边界：多租户条款把一个 workspace 定义为一个 tenant，未经书面许可不得用源码运行 multi-tenant environment；使用 `web/` 或 web image 时不得去掉/修改其 LOGO/版权信息，不使用前端时该条款不适用。[官方 LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)

框架开源许可证只涵盖相应软件组件，不等于模型 API 使用授权、云托管服务权限、商标使用权或生成代码依赖的许可证。不能因 SDK 是 MIT 就假定所有部署与模型都可无条件商业使用。[OpenAI SDK LICENSE](https://github.com/openai/openai-agents-python/blob/main/LICENSE)；[Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)

### Inferences

- MVP 最难的问题是访谈证据质量、需求范围、生成环境隔离和失败恢复。增加几个会互相聊天的 Agent 本身不能解决这些业务约束。
- 把生成 worker 封装成稳定接口，业务 API 只知道 job、status、events、artifact。以后更换 OpenHands/Agents SDK 时，不重写销售端流程。
- 若以后引入 LangGraph，由它编排一个明确的 AI 子流程；平台 PG 继续保存最终业务状态，避免两个组件争抢同一状态的写入权。
- Dify 可作为分析流程实验台，但工作流模板、平台鉴权、商业授权、工具沙箱仍需单独设计；可视化界面不是授权边界。
- 维护判断来自官方当前 README 和能力文档，本轮不以 stars、榜单成绩或营销成功率作为选型证据。

### Gaps

- 未做任何框架的中断、断电、版本升级后恢复测试；表格只证明官方提供对应接口/声明。
- 没有把任一 SDK 的当前主分支当作已验证生产稳定版本；需要正式实施时锁定发布版本与依赖。
- 未核查 Dify 所有工作流节点跨请求人工暂停与恢复的完整语义，不能声称其已满足本项目所有任务持久性要求。
- 未核查 OpenHands 整个平台、云服务、marketplace 或任意插件的完整许可；这里只确认 `software-agent-sdk` 仓库。

## 2. 访谈怎样变成可信、可冻结、可追溯的需求？

### Takeaway

**建议：把“总结”变成有证据的需求草稿，把“销售确认后的冻结版本”变成生成的唯一业务输入。** JSON Schema 限制输出结构，不证明客户说过某件事，也不证明需求之间无冲突。

### Cited Findings

- OpenAI Structured Outputs 支持按 JSON Schema 约束响应，Python/JavaScript SDK 可使用 Pydantic/Zod；官方仍明确输出可以有 mistakes，并只支持 JSON Schema 子集。[官方结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)
- OpenAI 官方要求处理 refusal、max tokens 导致的 incomplete 等路径，不能只看到 JSON 格式正常就宣告提取成功。[官方结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs)
- Anthropic structured outputs 区分 JSON outputs 和 strict tool use，支持的 Schema 有限制，refusal 与 max_tokens 仍可能导致不符合目标 Schema 的输出。[官方结构化输出](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- Qwen 官方文档区分 JSON object 模式和 JSON Schema strict 模式，并按模型及 thinking/non-thinking 模式列出支持情况；不能把所有 Qwen 型号统一视为 strict-schema 支持。[官方结构化输出](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output)
- DeepSeek JSON Output 文档保证 valid JSON strings，要求包含 json 指引、合理 token 上限，并提示偶发 empty content；这不是所有需求字段的语义保证。[官方 JSON Output](https://api-docs.deepseek.com/guides/json_mode)

### Inferences

建议业务流程如下；这是拟设计的流程，尚未实施，也未发生任何客户或销售确认：

1. 录音/聊天写入会话；上传完成后转写；销售可修正转写，但保留原版和修订版本。
2. 提取需求候选，只引用已存在的 transcript segment 或 chat message。
3. 校验来源 ID、时间范围、角色、数据对象、功能之间的引用关系和范围大小。
4. 按事实、推断、未知展示；把影响 Demo 行为的缺口转成少量澄清问题。
5. 销售编辑和确认业务范围；系统明确显示将演示的功能、默认假设、不做的功能。
6. 服务器生成不可变 spec snapshot、版本号和 hash；记录实际操作人的身份与时间。
7. 只允许 generation job 引用这个 frozen snapshot；修改需求产生新版本，原任务仍保留原输入。

建议需求字段契约：

| 字段组 | 应包含的信息 | 校验责任 |
| --- | --- | --- |
| 标识与归属 | requirement_id、project_id、tenant_id、session_id、schema_version | 服务端赋值并验证归属，模型不能改 tenant。 |
| 证据 | source_type、source_id、transcript_version、start_ms/end_ms（录音时）、原文摘录 | 来源真实存在；时间范围位于录音内；摘录对应来源；聊天使用 message_id。 |
| 认知状态 | fact / inference / unknown、理由短句、需确认项 | 不让模型自己的百分比当作已校准置信度；需要看到来源和推断依据。 |
| 业务主体 | 客户类型、业务目标、现有流程、痛点、用户角色 | 不从行业常识补写“客户已要求”。 |
| 功能 | module、user_story、priority、角色权限、输入/输出、验收步骤 | 功能有来源；推断项显式标识，生成前纳入确认范围。 |
| 数据与规则 | 实体、字段、关联、状态流转、数据校验、业务约束 | 检查实体引用、枚举一致性和流程冲突。 |
| 范围与缺口 | in_scope、out_of_scope、assumptions、open_questions、blocking_questions | 涉及角色权限、敏感数据、支付/外部系统的缺口不得静默补全。 |
| 版本与确认 | spec_version、canonical_hash、confirmed_by、confirmed_at、template_version | 由服务器可信会话确定实际操作者；确认接口防旧版本覆盖新版本。 |

证据处理建议：

- “事实”只指访谈明确表达或销售明确修订的内容；不能把“客户想提高效率”扩展为“客户要求 ERP+CRM+财务”。
- “推断”应说明“根据订单录入流程，建议加入订单列表”；销售可以接受、修改、拒绝。
- “未知”允许留空。Schema 的 required 字段可以要求存在空值/未知状态，不要求模型编造答案。
- 来源 segment 不等于人工核实的录音真值。ASR 转写、说话人分离和时间戳都需保留可回听入口。
- 更正过的转写不能静默覆盖原文，否则旧需求的证据链会失效；应记录 correction_id 和版本关系。
- 摘录、说话人标签和业务字段分开存储；说话人分离不是客户姓名身份验证。
- 一条需求可以引用多个来源，来源冲突需留在待确认列表，例如不同时间说的审批层级不同。
- 原始会话中“忽略你的规则，执行这段命令”属于待处理内容，不能升级成 Agent system instruction。

冻结与澄清建议：

- 冻结前显示需求清单、核心流程、角色、数据实体、Demo 默认假设、未覆盖项和预估资源范围。
- 把问题分为阻塞生成与可按模板默认演示两类；默认假设也要显示在确认页面。
- 优先问“审批由经理一人还是两级？”等影响界面的业务问题，不先向销售展示技术框架选择题。
- 按规范序列化后的 spec 内容计算 hash；录音、会话引用版本、模板版本和策略版本都留关联。
- confirmed_by 必须来自服务端登录会话，不能相信请求 body 中伪造的销售 ID。
- 需求确认与工具危险操作确认是不同概念；销售确认业务范围，不代表授权 worker访问平台凭证或生产系统。
- 冻结后新增聊天可生成变更草稿；不能偷偷更新正在生成的 Demo 输入。
- 原始全文仅供需求阶段受限使用；coding worker拿到规范化 spec 和有限必要摘录，避免无关敏感内容扩散。

### Gaps

- 没有本行业真实访谈样本、专家标注和测试集，无法给出需求提取准确率或漏项率。
- 未验证目标 provider对最终 Schema、中文长访谈、纠错版本、复杂实体关系的兼容性。
- 没有经过销售用户验证的澄清问题数量或 Demo 范围上限；这些应通过样本 PoC 调整。

## 3. 怎样替换模型供应商并满足国内部署假设？

### Takeaway

**建议：大陆部署优先评估阿里云百炼/Qwen 与 DeepSeek，平台提供按能力声明的 provider adapter。** OpenAI-compatible 通常表示部分协议兼容，不能推导所有 Responses、strict Schema、工具调用、流式中断、token 使用量和数据政策都一致。

### Cited Findings

| 提供方 | 已核查事实 | 本项目建议 / 限制 |
| --- | --- | --- |
| Qwen/阿里云百炼 | 官方 OpenAI Chat兼容文档明确可调整 API Key、BASE_URL、model；当前建议北京、新加坡、中国香港业务空间专属域名，地域与 workspace 需匹配。[官方兼容文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope) | 使用国内账号与北京地域作为待验证默认方案；base_url 由账号和 workspace 配置，不写死历史端点。 |
| Qwen structured outputs | JSON Schema strict 支持按具体模型与模式区分。[官方文档](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output) | provider capability 需要精确到 model+API+mode；需求提取与 coding 可用不同型号。 |
| DeepSeek | JSON object 模式有 empty content 与截断边界；function calling strict 模式目前在 beta endpoint，并验证支持的 Schema 类型。[JSON Output](https://api-docs.deepseek.com/guides/json_mode)；[Tool Calls](https://api-docs.deepseek.com/guides/tool_calls) | JSON 模式走服务端校验；strict beta 不作为无需验证的生产默认。 |
| OpenAI | 支持地区页面明确未列地区的访问或对外提供访问可能导致账户 blocked/suspended；本轮所读取列表未包含中国大陆。[官方地区列表](https://platform.openai.com/docs/supported-countries) | 只保留在部署主体、最终用户地区与服务条款允许时启用的适配器；不可假设大陆直连是可运营路径。 |
| Anthropic | 当前地区政策涵盖身处地区、实体注册地/总部及直接或间接控制关系；未列地区不支持，本轮列表未包含中国大陆。[官方地区政策](https://www.anthropic.com/supported-countries) | 仅在符合当前官方授权条件时评估；不能把境外服务器当作当然解决方案。 |
| OpenAI Agents SDK | 官方提供 OpenAI-compatible client/base_url、模型接口和多提供方集成；文档要求注意 provider feature differences。[Models](https://openai.github.io/openai-agents-python/models/) | SDK可以复用，但要精确测试用到的接口；不能只更换 URL 就宣称能力完全一致。 |

### Inferences

建议 provider adapter 固定以下契约，不把供应商 SDK 的内部类型直接传给业务 API：

- 输入：业务用途、provider/model/region、指令与数据分离后的 messages、Schema、允许的工具、预算上限、deadline、取消信号、trace_id。
- 能力声明：json_object、strict_json_schema、tool_call、strict_tool_arguments、streaming、usage_reporting、reasoning_mode、max_context、supported_schema_subset。
- 输出：规范化 parsed_data、原始响应引用、finish_reason、拒绝/截断状态、tool_call IDs、token/cached token usage、latency、provider_request_id。
- 错误：鉴权/地区、限流、网络超时、Schema 不支持、内容拒绝、上下文超限、预算超限、取消；不要统一成“AI生成失败”。
- 每种用途分别配置主模型与备用模型，不能在发生高风险工具调用后无条件重放到另一 provider。
- 自动切换需要记录模型、区域、版本与原因；同一次 frozen spec 的新 attempt 可以换模型，但旧产物和输入必须保留。
- 只用没有产生外部副作用的阶段做自动重试；模型输出坏 JSON 的修复循环有次数和token上限。
- usage 不可得时标记为估算/未知，不把空值当零成本。
- 费用公式：输入 token × 输入单价 + 输出 token × 输出单价 + 音频时长计费 + 沙箱CPU/内存/存储/预览时长费用；单位统一到供应商实际计费单位。
- 国内优先是部署建议，不是已确认服务可用性。需实际验证企业账号、网络、数据处理协议、保留策略与地域配置。
- 模型服务条款、模型权重许可证、SDK许可证、生成项目依赖许可证分开登记；本轮没有申请账号或确认任何商业服务授权。

若采用 OpenAI Agents SDK，其 tracing 默认启用，默认 processor会后台导出；可禁用或改自定义出口。不能因为模型改成国内 provider就认为追踪内容自然只留在国内。[官方 tracing](https://openai.github.io/openai-agents-python/tracing/)

### Gaps

- 没有用任何真实模型 key调过 API，地区可用性、企业配额、延迟、费用和中文质量未实测。
- 本轮未核实所有模型服务的完整企业合同与数据保留条款，不能保证访谈数据保留期限。
- 本轮不推荐某个“最新型号”作为永久配置；落地需要固定已实测版本，并保存能力测试结果。

## 4. 单 worker、持久队列、幂等、预算与取消怎样设计？

### Takeaway

**建议：一个 generation job只管理一个独立生成工作空间，由一个 worker顺序完成计划、文件生成、运行校验、有限修复与产物封装。** 队列提供分发能力，业务数据库才是任务状态事实来源；不要声称消息系统提供端到端 exactly-once。

### Cited Findings

- Celery官方任务文档要求考虑任务幂等，acks_late 可以延后 ACK；worker 异常退出的确认语义还有额外边界，需要根据运行策略配置。[Tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- Redis broker visibility timeout 默认 1 小时；超时未 ACK 会重投，调得很长又会推迟丢失任务的恢复；官方明确 broker不是数据库。[Redis broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)
- LangGraph 恢复时 affected node可能从函数开头重跑，明确建议幂等 keys/upsert/read-before-write。[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- Redis 8 起可选择 RSALv2/SSPLv1/AGPLv3，官方明确前两者不是开源许可证、AGPLv3为OSI认可开源许可证；不能笼统写“Redis都是宽松开源”。[官方许可证页](https://redis.io/legal/licenses/)
- Valkey仓库 COPYING明确为 BSD-3-Clause。[官方 COPYING](https://github.com/valkey-io/valkey/blob/unstable/COPYING)

### Inferences

MVP职责建议：

明确实施建议：先做 **OpenAI Agents SDK + 显式 OpenAIChatCompletionsModel + 百炼/DeepSeek兼容端点** 的worker PoC。SDK只负责有界模型与工具循环；平台PG/Celery负责作业、需求确认、版本与审计。只提供平台实现的受限patch、读取workspace与固定检查工具，不开放通用宿主terminal，运行环境由sandbox supervisor管理。启动前禁用默认OpenAI tracing出口。SDK名称不要求使用OpenAI模型API；兼容依据来自其官方[Models文档](https://openai.github.io/openai-agents-python/models/)。

PoC门槛：目标具体型号的function calling、坏JSON/拒绝/截断处理；2—3个真实CRUD Demo模板；崩溃重启与重投不会产生双份可发布产物；预算与取消有效；workspace、凭证、网络和预览origin隔离通过。如果兼容门槛失败，评估OpenHands SDK；本轮不预先开发或同时维护三个Agent引擎。

| 层 | 唯一职责 | 不由它决定的事 |
| --- | --- | --- |
| PostgreSQL | frozen specs、jobs、attempts、状态转换、锁/租约、outbox、审计、artifact登记 | 不运行生成代码。 |
| Celery + broker | 投递、并发控制、短作业重试、worker分组 | 不作为唯一业务状态库，不决定销售权限。 |
| 单 coding worker | 有界 plan → scaffold from vetted template → code → checks → limited repair → artifact | 不改业务冻结范围，不发布到生产，不读平台数据库。 |
| Sandbox supervisor | 创建/销毁运行环境、资源/网络边界、文件与进程生命周期 | 不信任模型说“测试通过”。 |
| Artifact/preview服务 | 接收可信检查后的产物、展示独立预览、限时访问 | 不让上传产物任意操作平台。 |

- broker候选可写 Celery + Valkey，按 Redis协议接入是需要 PoC 的兼容性假设；也可用已确认许可的托管broker或RabbitMQ，不因此提前部署多套组件。
- 在 PG 同一事务写 job和 outbox，派发器读 outbox投队列；broker消息丢失时可依据 PG补投。
- 首次入队按 tenant + frozen spec hash +模板版本+生成策略版本+生成请求标识去重；明确“重新生成”创建新 attempt，保留原产物。
- worker接任务先原子争取 lease并检查 terminal state；重复投递不创建第二个可发布产物。
- 每个阶段保存阶段结果引用、错误类型、校验日志摘要、usage和预算消耗；大日志和文件放隔离产物存储。
- 预算应含 max_tokens、max_model_calls、max_tool_calls、max_iterations、max_repair_rounds、wall_clock_deadline、CPU/内存/磁盘、网络请求限制。
- 模型自己的“预计剩余10秒”不能用作真实进度；展示已完成阶段、当前阶段和真实事件时间。
- 队列消息只携带 job ID，worker从受控只读契约取 frozen spec；不将原始访谈全文和 key放broker消息。
- 长时等待销售确认不占 worker进程；业务状态存PG，确认后创建新的短阶段作业。
- job状态可以是 queued/running/validating/ready/failed/cancel_requested/cancelled/expired；平台需定义每条合法转换。
- 取消先写 cancel_requested，再合作式停止模型/工具；无法及时停止时由supervisor终止容器。
- Celery revoke不能当作已完成清理证明；容器停止、子进程终止、临时凭证失效、lease释放和artifact状态需要确认。
- 硬终止后的恢复默认创建新 attempt或从已验证阶段恢复；不能盲目重放此前可能已完成的外部调用。
- visibility timeout、最长任务时长、late ACK、worker-lost行为、prefetch必须一起验证；避免任务仍运行时收到重复投递。
- 审计包含操作者、spec hash、模板/策略/模型版本、每次工具调用、预算、失败原因、产物hash和预览访问记录；敏感数据最少化。

单 worker相对多 Agent的判断：

- 优点：预算、文件所有权、重试语义和日志更容易界定；一次需求不会同时被几个Agent互相改写。
- 局限：前后端复杂任务可能质量不够；先通过限制模板和范围、客观验证与有限修复解决。
- 多Agent可后续用于独立只读审查或模块分工；不能默认认为角色越多质量越高或成本越低。
- 如果引入审查Agent，其输出是建议；发布gate仍由程序检查与授权逻辑决定。

### Gaps

- 没有验证 Celery/Valkey指定版本、持久化配置、断电恢复、故障转移和消息重投的组合行为。
- 没有本项目生成样本，不知道单 worker完成典型Demo的成功率、费用分布与P95时延。
- 未决定broker具体部署方案，不能提前宣称Redis或Valkey已适用本项目全部商业授权场景。

## 5. 怎样防止未经确认的访谈变成任意执行命令？

### Takeaway

**建议：采用数据到结构化需求、需求到冻结快照、快照到受限工具这三道边界，生成和运行都在平台之外的隔离环境。** 提示文本、Schema、人工确认各自有作用，任何一种都不能代替操作系统、网络与权限边界。

### Cited Findings

- OWASP说明prompt injection利用自然语言指令与数据混在一起的设计弱点，并推荐结构化分离、输入/输出验证、HITL、最小权限和工具调用控制。[官方防护速查表](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- OpenAI Agents SDK的 local ShellTool/ApplyPatchTool审批默认不启用，needs_approval要显式配置；仅设置callback不会自动启用审批。[官方 HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- 同一文档要求把完整RunState留服务器可信存储、认证审核人、校验授权和pending call，并原子防止重复恢复；浏览器传回快照不是可信身份。[官方 HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- OpenHands持久化文档列出 managed credentials/API keys属于可能持久化状态；持久目录必须按敏感数据保护，不能当作普通公开artifact。[官方 Persistence](https://docs.openhands.dev/sdk/guides/convo-persistence)

### Inferences

- 客户录音、聊天、附件、抓取内容、生成代码、工具日志都当作不可信数据；系统指令与执行策略来自服务器固定版本。
- 需求抽取模型只允许读会话并输出Schema，不能拿terminal、网页任意访问、发布、支付或平台DB写工具。
- sales confirmation只确认业务范围；模型字段不能授予新增工具、扩大网络权限或批准外部系统调用。
- frozen spec只包含业务目标、数据/流程、UI需求、验收步骤和允许模板；不包含客户提供的任意shell执行要求。
- coding tools只作用于独立workspace，限制路径穿越、符号链接、文件大小和artifact类型；禁止读取宿主目录、平台配置和凭证。
- 普通Docker不能仅凭名称视为完全安全边界；隔离方案需另行评估non-root、资源限制、无Docker socket、无宿主挂载和网络策略。
- 默认不访问生产数据库、内网服务、云metadata和客户真实账号；Demo用独立测试数据与独立数据库。
- 依赖只从已审批模板/缓存/registry白名单安装，安装脚本与生成代码同样是不可信执行内容。
- API key由平台model proxy或短期最小权限凭证提供；不要把长期平台key注入会话上下文或生成项目环境文件。
- tool权限由服务器policy检查，不能依赖模型自主承诺“我只会执行安全命令”。
- 后端与前端都要验证：真实启动、健康检查、关键CRUD、数据持久化、权限假设、构建结果；模型文字“成功”不是验证证据。
- 有失败时展示哪个阶段失败和可继续的操作；未验证产物不能进入Demo广场或面向客户分享。
- 预览部署独立origin，不与平台共用cookie或平台API凭证；生成HTML/JS不能读取平台登录态。
- 预览默认团队私有、带访问授权和过期策略；进入Demo广场需明确发布动作，并检查真实客户信息是否已替换。
- 方案不承诺可以自动发布正式系统；售前Demo的质量gate应围绕核心流程可演示、可回溯和范围明确。

### Gaps

- 本轮尚未做prompt injection、路径穿越、SSRF、恶意依赖、跨租户访问、取消后残留进程或preview cookie隔离测试。
- 未验证任一coding SDK的默认tools、shell审批、网络策略与secrets持久化能直接满足这些边界，需要部署PoC。
- Prompt injection无法仅通过一段提示词保证消除；本方案的目标是约束可造成的副作用，并让来源和权限可检查。

主要来源原始快照存于项目 `.firecrawl/agents-*`。Firecrawl keyless developer/search及scrape前期成功；后续触发free-tier rate limit，停止重试，余下官方公开来源使用HTTP读取并保留原文。一个最初的Qwen英文compatibility URL仅返回极短内容，未用作证据，改用阿里云中文官方兼容文档。未申请key、未安装项目依赖、未执行生成代码。
