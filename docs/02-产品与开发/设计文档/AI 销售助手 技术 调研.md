# 把销售访谈转成可验证业务演示

调研日期：2026-10-12，Asia/Shanghai。状态：**方案草案，公开资料调研已整理，项目 PoC 尚未执行**。

面向软件公司售前的手机 Web 助手，最合适的首期路线是**前台录音、录后异步转写、有来源的需求草稿、销售冻结版本、固定业务模板加受控 Agent、服务端真实前后端预览**。价值来自会谈到可演示流程的闭环；整合一个完整开发者 builder 不是必要起点。手机端保留首页、Demo 广场、生成 Demo、我的四入口，主要处理采集、确认和查看；代码执行放在独立服务端环境。平台推荐候选是 React/TypeScript/Vite/Ant Design Mobile + FastAPI/PostgreSQL，Demo 采用 React/FastAPI/独立 SQLite。中文 ASR 先比较境内云，Agent SDK 可搭配国内兼容模型，但兼容性、网络、许可和隔离要逐项验证。所有配额、生成成功率和成本结论仍需样本证据，本轮未编写应用或调用真实模型/ASR。

## 前台保存完整音频比实时字幕更适合首个闭环

手机 Web 有明确可用的麦克风入口：getUserMedia 在安全上下文可用并需要用户授权，正式手机访问应使用 HTTPS；电脑 localhost 的例外不能套用到手机访问局域网 HTTP。设备不存在、权限拒绝和硬件读取失败都有不同错误，产品可以分别给出上传文件或粘贴谈话的降级操作。浏览器麦克风授权只是设备权限，不能替代销售向客户说明录音、转写和 AI 处理目的。([MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)，[个人信息保护法](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm))

