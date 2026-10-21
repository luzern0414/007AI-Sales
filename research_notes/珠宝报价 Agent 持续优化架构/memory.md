# 珠宝报价 Agent 的记忆与持续改进架构（2026-10-16）

## 记忆应怎样组织，才能改善报价判断而不污染正式业务规则？

### Takeaway
记忆应保存有来源、有适用边界、有结果的业务经验，不应只保存聊天摘要。010ERP 宜把任务状态、业务事实、决策案例和程序性经验分开；公式/金价/毛利底线属于受控业务资产，记忆只能提出变更候选，不能改写。

### Cited Findings
- LangGraph 官方将短期记忆定义为 thread 范围的状态，通过 checkpointer 持久化；长期记忆通过自定义 namespace 的 store 跨会话保存。语义、情节和程序记忆与语义搜索是不同概念；生产须使用数据库支持的存储，不能把 InMemoryStore 当生产持久化。— [Memory overview](https://docs.langchain.com/oss/python/langgraph/memory)
- LangGraph 明确 checkpointer 用于运行状态与恢复，store 用于跨线程持久信息，两者不能互相替代。— [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- LangMem 的语义记忆可用严格 schema 的 profile 或逐条 collection；collection 更新需调和既有信息，过度抽取降低检索精度，抽取不足降低召回。官方同时强调相关性不能只看语义相似。— [Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- LangMem 情节记忆示例保存情境、关键考虑、行动、结果；程序记忆支持使用交互轨迹、用户评分优化提示。这是可用 API 机制，不能证明任意企业在线自动优化都会可靠。— [Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- Graphiti 官方开源 README 描述有效时间窗、来源 episode、旧事实失效但保留历史、双时态跟踪，以及关键词/向量/图遍历混合检索。README 中的速度与产品比较是项目方主张，本研究未据此作性能承诺。— [Graphiti README](https://github.com/getzep/graphiti)

### Inferences
以下为结合珠宝 ERP 的设计推导，并非官方框架自动提供的完整财务治理：

1. 任务状态：当前报价版本、目标、已有证据、待核对项目、工具回执、等待审批状态。可恢复任务，不等于长期业务知识；报价已变化须检查状态是否过期。
2. 业务事实：客户合同账期、客户集团归属、结算方式、工艺定义。每条有有效期与证据。当天金价是带来源/时点的行情快照；客户条款是有适用合同和有效期的条款版本，均不能变成永久事实。
3. 决策案例：报价快照→可比报价→差异解释→建议→人工修改/原因→最终审批→是否成交→实际重量/损耗/工时→实际毛利→回款/争议。保存拒绝与失败案例；不能只学成功成交。
4. 程序性经验：例如“比较来料加工报价前先确认材料所有权与工费计价单位”；这是可以复用的检查方法，不是“某客户曾获折扣，因此今后该集团都用此折扣”。
5. 用户偏好独立管理：输出详略、常用筛选、阅读方式；个人偏好不得覆盖主体财务政策。

建议 memory_record 至少含：id、type、tenant_id、legal_entity_id、customer_id/group_id、style/material/purity/settlement_scope、source_ids/source_version、valid_from/valid_to、recorded_at、status、reviewer、confidence_label、supersedes_id、sensitivity/ACL、model/prompt/extractor_version、content_hash。金额/重量/币种/单位存结构化值，不只存自然语言。

生命周期采用 candidate→verified→active→superseded/retracted；approved 与 active 分离，允许未来生效。自动抽取只进入 candidate；从签署合同、批准业务记录可按确定性同步规则产生 verified 事实；影响报价策略/正式制度的经验须业务审核并通过回归评估。重复案例的频次不等于事实可信度，模型自述置信度也不等于业务置信度。

冲突处理不采用“最后一条聊天覆盖”：先判断是否不同主体/客户/工艺/有效期；其次按签署合同、正式规则、已核实实际记录、人工说明等业务定义来源优先级判断；无法调和则标为冲突并补证。保留前后版本。需要同时支持“业务当时是什么”和“系统当时知道什么”，即有效时间与记录时间。

建立 source→memory→analysis→recommendation 的反向依赖。原单据更正、条款撤回、记忆被 retracted 后，失效相关索引/缓存和分析结论，并对尚未执行建议要求重算。历史已执行决策保留当时证据，不静默改写。

检索路径是授权范围→active/有效期→结构化可比条件→关键词/语义候选→业务重排→上下文装配。集团相似只是业务相关性，不产生主体间访问权限；不得先跨租户检索，再仅在输出时过滤。只给模型可见的字段与检索结果，embedding 同样有敏感数据边界。

### Gaps
- 本研究未读该客户真实成交、实际损耗和回款数据，无法估计案例量、模型效果或量化收益。
- 现有项目一期规定敏感报价/工资不进模型：上述是未来获许可的数据处理架构建议；当前可先在本地建立结构化记忆、规则化检索、人工反馈与审计，不代表当前已获外发或嵌入授权。
- 在聊天中让模型“记住”不等于可审计记忆，以上治理须自己实现，不能声称框架自带全部审批、ACL、撤回传播能力。

## 三类技术方案各适合什么，010ERP 应怎样选型？

### Takeaway
建议先在 FastAPI 模块化单体内做受控 MemoryService 和后台任务，使用现有关系数据库作为事实主库；若选择 PostgreSQL，可先关系索引/全文检索，确有语义召回需求且数据获许可再加 pgvector。LangGraph 可作复杂任务恢复工具；无需同时引入 LangMem、Mem0、图数据库。

### Cited Findings
- LangGraph 的 namespace+key JSON 文档存储与内容过滤/相似检索机制，可以支持多作用域记忆；namespace 是组织方法，并不自动构成财务 ACL。— [Memory overview](https://docs.langchain.com/oss/python/langgraph/memory)
- LangMem 除集成 LangGraph store 外，提供核心 API 抽取记忆和优化提示，并展示同步/后台两种形成方式。— [Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- LangMem ReflectionExecutor 可对同会话延迟处理、取消旧任务并重排，避免片段记忆和重复消耗；其本地线程模式在 serverless 调用之间会终止，官方提示可用远端执行器。— [Delayed background processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)
- 本次读到 Mem0 add 文档：infer=True 默认由 LLM 抽取；infer=False 原样存储，混用可产生重复；支持 metadata、user/agent/app/run 标识及 expiration_date；Platform add 可返回 PENDING/event_id。当前该页明确描述 ADD-only additive storage，而非自动覆写删除既有记忆，不能沿用旧印象保证自动冲突消解。— [Add memory](https://docs.mem0.ai/core-concepts/memory-operations/add)
- Graphiti 以 episode 来源、时间事实与实体关系建图，支持自定义实体/边类型、增量写入和混合检索，适用于动态关系与历史查询；其 README 目前列出图后端和 LLM/embedding 配置要求。— [Graphiti README](https://github.com/getzep/graphiti)

### Inferences
比较三条路线：

A. 自建受控存储＋可选 LangGraph/LangMem。最贴合现有 Python/FastAPI：关系表保存业务范围、时态、审批、证据；Graph 只负责复杂分析循环和 checkpoint；LangMem 可后续做候选抽取/提示候选。优点是能复用主体权限、审计、SQLAlchemy 事务；代价是生命周期、冲突、索引失效自己建设。推荐起点。

B. Mem0 式记忆服务。适合快速接入记忆添加/检索、个性化偏好和通用事实抽取；但在 ERP 中不能直接让 add 的结果成为正式条款/政策。应外包一层受控适配器，由自己的数据库记录 scope/source/status。需逐个验证实际采用版本的更新/删除/过期语义、OSS 与托管差异、部署/数据保留策略。引入额外服务并不会替代业务治理。

C. Graphiti/Zep 时态关系图。适合客户集团、关联主体、合同、报价、订单、应收和争议之间的跨实体、跨时间调查。比纯文本相似更容易组织“某次报价时当时有效的关联关系”。但关系抽取仍可能错误，图中事实需来源与审核；小团队需承担图运维、实体消歧和版本治理。待多跳调查明确成为主要瓶颈时引入，不以“有记忆”作为必须上图的理由。

最小本地架构：
- 当前业务服务作为唯一账务/报价事实主库；增加 agent_run/checkpoint、quote_case、feedback_event、memory_record/version、memory_source/dependency、prompt_release、eval_case/result 等表。可先用现有关系数据库，迁 PostgreSQL 应另评估而非为 Agent 强迁。
- 业务事务写入报价审批/修改/结果时，同事务写 outbox；后台 worker 读取、去重、构建候选案例/记忆、校验、等待审核、更新索引。每个事件有幂等键与失败重试，不要求一开始 Kafka。
- 在线流程只读已授权有效记忆、执行确定性报价工具、生成证据与建议；必须即时保存的任务状态和人工确认事实按事务写入，案例归纳/经验提炼异步执行。
- ContextBuilder 装配任务目标、当前报价规则版本、实时行情快照、可比案例、已批准检查方法。每个片段携带来源与作用域；预算不足优先保留正式规则/当前事实，压缩历史案例。
- MemoryService/CaseRetriever 抽象层避免绑定单一框架；将存储治理与提示模板解耦。复杂暂停/补查才用 LangGraph；简单公式、审批、导出仍走现有服务。

### Gaps
- 无本地性能测试，不能比较三种方案延迟/成本/召回，也不引用项目方自报 benchmark。
- LangGraph/LangMem 文档提供通用机制，未证明其支持客户所需所有财务合规与数据隔离，须自身验证。

## 上线反馈怎样变成可靠改进，而不是越用越偏？

### Takeaway
先改进案例检索、字段补齐和调查方法，再评估统计建议与提示版本；长期才考虑模型微调。反馈和结果必须分开，销售接受建议、审批通过、客户成交、实际利润/回款是四种不同信号。

### Cited Findings
- LangMem 支持轨迹＋用户反馈产生程序性提示候选，但示例只是提示优化能力。— [Core concepts](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- LangGraph 官方支持热路径写入与后台写入，并说明热路径增加延迟、依赖 Agent 是否记得写，后台则有更新时效和触发频率取舍。— [Memory overview](https://docs.langchain.com/oss/python/langgraph/memory)
- LangMem 延迟去抖机制专门减少快节奏对话的冗余处理与半成品上下文。— [Delayed background processing](https://langchain-ai.github.io/langmem/guides/delayed_processing/)

### Inferences
反馈表记录 run_id/quote_version、被改字段、前值/后值、结构化原因（口径错误/漏条款/错误可比/推理无依据/建议不适用/表达问题）、操作者及角色、来源证据、时点。点赞仅代表感受；人工改价不自动证明算法错，可能是特批、关系维护或新信息。实际报价结果晚到，按事件关联补齐，不把“未成交”简单归因为价格过高。

持续改进分层：
1. 即时纠正当前任务：用户补充重量/成色/结算方式后重算当前版本，影响相关结论；不立即泛化。
2. 案例记忆：经审核保存某条件下的判断与后续结果，下次优先找到真正可比案例。
3. 经验候选：多案例提出“比较前应检查什么”，附支持案例、反例与适用边界，业务确认。
4. 提示发布：错误归因→改提示候选→冻结评测集回放→历史时间切分评测→影子运行→有限灰度→版本发布/回滚。不能让 agent 在生产自行改全局 system prompt。
5. 统计模型：有足够可比样本后预测工时/实际损耗/成交概率/毛利偏差，带不确定性；作为建议输入，正式公式/审批约束不变。低价提高成交但降低利润属于多目标权衡；观测结果受客户质量、销售选择、金价、季节性等混杂，不直接当因果收益。
6. 微调：只有任务稳定、数据许可、标注充足、检索和提示已暴露明确上限时考虑；新金价/新合同不靠微调记住，应从受控事实工具查询。

抗反馈污染：不可信邮件/附件是待分析数据，不能变成系统指令；模型输出不能自证事实；一条反馈不能全局改策略；按角色决定能确认什么；持久记忆写入做来源校验、scope 检查、敏感性检查、冲突与重复检测。样本复制/多次点赞不能堆高可信度。管理员须能看到“为什么记住”、纠正/撤回、查看受影响建议。

上线验收应有：可比案例命中率、事实/口径错误率、无依据建议率、人工改动原因、审批用时、异常漏检/误报、敏感数据越权、记忆过期/撤回测试、报价毛利偏差、成交与回款结果。分客户/工艺/结算方式看，不只看平均满意度。时间切分避免用未来实际结果评价过去建议形成泄漏。

搜索记录（原始文件均在 .firecrawl/20261016-qmemory-*）：
- Google 搜索 LangGraph long term memory namespaces store、LangMem semantic episodic procedural memory、Graphiti temporal knowledge graph memory：均返回验证/重定向脚本，无法取得可靠结果。
- Bing 搜索 LangGraph memory store namespaces、LangMem procedural prompt optimization、Graphiti bi temporal facts：结果均明显不相关（彩票、汽车、Canvas），未作为证据。
- 改为直接读取官方文档/开源官方 README；成功读取七页，正文采用六页（LangGraph memory/persistence、LangMem concepts/background、Mem0 add、Graphiti README）。Letta /guides/agents/memory/ 返回偏概念导航页，未作为核心证据。
- Firecrawl latest 的损坏依赖问题由主研究者已确认，本子任务按授权采用只读 HTTP fallback，没有修复环境、传输业务资料或调用供应商写入 API。

### Gaps
- 未检索到能直接证明珠宝企业在线记忆提升毛利的可信研究；建议为工程设计推导，不能承诺提升百分比。
- 当前样本量未知，因此不能给出最小样本数、精确训练周期或收益估计。
