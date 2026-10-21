# 用可靠录音支撑有据销售方案

调研日期：2026-10-15，Asia/Shanghai。范围：现场客户会议优先，Web 架构、开源选型、四页界面与会议文档生产。状态：公开资料调研与设计，未编写应用代码、测试麦克风、运行模型或输出 PDF 成品。

推荐建设 **自有 React/TypeScript Web 工作区 + FastAPI 业务服务 + PostgreSQL/pgvector + 私有对象存储 + LangGraph 持久工作流**，首页以现场麦克风实时录音、实时文字和双端保存状态为中心。现成 Agent 平台能提供编排/知识检索，却不能自动承担浏览器录音恢复、客户事实核准、产品承诺和中文文档排版。音频通过 AudioWorklet/Worker 独立落盘，实时 ASR 和归档补传分开，避免识别故障拖垮保存。会议结束在完整归档上校正转写，以同一事实快照生成纪要、售前方案、需求清单与甲方资料权限规则确认清单，纪要 **MD/PDF 为必需输出**。产品库保存有版本、有证据且核实过的能力，方案不得将未核实功能写成“已有”。导航固定首页、历史纪要、产品库、工作台，采用藏青/石板灰低饱和设计；当前会议未要求分期则全产物单版。以下推荐是针对需求的工程判断，不是开源项目性能排名；浏览器中断风险只能测量和减轻，不能承诺绝对零丢失。

## 一、自建业务层能同时掌握音频、产品事实和文档版本

选择路线应先看谁负责核心事实与故障恢复。LangGraph 官方将线程 checkpoint、跨线程 Store 与业务数据区分，持久 PostgreSQL checkpointer 可保存工作流进度；不同 durability 模式对运行中崩溃的窗口不同，节点恢复也可能重新执行外部调用。它适合明确的文档处理步骤，但不替代录音归档和幂等业务协议。([LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)，[Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers))

| 架构路线 | 可复用能力与优势 | 本项目代价/边界 | 适用条件与结论 |
|---|---|---|---|
| 自建四页 + LangGraph + 自有数据库 | 会议、产品、事实和文档版本在一条业务链，工作流可暂停/恢复、按证据重生 | 需要自己实现录音协议、权限、数据/API和导出 | **唯一推荐主线**，适合本次持续录音与严格方案要求 |
| 自建四页 + Dify/FastGPT/RAGFlow API | 较快试验知识库、低代码流程，技术人员可视化配置 | 业务状态与平台状态衔接、部署资源及许可条件；仍须自建录音/版本/排版 | 适合已有平台且已处理许可的内部试点；不能认为换前端消除多租户约束 |
| 自建四页 + PostgreSQL步骤表 + Agents SDK普通worker | 线性短流程依赖较少，工具与结构输出清楚 | 团队自行实现崩溃恢复、步骤重放、人工等待及幂等，复杂分支成本上升 | 只在流程保持短线性且故障恢复实测通过时作为轻量备选 |