最容易被低估的是保存语义。**MediaRecorder 分片不是独立音频文件**：规范允许 timeslice 或 requestData 产生的单独 Blob 不可播放，完整录制的 Blob 组合才有可播放要求。stop 之后仍有最终 dataavailable，然后才触发 stop 事件；调用 stop 返回不能当作最后一片上传完成。因此方案必须保存 recording_stream_id、seq、实际 MIME/codec、hash 与服务器 ACK，等最终片和全部 ACK 后 finalize，由服务器按完整流合并、解码和转码。重建 Recorder 要创建新流，各流分别解码后按会话顺序组合。([W3C MediaStream Recording](https://www.w3.org/TR/mediastream-recording/))

分片周期也不是时钟。Safari 暂停麦克风、Android Chrome 锁屏或主线程阻塞都会延迟 dataavailable，产生更大的 Blob；应用不能用“分片数 × 5 秒”计算实际时长。isTypeSupported 探测格式有用，但 true 仍可能因资源不足失败。WebKit 历史文档中的 MP4/AAC 支持描述不能代替当期 Safari 的实际 MIME 探测，更不能证明宿主 WKWebView 的能力。([MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event)，[MIME 探测](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static)，[WebKit](https://webkit.org/blog/11353/mediarecorder-api/))

IndexedDB 适合暂存未确认片，但默认 best-effort 存储会受到配额、清理和回收影响。即使请求持久化，也不能保证用户清理数据或操作系统 kill 后恢复未发出的尾片。由此，首期支持范围应写成经测试的前台 Safari/Android Chrome，明确没有后台、锁屏或普通电话/微信系统音频录制保证；微信内置浏览器需要单独 PoC。恢复目标是可解释地保存已收到的部分，并诚实标记缺失，而非宣传无损恢复。([MDN 存储规则](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria))

录后异步转写使保存、重试和需求生成解耦。阿里文件识别采用异步任务与查询，腾讯支持轮询/回调，火山标准版分 submit/query；这些路径与“完整文件确认后开始分析”一致。实时流式协议还涉及握手、音频帧、序号、终止与 partial/final 语义，MediaRecorder Blob 不是通用实时帧。faster-whisper 的实时模式依赖外部集成，也不能把它的离线文件接口称为原生流式 ASR。([阿里文件 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)，[腾讯 CreateRecTask](https://cloud.tencent.com/document/product/1093/37823)，[火山文件 API](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh)，[火山流式 API](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelstreamingautomaticspeechrecognitionAPI?lang=zh)，[faster-whisper](https://github.com/SYSTRAN/faster-whisper))

| 路线 | 对本项目的贡献 | 首期代价与判断 |
|---|---|---|
| 录后文件 ASR | 完整保存后转写、回听、修订、证据定位。 | 首期推荐，失败可基于原件重试。 |
| 实时流式 ASR | 访谈中字幕、提示下一问题。 | 后续验证销售价值；仍需独立保存原音。 |
| 手机浏览器本地模型 | 离线/隐私潜在优势。 | 下载、内存、发热和模型兼容未测，首期不承担。 |

中文服务选择应由同语料实验决定。阿里作为首轮主候选、腾讯与火山作为对照，是考虑异步文件接口和境内部署路径的设计建议，没有本项目准确率排名。阿里和腾讯的结果窗口在所核查接口中为 24 小时，平台应及时保存结果，不能一直引用供应商短期 URL。腾讯 diarization 与需要声纹样本的 SpeakerRoles 是不同能力；匿名说话人分离不意味着客户身份或购买决策角色识别。([阿里 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)，[腾讯 API](https://cloud.tencent.com/document/product/1093/37823))

| 中文 ASR 候选 | 核查事实与许可 | 适配边界 |
|---|---|---|
| 阿里文件 ASR | 异步、时间信息、单声道说话人分离；具体模型和账号条款独立。 [官方](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api) | 完整文件、结果下载和区域/词表/计量 PoC。 |
| 腾讯文件 ASR | URL 文件、TaskId、轮询/回调、热词与分离；不同引擎能力不同。 [官方](https://cloud.tencent.com/document/product/1093/37823) | 核验适用引擎、增值能力及限制。 |
| 火山标准文件 ASR | submit/query、格式、热词、聚类；距离/音量变化影响区分。 [官方](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh) | 转码、时间映射、回调及网络测试。 |
| 讯飞长音频接口 | 分片/合并/结果查询；官方说明分离仍可能不足商用。 [官方](https://www.xfyun.cn/doc/asr/lfasr/API.html) | 采购接口版本单独核查，不泛化到全部讯飞产品。 |
| FunASR | 工具代码 MIT；模型权重另有自定义条款。 [代码许可](https://github.com/modelscope/FunASR/blob/main/LICENSE)、[模型许可](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE) | 中文私有化候选，每个 Paraformer/CAM++/VAD checkpoint 单独核验。 |
| Whisper / faster-whisper | Whisper 代码和官方权重 MIT；faster-whisper 库 MIT、CTranslate2/量化/VAD。 [Whisper](https://github.com/openai/whisper)、[faster-whisper LICENSE](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) | 多语言/私有化对照；第三方模型、VAD 仍分开登记。 |
| whisper.cpp / sherpa-onnx | 前者 MIT、C/C++/量化/WASM；后者代码 Apache-2.0、ONNX/流式等。 [whisper.cpp](https://github.com/ggml-org/whisper.cpp)、[sherpa LICENSE](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE) | 原生、CPU/边缘后续候选，原生示例不证明手机网页性能。 |

FunASR 权重不能概括为 MIT：本轮 MODEL_LICENSE 为 1.1，包含行为条件、终止及修订条款；SenseVoiceSmall 模型卡写 license: other 并引用该模型协议。faster-whisper 项目 benchmark 的速度数字有硬件、精度和 batch 条件，不能作为本项目吞吐承诺。([FunASR MODEL_LICENSE](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)，[SenseVoiceSmall](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)，[benchmark](https://github.com/SYSTRAN/faster-whisper#benchmark))

这些 ASR 仓库的维护快照有近期提交：FunASR 2026-10-08、Whisper 2026-08-31、faster-whisper 2026-10-10、whisper.cpp 2026-10-11、sherpa-onnx 2026-10-12；日期来自本轮 API/commit 证据，只证明有活动，不证明 release 稳定。正式使用必须固定版本和模型清单，再以至少 20 段授权样本测 CER、关键业务实体、否定/金额、DER、人工修订时间、失败率和实际账单。([FunASR commit](https://github.com/modelscope/FunASR/commit/e7e61293d308f4342ab9307895e710e4b51b949c)，[Whisper commit](https://github.com/openai/whisper/commit/86098128c0b4f24f0e2aa2994de830614b474227)，[faster-whisper commit](https://github.com/SYSTRAN/faster-whisper/commit/a52b026ac844c02117865e61968547639b60a6f8)，[whisper.cpp commit](https://github.com/ggml-org/whisper.cpp/commit/7e26d3b0d5bced6c8217ef09710ec2f969001241)，[sherpa commit](https://github.com/k2-fsa/sherpa-onnx/commit/6e7ea3e409f90aaf1541c87f21a013c4f20b9680))

## 需求确认应成为 Agent 的输入边界

AI 总结应拆成来源、认知和人审三个维度。source_kind 区分 customer_quote、sales_note、ai_suggestion、customer_feedback；epistemic_status 区分 fact、inference、unknown；confirmation 记录 pending、accepted、edited、rejected。销售明确补充可以成为销售来源的事实，但不能冒充客户原话。这个设计使业务目标、痛点、实体、角色、流程、功能优先级、限制、集成、验收和开放问题能被逐项检查，而不只是阅读一段听起来合理的总结。

Structured Outputs 能约束形状，不能证明内容真实。OpenAI 官方文档说明输出仍可能有 mistakes、Schema 子集及 refusal/incomplete 路径；Anthropic 也区分 JSON outputs 与 strict tool use 并说明限制。Qwen 的严格 Schema 支持依模型和 thinking/non-thinking 模式变化；DeepSeek JSON mode 保证 JSON 字符串但有 empty content 边界，其 strict tool calling 当前使用 beta endpoint。平台必须按具体 model/API/mode 记录能力，支持 strict 时使用，其他情况走服务端结构/语义校验与有界纠正。([OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)，[Anthropic](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)，[Qwen](https://www.alibabacloud.com/help/en/model-studio/qwen-structured-output)，[DeepSeek JSON](https://api-docs.deepseek.com/guides/json_mode)，[DeepSeek tools](https://api-docs.deepseek.com/guides/tool_calls))

**确认后的不可变需求版本才是生成依据。** 原始转写和人工更正保存版本，需求引用 segment/message ID 和时间；销售确认目标、角色、主流程、演示范围及默认假设后，由服务器记录身份、version 和 canonical_hash。新聊天或反馈建立新 draft，旧 generation_job 不变。只有影响本次 Demo 核心行为的歧义阻塞确认；外部集成缺少规范时显式排除，不能悄悄生成看似真的接口。这是项目推荐，不是任何 SDK 自动提供的业务功能。

Agent 选型也应围绕边界而非角色数量。OpenAI Agents SDK 提供 tools、guardrails、handoffs、sessions、tracing，MIT 许可；官方模型接口支持兼容 client，但提示 provider feature differences。MVP 可先 PoC 显式 Chat Completions adapter 接百炼/DeepSeek，只给自定义 patch/read/list/fixed-check 工具，由平台保存 job，由 supervisor 隔离代码执行。SDK 名称不意味着调用 OpenAI 模型服务。([SDK README](https://github.com/openai/openai-agents-python)，[LICENSE](https://github.com/openai/openai-agents-python/blob/main/LICENSE)，[Models](https://openai.github.io/openai-agents-python/models/))

此 SDK 默认 tracing 启用且 processor 会导出；更换模型 base_url 不自动更换追踪去向，因此接入前要关闭默认出口或配置已审查的自定义审计。RunState 人工暂停/恢复也要求服务器保护快照、认证审核人、校验 pending call 和防重复消费；会话记忆不是平台 durable job。([Tracing](https://openai.github.io/openai-agents-python/tracing/)，[HITL](https://openai.github.io/openai-agents-python/human_in_the_loop/))

| 框架 | 官方能力、许可与当前状态 | 项目判断 |
|---|---|---|
| OpenAI Agents SDK | 工具/会话/HITL/tracing，MIT。 [官方](https://github.com/openai/openai-agents-python) | 首轮受控 worker PoC；兼容及恢复必须实测。 |
| OpenHands Software Agent SDK | 编辑/terminal/conversation、Agent Server、TS client；MIT。 [README](https://github.com/OpenHands/software-agent-sdk)、[LICENSE](https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE) | 更完整 coding 执行第二候选，平台仍负责版本/预算/发布。 |
| LangGraph | checkpointer、interrupt、恢复；MIT，节点重跑仍需副作用幂等。 [持久化](https://docs.langchain.com/oss/python/langgraph/persistence)、[语义](https://docs.langchain.com/oss/python/langgraph/graph-api)、[许可](https://github.com/langchain-ai/langgraph/blob/main/LICENSE) | 后续复杂分支 AI 子流程，不首期重复维护顶层状态。 |
| Dify | 可视化工作流/RAG/Agent；modified Apache-2.0。 [README](https://github.com/langgenius/dify)、[LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE) | 内部验证候选；多租户 SaaS 不直接默认复用。 |
| AutoGen | 官方当前 maintenance mode、无新功能，推荐 Microsoft Agent Framework；代码 MIT。 [README](https://github.com/microsoft/autogen)、[许可](https://github.com/microsoft/autogen/blob/main/LICENSE-CODE) | 无既有依赖，不作为新项目首选。 |
| Microsoft Agent Framework | Python/.NET、图式工作流/checkpoint/HITL/OTel，MIT。 [README](https://github.com/microsoft/agent-framework)、[许可](https://github.com/microsoft/agent-framework/blob/main/LICENSE) | 团队偏 .NET 时评估，当前不需额外引擎。 |

Dify 的两个边界应直接写入选型记录：其源码未经书面许可不能运行 multi-tenant environment，条款以一个 workspace 为 tenant；使用 web 前端时不得修改 LOGO/版权，未用前端时相关条款不适用。OpenHands persistence 官方列出 managed secrets 等持久内容，因此不能把 SDK 会话目录作为公开源码 bundle。代码库许可不覆盖云服务合同、模型权重或生成物依赖。([Dify LICENSE](https://github.com/langgenius/dify/blob/main/LICENSE)，[OpenHands persistence](https://docs.openhands.dev/sdk/guides/convo-persistence))

境内运营优先评估百炼/Qwen 与 DeepSeek是部署建议，需实际企业账号、地域、数据协议和网络证明。百炼兼容文档当前要求业务空间/地域与专属 base_url 匹配；OpenAI 和 Anthropic 本轮支持地区列表未列中国大陆，后者还涉及实体注册与控制关系，不能把境外服务器当作当然可运营路径。([百炼兼容](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)，[OpenAI 地区](https://platform.openai.com/docs/supported-countries)，[Anthropic 地区](https://www.anthropic.com/supported-countries))

## 固定模板比整套 builder 更贴合手机售前

首期目标是缩短售前跟进等待，让销售尽早用清晰的核心业务流程讨论需求。模板优先把能变的中文字段、枚举、页面、筛选、合成数据和有限状态流转交给 Agent，把锁文件、权限、检查器、网关和网络策略留给平台。CRM-lite、工单、简单审批是本方案首批建议；相比进销存，简单审批更容易把一条主流程和有限规则演示清楚，进销存可在确认高频需求后加入。三类选择仍需要售前代表验证，不是已完成需求覆盖研究或生成时延承诺。

每个 Demo 必须有实际 React 界面、FastAPI HTTP API 和隔离 SQLite。创建、读取、编辑、删除、筛选和状态转换要经过后端，写入后刷新及重启仍可读；外部 ERP、短信、付款和签章明确模拟或排除。MVP 同 revision 的授权访客共享合成数据，公开提示多人写入，owner 可 reset；每客户独立数据库副本后置，避免把简单 share token 误称为数据隔离。

| builder/代码项目 | 本轮核查事实 | 许可及维护限制 | 推荐用途 |
|---|---|---|---|
| bolt.diy | WebContainers 工作台、starter、文件修改、ZIP 导出与部署。 [README](https://github.com/stackblitz-labs/bolt.diy/blob/main/README.md) | 仓库 MIT；WebContainer 商业 API 另授权。 [LICENSE](https://github.com/stackblitz-labs/bolt.diy/blob/main/LICENSE) | 参考生成/预览体验，不直接作为移动 SaaS 控制层。 |
| OpenHands Agent Canvas | 当前主仓定位 coding agent 控制中心；SDK/Agent Server 分仓。 [README](https://github.com/OpenHands/OpenHands/blob/main/README.md) | 当前主仓 MIT；不能沿用历史架构教程。 [LICENSE](https://github.com/OpenHands/OpenHands/blob/main/LICENSE) | 参考调度/日志，实际集成优先 SDK。 |
| Dyad | Mac/Windows 本地 builder、用户自带模型 key。 [README](https://github.com/dyad-sh/dyad/blob/main/README.md) | src/pro 外 Apache-2.0；Pro 为 FSL-1.1-ALv2。 [根许可](https://github.com/dyad-sh/dyad/blob/main/LICENSE)、[Pro](https://github.com/dyad-sh/dyad/blob/main/src/pro/LICENSE) | 桌面原型参考，不能当作宽松许可的移动后端。 |
| gpt-engineer | prompt 文件 CLI/实验平台；旧组织链接重定向。 [README](https://github.com/AntonOsika/gpt-engineer/blob/main/README.md) | MIT、已归档；商业 app 单独产品。 [LICENSE](https://github.com/AntonOsika/gpt-engineer/blob/main/LICENSE)、[API](https://api.github.com/repos/gpt-engineer-org/gpt-engineer) | 历史流程参考，不新增维护依赖。 |

Dyad 的 FSL Pro 条款禁止规定的 Competing Use，具体版本在第二周年后转 Apache-2.0，不能把所有当前 Pro 代码提前视为 Apache。bolt.diy 的 MIT 也不能消除底层 WebContainer 商业生产 API 的授权要求。WebContainers 官方生产定义包含为客户、潜在客户和员工提供的商业用途，原型 PoC 例外不覆盖未来售前 SaaS 的正式使用。([Dyad Pro LICENSE](https://github.com/dyad-sh/dyad/blob/main/src/pro/LICENSE)，[WebContainers 商业](https://webcontainers.io/enterprise))

本轮维护快照：bolt.diy 未归档、pushed_at 为 2026-10-11；OpenHands Canvas 未归档、2026-10-12；OpenHands SDK 未归档、2026-10-11；Dyad 未归档、2026-10-12；gpt-engineer 已归档、2025-05-14。最近 push 不能证明稳定 release 或安全响应，实施应固定 tag/commit。没有证据表明 bolt.diy/Dyad 的公开 headless API 可以直接承接本项目多租户契约，因此整套 fork 需要单独维护评估。([bolt API](https://api.github.com/repos/stackblitz-labs/bolt.diy)，[OpenHands API](https://api.github.com/repos/OpenHands/OpenHands)，[SDK API](https://api.github.com/repos/OpenHands/software-agent-sdk)，[Dyad API](https://api.github.com/repos/dyad-sh/dyad)，[gpt-engineer API](https://api.github.com/repos/gpt-engineer-org/gpt-engineer))

自由生成多 Agent 的优势是更大栈和复杂业务覆盖；代价是文件归属、预算、依赖、外部副作用和修复循环更难控制。模板路线的局限是覆盖有限，超出范围必须明确缩减或人工处理。两条路线的比较是工程判断，没有本项目成功率数据，后续由样本覆盖率和失败类型决定是否放宽。

## 服务端隔离与窄权限预览决定能否给客户使用

WebContainers 的 Node runtime 是浏览器里的开发环境，不是手机 FastAPI/SQLite 服务器替代。官方支持页偏 desktop Chromium，非 Chromium 的预览/第三方资源有限制，依赖 SharedArrayBuffer 和跨域隔离；Safari 支持描述不能推导手机稳定运行。对四个售前页面，手机只看独立服务端预览更符合业务边界。([介绍](https://webcontainers.io/guides/introduction)，[浏览器支持](https://webcontainers.io/guides/browser-support))

| runtime | 已核查事实/许可 | 项目选型边界 |
|---|---|---|
| 加固 Linux Docker | namespace/cgroup/capability；默认隔离有局限。 [官方](https://docs.docker.com/engine/security/) | 内部有限模板试点基础设施，普通共享主机 Docker 不足任意代码边界。 |
| gVisor | OCI runtime、用户态 application kernel，减少直达内核接口；兼容/开销有代价。 [官方](https://gvisor.dev/docs/)、[仓库](https://api.github.com/repos/google/gvisor) | 独立 runner 加强隔离候选，Apache-2.0；不是微 VM。 |
| E2B | JS/Python SDK 控制 sandbox，SDK 仓库 Apache-2.0。 [README](https://github.com/e2b-dev/E2B/blob/main/README.md)、[LICENSE](https://github.com/e2b-dev/E2B/blob/main/LICENSE) | 托管候选，runtime 自托管/依赖许可与大陆可达性另核。 |
| Daytona 托管产品 | 当前 sandbox classes、preview、网络策略。 [sandbox](https://www.daytona.io/docs/en/sandboxes/)、[preview](https://www.daytona.io/docs/en/preview/) | 可做服务 PoC，账户 tier、地域和价格不预设。 |
| Daytona 旧公开 core | 2026 年 6 月开发迁到私有 codebase，旧仓停止更新/修复/release，已归档。 [README](https://github.com/daytonaio/daytona/blob/main/README.md)、[API](https://api.github.com/repos/daytonaio/daytona) | v0.190.0 是 AGPLv3，历史 fork 自担维护；不能推荐为持续维护的开源 core。 [固定许可](https://github.com/daytonaio/daytona/blob/v0.190.0/LICENSE) |

Docker 官方说明 daemon 控制、宿主目录挂载和默认 capabilities 的攻击面；本项目要使用独立 runner、非 root、无 docker.sock/宿主挂载、资源限制和运行时禁出网。**客户外部分享前的门槛是强隔离验证，而不是“用了 Docker”**。gVisor 或微 VM、适当托管沙箱必须与模板、Python wheels、SQLite 快照、Node 构建和检查器一起 PoC。([Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)，[gVisor](https://gvisor.dev/docs/))

托管沙箱也有容易误用的默认。E2B 默认联网，可以配置禁网/allow list；pause 后不可访问，kill 不可恢复，默认 timeout 是 kill，auto-pause 要显式选择，paused 文档当前没有自动 TTL。因此平台仍需 own 生命周期、源码和数据库快照，不把 vendor pause 当永久备份。Daytona 普通 preview token 是 sandbox-wide credential，可触达 toolbox/terminal；客户分享只能用受限单端口签名或平台网关，不能给管理 token。网络策略能力还受账户 tier 影响。([E2B network](https://docs.e2b.dev/sandbox/internet-access)，[persistence](https://docs.e2b.dev/sandbox/persistence)，[Daytona preview](https://www.daytona.io/docs/en/preview/)，[network limits](https://www.daytona.io/docs/en/network-limits/))

建议平台与生成物使用不同可注册主域、host-only cookie、独立鉴权 audience 和网关映射业务端口，配置 CSP/CORS。客户 bearer 只绑定 demo_revision，不能看到录音、平台 PG、源码管理和 terminal。私密分享建议 7 天，实际取政策/请求时长/产物剩余寿命的最小值，可即时撤销；30 分钟空闲后休眠是资源政策，唤醒不能延长分享。生成物使用合成数据，客户派生案例只有 owner/admin 明确脱敏发布才进公共目录；平台模板才默认全局可见。

质量 gate 应由固定检查器掌握：依赖锁与允许 patch、前端 build、后端 health、实际 CRUD、重启后持久化、SQLite 快照恢复及手机 smoke 全部通过，才允许 succeeded。自动修复最多两轮是试点政策；Agent 自报成功、删掉检查器或把后端改 LocalStorage 都不通过。prompt injection 防护需要指令/数据分离、输入输出验证、人审与最小权限，不能靠一句提示保证安全。([OWASP](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html))

## 持久任务、留存与实测成本构成运营基线

平台 PG 是 job 状态事实，Celery/broker 只做投递。job 创建与 outbox 同事务，worker 原子争取 lease、heartbeat 和 fencing token，旧 lease 的 worker 不能再次发布；重复投递不无条件重复沙箱。外部模型请求发出而结果未落库时仍可能重复计费，不能宣称 exactly-once。Celery ACK、visibility timeout、worker-lost 和最长任务须组合故障测试。Redis 8 的 RSAL/SSPL/AGPL 选择不能统称宽松开源；Valkey 是 BSD-3-Clause，但 Celery Redis transport 的指定版本兼容仍待测试。([Celery tasks](https://docs.celeryq.dev/en/stable/userguide/tasks.html)，[broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html)，[Redis licenses](https://redis.io/legal/licenses/)，[Valkey COPYING](https://github.com/valkey-io/valkey/blob/unstable/COPYING))

generation_job 状态统一为 queued、planning、generating、validating、repairing、starting、succeeded、failed、cancelled、timed_out；cancel_requested 是独立请求标志。一次人工重试建立新 attempt，自动修复留在该 attempt；更改需求必须新版本和 job。runtime running/sleeping/expired 与历史 succeeded 分离，避免休眠看成生成失败或到期看成从未验证。完整转换和接口见[数据/API](data-and-api.md)，此处是项目建议，没有证明队列恢复已通过。

保留建议区分四类材料：原音/分片/转码 30 天、转写全文 180 天、源码/SQLite 快照 30 天、必要已确认证据摘录及 confirmed spec 按项目目的保留至删除。原音到期显示无法回听，全文到期显示仅存引用摘录，不让证据链接看似可访问。删除先立即撤销访问，再异步清理对象和隔离备份；备份建议滚动 30 天并在恢复前重放删除清单。上述数字是试点政策而非法定期限，需业务和数据责任人确认。

个人信息保护法要求处理前说明目的、方式、种类、保存期限，并按实现目的的最短时间保存；委托处理、敏感信息与境外提供有分别要求。不能把所有普通访谈音频一律等同生物识别，也不能把“转写结果 24 小时失效”推断为厂商音频已经删除。候选云服务的数据用途、训练政策、源音/日志保留、删除和地域需以实际合同核验。([官方法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm))

成本模型采用实测输入：ASR 计费分钟 × 当期价，加所有分析/生成/修复/retry 输入和输出 token 成本，加沙箱活动分钟/资源成本、存储与出站流量；自托管还计闲置机器、GPU、备份和运维。unknown usage 不能记为零，缓存 token 依具体提供方计量。暂定单次 30 分钟/100 MiB、每 attempt 自首次 lease acquisition 起 15 分钟活动执行（不含排队，恢复不重置，manual retry 新 attempt 仍受累计预算）、自动修复 2、用户/租户并发 1/2、2 vCPU/2 GiB sandbox，都用于校准风险和预算，不是厂商限额或测得容量。

P0 应收集浏览器设备/版本和失败恢复记录、同语料 ASR 对照、provider tool/schema/refusal/timeout/usage 测试、模板真实 CRUD、队列重投/取消证据和隔离/国内网络结果，再判断 P1/P2/P3 的开放程度。大陆网络至少拆为模型 API、sandbox 控制 API、preview 域名、依赖/镜像下载四链路；办公室 Wi-Fi 可用不能证明客户手机网络可用。没有真实调用，本报告不填现价、延迟、准确率、成功率或优惠。

### 结论与来源追溯

决定实施难度的不是选了多少 Agent 框架，而是能否让每次演示都回答“谁确认的什么范围、依据哪段谈话、实际验证了哪些行为、客户能访问哪些资源”。因此下一阶段最有价值的投入是少量授权样本和三模板基线，不是自由生成页面数量。只要版本、检查和预览边界保持稳定，ASR、模型和 coding SDK 可以逐步替换，售前的确认习惯无需跟随供应商变化。

公开资料能支持技术路线和排除错误假设，无法替代项目实测。下面的追溯表连接本轮资料、建议及验证责任；主分支及服务政策会变化，实施前需锁定版本并重新核查。原始抓取保留在本地 .firecrawl 缓存，不作为客户交付，不公开重发布。

| 决策主题 | 官方来源入口 | 原始研究笔记 | 待收敛证据 |
|---|---|---|---|
| HTTPS、最终片与完整流 | [MDN](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)、[W3C](https://www.w3.org/TR/mediastream-recording/) | [录音/ASR](<audio-and-asr.md>) | iPhone/Android/微信、断网/中断/大 Blob/实测 MIME。 |
| 境内文件 ASR | [阿里](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)、[腾讯](https://cloud.tencent.com/document/product/1093/37823)、[火山](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh) | [录音/ASR](<audio-and-asr.md>) | 同语料误差、人工修订、账号/合同/成本。 |
| 私有 ASR 与权重许可 | [FunASR](https://github.com/modelscope/FunASR)、[Whisper](https://github.com/openai/whisper) | [录音/ASR](<audio-and-asr.md>) | 固定 checkpoint 与 GPU/CPU 运维成本。 |
| provider 与 coding SDK | [Agents Models](https://openai.github.io/openai-agents-python/models/)、[百炼](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)、[DeepSeek](https://api-docs.deepseek.com/guides/tool_calls) | [需求/Agent](<requirements-and-agents.md>) | 工具/Schema/拒绝/截断/流式/取消/费用测试。 |
| 状态与队列 | [Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html)、[Valkey](https://github.com/valkey-io/valkey/blob/unstable/COPYING) | [需求/Agent](<requirements-and-agents.md>) | 固定版本 lease/fencing、故障与重投实验。 |
| builder 维护与授权 | [bolt](https://github.com/stackblitz-labs/bolt.diy)、[Dyad](https://github.com/dyad-sh/dyad)、[OpenHands SDK](https://github.com/OpenHands/software-agent-sdk) | [生成/runtime](<demo-generation-and-runtime.md>) | 固定源码/依赖许可，避免整站耦合。 |
| 运行隔离与分享 | [Docker](https://docs.docker.com/engine/security/)、[gVisor](https://gvisor.dev/docs/)、[E2B](https://docs.e2b.dev/sandbox/persistence)、[Daytona preview](https://www.daytona.io/docs/en/preview/) | [生成/runtime](<demo-generation-and-runtime.md>) | 强隔离、窄端口 token、国内移动网络、持久快照。 |
| 授权和删除 | [网信办法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm) | [录音/ASR](<audio-and-asr.md>) | 真实主体/合同/授权文本与删除恢复演练。 |

对应交付方案：[功能](../../01-%E5%95%86%E5%8A%A1%E4%B8%8E%E9%9C%80%E6%B1%82/%E5%AE%A2%E6%88%B7%E8%B5%84%E6%96%99/functional-spec.md)、[架构](technical-design.md)、[ADR](0001-template-first-and-isolated-runtime.md)、[阶段验收](../../03-%E6%B5%8B%E8%AF%95%E4%B8%8E%E4%BA%A4%E4%BB%98/%E6%B5%8B%E8%AF%95%E9%AA%8C%E6%94%B6/phase-plan-and-acceptance.md)、[配置](../../../config/settings-catalog.md)、[模板](../../../templates/README.md)。