Meetily 是 Tauri 桌面应用，Hyprnote 是设备音频和本地文件路径，Scriberr 可提供自托管 Web 转写交互参考；这些形态不能互相等价为现成销售 SaaS。Vexa 针对远程会议机器人，对本次现场单麦不需要先引入。([Meetily README](https://github.com/Zackriya-Solutions/meetily/blob/main/README.md)，[Hyprnote README](https://github.com/fastrepl/hyprnote/blob/main/README.md)，[Scriberr README](https://github.com/rishikanthc/Scriberr/blob/main/README.md)，[Vexa README](https://github.com/Vexa-ai/vexa/blob/main/README.md))

推荐前端 React + TypeScript + Vite + shadcn/ui 定制组件，后端 FastAPI，数据 PostgreSQL + pgvector，产品 PDF 解析先验证 Docling，导出 Playwright/Chromium。实时中文 ASR 先同语料评测一家国内云并做 FunASR 2pass 私有化对照，通过 adapter 替换。LangGraph 是唯一文档编排引擎，普通 Pydantic 做字段验证；不用同时叠加 Agents SDK、Pydantic AI、CrewAI、Mastra、Temporal。异步解析/ASR/PDF worker 是作业执行边界，不是第二套 Agent 流程。任务入队用业务事务 outbox，operation_id 去重与结果复用；不宣称跨模型/DB/对象存储天然 exactly-once。

## 二、42 项候选覆盖编排、音频、知识和排版，许可决定复用方式

本次覆盖 **42 个不同候选项：14 个 Agent/知识平台或框架，13 个音频/接口/模型候选，15 个会议/UI/文档组件**。其中3项为商业云ASR，其他为代码项目、协议客户端或模型，不把商业接口统称开源。这是候选项数，不是42个项目均已集成或测评。表中官方能力和许可来自已读取的README/许可证/文档，适用判断为本项目推论。所有在线分支快照均以2026-10-15取证为准，实施需锁定commit/release、模型revision和依赖后复查。

### 2.1 Agent 平台应服务于销售工作流

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

Flowise 的 README/API 在本次快照显示归档，AutoGen README 明确维护模式；这里不推断归档原因、团队质量或其他项目“生产最稳”。GitHub pushed_at 不代表正式发布、安全响应或中文质量。Dify/FastGPT 带多租户和品牌附加条件，Mastra/Flowise/Hyprnote 有商业目录边界，AutoGen 根文档与代码许可分离；根仓“开源”不能覆盖所有企业模块、权重、插件和云合同。([Flowise API](https://api.github.com/repos/FlowiseAI/Flowise)，[AutoGen README](https://github.com/microsoft/autogen/blob/main/README.md)，[Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)，[FastGPT LICENSE](https://github.com/labring/FastGPT/blob/main/LICENSE))

### 2.2 实时中文识别通过适配层替换

| 候选 | 官方能力证据与适配位置 | 许可证/性质 | 建议 |
| --- | --- | --- | --- |
| FunASR | README提供流式模型与VAD/标点/说话人管线；runtime支持online/offline/2pass，先实时输出再句尾高精度修正。[README](https://github.com/modelscope/FunASR)、[2pass guide](https://github.com/modelscope/FunASR/blob/main/runtime/docs/SDK_advanced_guide_online_zh.md) | 代码 [MIT](https://github.com/modelscope/FunASR/blob/main/LICENSE)；模型单独核对 | 中文私有化主候选 |
| sherpa-onnx | 支持流式/非流式ASR、离线运行及WebAssembly示例，包括中英文流式模型。[README](https://github.com/k2-fsa/sherpa-onnx) | [Apache-2.0](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE)；模型另核 | CPU/边缘与端侧离线候选；大模型加载、电量仍需实测 |
| faster-whisper | CTranslate2后端、batch转写、VAD；README将Whisper-Streaming/WhisperLive列为实时集成。[README](https://github.com/SYSTRAN/faster-whisper) | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) | 会后离线校正主候选之一；不把其普通transcribe直接称为完整可靠live服务 |
| WhisperLive | nearly-live Whisper服务；文档提供faster_whisper/tensorrt/openvino后端、麦克风/文件输入和服务端选项。[README](https://github.com/collabora/WhisperLive) | [MIT](https://github.com/collabora/WhisperLive/blob/main/LICENSE) | 对比低延迟流式封装；不替代本地归档/幂等协议 |
| whisper.cpp | C/C++实现，支持移动端和WASM；stream示例按半秒采样连续转写。[README](https://github.com/ggml-org/whisper.cpp) | [MIT](https://github.com/ggml-org/whisper.cpp/blob/master/LICENSE) | CPU/离线/原生客户端备选；浏览器性能实测 |
| Silero VAD | 官方提供轻量语音活动检测及ONNX部署说明。[README](https://github.com/snakers4/silero-vad) | [MIT](https://github.com/snakers4/silero-vad/blob/master/LICENSE) | 用于识别分段/静音检测；归档不因VAD判静音就删原音 |
| tus-js-client | 浏览器/JS断点续传客户端。[README](https://github.com/tus/tus-js-client) | [MIT](https://github.com/tus/tus-js-client/blob/main/LICENSE) | 大文件导入和补传；服务器也需tus协议实现 |
| LiveKit server | 分布式WebRTC SFU，音视频与数据传输。[README](https://github.com/livekit/livekit) | [Apache-2.0](https://github.com/livekit/livekit/blob/master/LICENSE) | 未来多人在线会议/AI参会时评估；现场单麦录音可先不引入SFU |
| Pipecat | 实时对话管线，支持WebRTC/WebSocket、STT/LLM/TTS服务集成。[README](https://github.com/pipecat-ai/pipecat) | [BSD-2-Clause](https://github.com/pipecat-ai/pipecat/blob/main/LICENSE) | 未来语音销售陪练/对话助手评估；不能取代文档工作流 |
| 阿里云实时ASR | WebSocket文本指令+二进制音频；PCM16单声道8k/16k；中间/句末/任务结束事件。[官方协议](https://help.aliyun.com/zh/isi/developer-reference/websocket) | 商业接口，非开源 | 现场中文云端候选，热词/账号配额/区域/合同实测 |
| 腾讯云实时ASR | 流式结果稳态标识、热词、1:1发送约束；新连接需新voice_id。[官方协议](https://cloud.tencent.com/document/product/1093/48982) | 商业接口，非开源 | 与阿里/火山选一至两家PoC，禁止忽略发包节奏限制 |
| 火山引擎流式ASR | 双向流式、优化版本、100–200ms分包、session协议。[官方协议](https://www.volcengine.com/docs/6561/1354869) | 商业接口，非开源；当前读取URL归于历史文档 | 候选；落地先复核当前控制台推荐新接口/资源ID |
| Paraformer-zh-streaming 模型 | FunASR流式中文/英文候选，模型卡列license:apache-2.0。[模型卡](https://huggingface.co/funasr/paraformer-zh-streaming/blob/main/README.md) | 模型卡 [Apache-2.0](https://huggingface.co/funasr/paraformer-zh-streaming/blob/main/README.md)，不能据此推断FunASR全部模型同许可 | 以具体checkpoint+revision验证商用条款和真实CER |

FunASR 的代码MIT、具体Paraformer流式模型卡的Apache-2.0不能推导全部FunASR权重都同许可。faster-whisper普通transcribe是转写能力，完整实时产品仍需会话、发送速率、回压和重连服务。LiveKit/Pipecat 适合多人在线音频/语音对话，当前现场采集不必承担SFU和TTS复杂度。([FunASR LICENSE](https://github.com/modelscope/FunASR/blob/main/LICENSE)，[模型卡](https://huggingface.co/funasr/paraformer-zh-streaming/blob/main/README.md)，[faster-whisper](https://github.com/SYSTRAN/faster-whisper)，[LiveKit](https://github.com/livekit/livekit)，[Pipecat](https://github.com/pipecat-ai/pipecat))

### 2.3 会议交互与排版组件比整站搬用更合适

| 项目 | 官方已核实能力 / 形态 | 许可证及边界 | 建议使用位置 |
|---|---|---|---|
| Meetily | 本地会议录音、实时转写、摘要；README 明示单体 Tauri 应用，Rust 后端 + Next.js 前端。[README](https://github.com/Zackriya-Solutions/meetily/blob/main/README.md) | 社区代码 MIT；README 说明 PRO 是不同代码库，不能据社区 MIT 推断 PRO 功能可以自由复用。[LICENSE](https://github.com/Zackriya-Solutions/meetily/blob/main/LICENSE.md) | 参考录音状态、转写/摘要分离设计；不能当现成 Web SaaS 底座。 |
| Hyprnote（本次 README 称 anarlog，团队正在构建 char） | 无机器人、设备音频、本地 SQLite 与文件、Markdown 导出；可分别选择转写与文本智能提供方。[README](https://github.com/fastrepl/hyprnote/blob/main/README.md) | 社区 MIT；`enterprise/` 不受 MIT 授权，生产使用等需书面商业协议。[MIT](https://github.com/fastrepl/hyprnote/blob/main/LICENSE)、[Enterprise](https://github.com/fastrepl/hyprnote/blob/main/LICENSE.enterprise) | 参考实时记录、原始音频留存和模型供应商分离；不要复制商业企业组件。 |
| Vexa | 机器人进入 Google Meet、Teams、Zoom，流式输出带说话人的转写；支持自托管。README 对 Jitsi 明确写 live validation pending。[README](https://github.com/Vexa-ai/vexa/blob/main/README.md) | Apache-2.0 代码；托管服务与自托管能力范围不同；模型、云服务仍各有独立条款。[LICENSE](https://github.com/Vexa-ai/vexa/blob/main/LICENSE) | 可选远程会议连接器；现场麦克风录音无需机器人。 |
| Scriberr | 自托管音视频转写、内置录音、转写编辑/笔记、对录音问答、PWA，截图描述有跟随播放及文字定位跳转。[README](https://github.com/rishikanthc/Scriberr/blob/main/README.md) | 应用代码 MIT；其模型和提供方不因包装层 MIT 自动获得相同授权。[LICENSE](https://github.com/rishikanthc/Scriberr/blob/main/LICENSE) | 最接近可参考的 Web 会议记录界面；需要另建销售产品库、证据底稿、方案规则、录音恢复保障。 |
| Docling | PDF 版面、阅读顺序、表格、OCR、多格式输入，统一 DoclingDocument，可输出 Markdown/JSON，可本地执行。[README](https://github.com/docling-project/docling/blob/main/README.md) | 代码 MIT；README 明确 individual model usage 需核对原模型许可。[LICENSE](https://github.com/docling-project/docling/blob/main/LICENSE) | 复杂 PDF/扫描产品资料的首选验证对象；保留 JSON 及页码位置，不只保存扁平 Markdown。 |
| MarkItDown | 轻量 Python 多格式转 Markdown，保留标题、表格、列表、链接；README 强调面向文本分析而非高保真文档转换。[README](https://github.com/microsoft/markitdown/blob/main/README.md) | MIT；插件、Azure 或额外模型调用独立核实。[LICENSE](https://github.com/microsoft/markitdown/blob/main/LICENSE) | 普通办公资料快速解析路径；不能以其 Markdown 输出充当原文件的精确保真副本。 |
| Unstructured | 文件分区、预处理及各种格式 ingestion；本地 PDF 路径有 tesseract/poppler 等系统依赖。[README](https://github.com/Unstructured-IO/unstructured/blob/main/README.md) | 核心库 Apache-2.0；托管 API、inference 模型和系统依赖不能仅凭该许可概括。[LICENSE](https://github.com/Unstructured-IO/unstructured/blob/main/LICENSE.md) | 备选解析框架；若已用 Docling，不为同一流程同时引入三套重型默认依赖。 |
| pgvector | PostgreSQL 向量近邻检索；README 提供与 PostgreSQL 全文检索结合，RRF 或 cross-encoder 融合的说明。[README](https://github.com/pgvector/pgvector/blob/master/README.md#hybrid-search) | PostgreSQL 风格宽松许可，非 MIT。[LICENSE](https://github.com/pgvector/pgvector/blob/master/LICENSE) | 初始产品库使用 PostgreSQL + pgvector + 全文检索，减少独立数据库；中文分词单独验证。 |
| shadcn/ui | 可定制、可扩展、用于建立自己的组件库，Open Code。[README](https://github.com/shadcn-ui/ui/blob/main/README.md) | MIT；图标、所选底层组件、字体另查。[LICENSE](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md) | 四页低饱和定制工作区的推荐 UI 基础。 |
| Radix Primitives | 低层 UI 组件，关注可访问性、可定制性，可用作设计系统底层。[README](https://github.com/radix-ui/primitives/blob/main/README.md) | MIT。[LICENSE](https://github.com/radix-ui/primitives/blob/main/LICENSE) | 对话框、下拉、标签页、键盘交互；选择实际锁定版本所用 primitive，不宣称全部 shadcn 版本固定依赖 Radix。 |
| Ant Design | React 企业 UI 库。[README](https://github.com/ant-design/ant-design/blob/master/README.md) | MIT。[LICENSE](https://github.com/ant-design/ant-design/blob/master/LICENSE) | 表格、复杂筛选与权限后台优先时的备选；不建议与整套 shadcn 同时大面积混用。 |
| Playwright | 浏览器自动化；`page.pdf` 提供 A4、页边距、背景、CSS 页面尺寸、页眉/页脚、PDF 缓冲输出等。[API](https://playwright.dev/docs/api/class-page#page-pdf) | Apache-2.0；Chromium、字体及镜像中其他依赖有各自许可。[LICENSE](https://github.com/microsoft/playwright/blob/main/LICENSE) | 纪要 HTML → Chromium PDF 导出服务；也是后续页面和导出可视验证工具。 |
| python-docx | Python 创建/修改 Word `.docx`，项目 README 指向官方文档。[README](https://github.com/python-openxml/python-docx/blob/master/README.md) | MIT；不包含 Microsoft Word/LibreOffice 的运行或字体授权。[LICENSE](https://github.com/python-openxml/python-docx/blob/master/LICENSE) | 售前方案按指定 Word 模板生成；它本身不是 PDF 排版引擎，不能直接宣称可转 PDF。 |
| WeasyPrint | HTML/CSS 到 PDF 的专用排版引擎；支持字体配置、PDF 链接和书签。[README](https://github.com/Kozea/WeasyPrint/blob/main/README.rst)、[API](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html) | BSD-3-Clause。[LICENSE](https://github.com/Kozea/WeasyPrint/blob/main/LICENSE) | 如果复杂分页要求超过 Chromium 可控程度，可用作独立服务备选；需重测 CSS 与图表静态化，不默认与浏览器预览一致。 |
| ReportLab | 以 Python 直接构造 PDF 与图表的 toolkit，README 区分开源 toolkit 与商业 RML。[项目镜像 README](https://github.com/MrBitBucket/reportlab-mirror/blob/master/README.txt) | 开源 toolkit 使用 BSD 风格许可，商业 RML 另计；本次证据是项目 GitHub 镜像，不应把它称成唯一上游权威。[LICENSE](https://github.com/MrBitBucket/reportlab-mirror/blob/master/LICENSE) | 固定报表备选；复杂中文长方案维护成本需试验，不作首选。 |

Docling 的结构JSON/页序/表格可保留产品依据，MarkItDown 明确面向文本分析而不是高保真转换；XLSX还要逐表验证公式、隐藏字段、下拉状态和权限含义。pgvector支持和全文检索结合，适合先用一个权威数据库做混合检索，但中文分词、型号和专业缩写需要真实语料验证。([Docling](https://github.com/docling-project/docling/blob/main/README.md)，[MarkItDown](https://github.com/microsoft/markitdown/blob/main/README.md)，[pgvector hybrid search](https://github.com/pgvector/pgvector/blob/master/README.md#hybrid-search))

## 三、独立保存管线和连续水位让中断恢复可验证

**实时字幕出现不证明音频已经安全保存。** AudioWorklet处理音频，Worker负责重采样/存储；OPFS flush 与 IndexedDB strict transaction有不同确认条件。OPFS和IDB之间没有本项目假定的原子事务，恢复必须扫描自描述日志、校验hash、舍弃截断尾部并重建索引。请求 persist() 可降低自动回收风险，但用户清理、隐私模式、设备故障仍可能删除本机材料。([AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)，[OPFS](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)，[flush](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle/flush)，[IDB transaction](https://developer.mozilla.org/en-US/docs/Web/API/IDBDatabase/transaction)，[Storage quota](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria))

```text
现场麦克风 → AudioWorklet → Worker（实际采样率 → 连续重采样 → PCM16）
                              ├→ OPFS/IDB持久日志 → HTTP归档补传 → 私有存储
                              └→ 实时小帧 → WebSocket网关 → 中文ASR → 文字事件
                                        两条路径独立确认/背压
会议结束 → 归档完整性与缺口检查 → 会后校正/人稿 → 事实快照 → 产品匹配 → 文档
```

建议小帧100–200ms供ASR，约1秒自描述归档块记录epoch/seq、sample_start/frame_count、编码和hash；两种粒度独立。16kHz单声道PCM16每小时 `16000×2×3600` 为 **115.2MB / 109.86MiB**，两小时230.4MB / 219.73MiB，仅纯负载；48kHz同条件则345.6MB/小时。该计算是编码数学，不是性能实测。旧100MiB总额度不覆盖1小时标准PCM，还需索引/副本/缓冲；当前一小时逻辑归档初稿256MiB、本机可用空间独立预检，压缩与原生多声道另算。

云端块按tenant/meeting/epoch/seq与hash幂等，小对象写入和可恢复manifest成功后才durable ACK。首页展示最高连续确认水位而非最大块号，中间缺块必须显现。断网本地继续、网络恢复按missing_ranges补传；ASR故障不停止归档。普通WebSocket没有自动背压，应用必须有限队列并监控bufferedAmount，网络慢时字幕可延后，本机写盘不足则显式告警/停止并记录缺口。([WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket))

1秒32KB的PCM块不是普通S3 multipart part，通常part最小5MiB（末块除外）；可先存小对象/持久分块，再合并回放文件。1秒一个对象约3600PUT/小时，要测请求成本、索引压力和保存延迟；聚合不能提前ACK未持久尾部。tus提供字节偏移续传，但不自动建立会议采样时间线和转写状态。([S3 multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)，[Multipart overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)，[tus protocol](https://tus.io/protocols/resumable-upload))

MediaRecorder可兼容降级，不能把timeslice Blob当独立可播放文件。W3C只要求一次完整录音的全部Blob组合可播放，强杀的不完整尾流要另测恢复。MDN明确timeslice不精确，后台/锁屏可延迟事件；不能由“每秒分片”推出“最多丢1秒”。([W3C recording](https://www.w3.org/TR/mediastream-recording/)，[dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event))

ASR断线建立厂商新session并映射会议sample offset，积压另做补识别，不盲目高速灌入live session。腾讯协议明确约1:1实时发送、间隔和新voice_id约束；阿里中间/句末/完成事件不同；火山不是每帧都有统一回包。原始厂商事件、实时临时/稳定字幕、会后校正和人工修改分别保留版本；speaker_id不跨session自动认同一人。([腾讯流式ASR](https://cloud.tencent.com/document/product/1093/48982)，[阿里WebSocket](https://help.aliyun.com/zh/isi/developer-reference/websocket)，[火山流式](https://www.volcengine.com/docs/6561/1354869))

恢复指标分别计算未本地持久尾部、未服务端持久区间与真实采集缺口；已冻结的水位差为零也不能证明麦克风仍工作。iOS离页/锁屏可进入AudioContext interrupted，Wake Lock可被系统释放，PWA/Service Worker不是后台录音保证。上线声明必须基于Windows Chrome/Edge、Safari、Android/iOS前台实机60/120分钟及中断矩阵；后台强需求需要原生/桌面端或独立录音导入方案。([AudioContext state](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/state)，[Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API))

## 四、产品依据、四页界面和同源文档构成销售闭环

产品库先存版本化原件、能力/限制、核实人、出处、有效期与可见范围，再建立检索索引。关键词/向量/重排都在服务端允许集合内执行，检索后再次join权威权限表过滤，再交给模型；引用、缓存、预览、下载也复核权限。仅提示词约束不能隔离数据。方案匹配保留“可满足/有前提/需定制评估/不支持/待确认”，产品路线图不写成现有能力，参考样板的财务事实/价格/工期不迁移。本段是项目安全与质量设计，并非pgvector自带完整业务权限。

冻结 `FactSnapshot` 同时绑定转写/人稿、产品能力不可变快照、格式/模板版本与scope_mode。确定步骤为会议事实抽取、需求收集、产品匹配、方案及甲方清单、跨章节检查、人工确认、导出；每项需求、决定、数字保留来源。四份文档读取同一底稿，程序计算合计和覆盖率；模型只解释和起草。无明确分期时单版，缺少接口/权限/资料时保留待确认，不删掉原始诉求。

| 页面 | 主要视觉/操作 | 持续可见信息 |
|---|---|---|
| 首页 | 会议标题/设备条、主区实时文字、右区要点、底部时间轴与保存条 | 录音状态、本机/服务端已保存至、待补传、字幕稳定位置与缺口 |
| 历史纪要 | 客户/项目/日期/状态筛选、会议详情与回放、当前版本下载 | 录音完整性、转写/纪要修订、PDF任务与旧版提醒 |
| 产品库 | 产品卡/表、能力与限制、原件页码和核实操作 | 版本、审核/解析状态、依据、有效性与权限 |
| 工作台 | 输入/产物树、中央编辑/预览、右侧来源/需求/待确认 | 同一底稿、REQ去向、章节影响、审核与导出 |

视觉沿指定格式的藏青`#1F3A5F`、石板灰`#3E5C76`、雾蓝`#7489A3`和浅灰底，风险/人工确认少量暖金。Web使用Microsoft YaHei/PingFang/Noto Sans CJK等系统栈，长转写正文约16px，行高1.6；文档黑体/宋体/TNR另处理。桌面220px侧栏、可折叠证据栏，手机四项底部导航和常驻录音条。状态必须配文字/图标，读历史时暂停自动跟随，partial替换同片段不挤走光标；关键故障给恢复动作。shadcn/Radix能帮助定制和键盘基础，真实颜色对比/移动前台/屏幕阅读器仍要验收。([shadcn/ui](https://github.com/shadcn-ui/ui/blob/main/README.md)，[Radix](https://github.com/radix-ui/primitives/blob/main/README.md))

纪要从同一MinutesDocument结构树输出MD与PDF，异步任务按修订/模板/renderer/font hash幂等；PDF成功校验后进入ready，失败MD仍可下载。Playwright page.pdf支持print CSS、页面尺寸/边距/背景和页眉页脚，但页眉模板不继承页面CSS且不执行脚本，需独立样式。中文字体合法部署、A4边距、表头跨页、超高行续表、关键数字文本比对和逐页渲染是验收项，不是本轮已完成的输出。([Playwright PDF API](https://playwright.dev/docs/api/class-page#page-pdf))

Chromium只处理受信模板和转义结构树，禁止上传HTML或模型URL触发任意网络请求，资源限定审核本地目录，防止SSRF。短期签名URL在撤权后可能到期前仍有效；需要即时撤权的下载使用鉴权代理/网关复核。PDF离线来源显示时间/页码/版本，不嵌token。会议纪要讨论稿可直接下载，正式售前方案仍按指定规范先Word审核、再从已审版本转PDF；python-docx创建DOCX但不包含PDF转换引擎。([python-docx](https://github.com/python-openxml/python-docx/blob/master/README.md))

## 五、先通过录音故障实验，再把生成能力接入真实销售流程

实施先完成现场采集/本地持久/断网与崩溃PoC，再实时ASR/会后定稿及纪要PDF，然后产品库核实检索、方案和需求工作台，最后权限、负载、备份与上线验证。UI设计系统并行落地，但主链必须先证明能保存证据。每步留下可审阅采样计数、块hash、manifest、恢复日志、文本版本或逐页导出图；流程成功页面不能代替这些证据。

| 验证主题 | 最少实验与产物 | 影响决策 |
|---|---|---|
| 音频可靠性 | 60/120分钟、断网10分钟、ACK丢失/乱序、强杀、配额满、设备拔出、多标签、OPFS/IDB不同步 | 设备支持范围、flush/块粒度、实际损失尾部 |
| 中文ASR | 真实授权远场/噪声/多人/产品名/数字否定语料，关键实体错漏、校对时间和账单 | 云服务主选与私有化条件；不预设赢家 |
| Agent与产品 | 需求召回、证据正确、未核实能力不承诺、默认单版、跨章节一致、重启/重复任务恢复 | 图节点/模板/规则/重试边界 |
| 权限 | 越权搜索、缓存、来源、下载、任务ID猜测与撤权 | 服务端硬过滤和访问策略 |
| PDF/UI | 中文多页/长表/图片/字体逐页图；四页手机前台/键盘/错误状态 | 字体许可、模板、支持浏览器与正式下载能力 |
| 运维成本 | ASR实时+校正分钟、LLM各步token、对象PUT/容量/下载、数据库索引、PDF并发、备份恢复 | 企业预算与实际容量/保留政策 |

本次资料来源统计必须与研究广度分开理解。Agent专项记录66个初始请求URL（62个HTTP200、2个404、2个403），其中去重有效官方正文/API为54个；搜索结果只用于发现，无关200页、SPA空壳、重定向重复不算有效来源。音频专项记录46个成功官方URL，12个HTML文本派生副本不另计。会议/UI/导出专项核查15个项目README/许可证及2个排版API，未在此重新构造未经核对的成功来源总数。三份笔记引用URL并集133只是引用计数，包含发现/失败/非正文链接，不等于133份实取有效资料，也不把缓存文件数当来源数。

Firecrawl在本环境分别遇到未认证和CLI依赖异常，随后采用官方GitHub Raw/API、厂商与规范站点直接只读HTTP取证；GitHub搜索有403限流，部分宽查询返回无关内容，均保留并弃作事实证据。没有登录或绕过认证，也没有因为某URL失败宣称能力不存在。源笔记与缓存保留取证时间/URL/许可和失败轨迹：[平台与工作流](<agent-platforms.md>)、[实时音频](<realtime-audio.md>)、[会议/UI/导出](<meeting-ui-exports.md>)，原始抓取位于工作区`.firecrawl/20261015-*`。官方分支未来会变化，来源快照不替代锁版后的许可/安全审查。

研究仍缺真实产品资料、组织权限、客户授权、提供商合同/价格、设备PoC与中文质量测量，因此不提供模型准确率、时延、硬件配置或成本排名。下一步的架构依据应是录音保存边界和产品承诺证据：只有它们可验证，漂亮的实时文字和方案才具有业务可信度。完整实施契约已写入[实时平台设计](realtime-platform-design.md)，四页线框与状态写入[UI规范](ui-spec.md)，可据此开展开发评审而无需先选择整套平台fork。

