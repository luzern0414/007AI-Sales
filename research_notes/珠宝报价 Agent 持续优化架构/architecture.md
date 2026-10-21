# 010ERP 报价 Agent 持续优化：实现架构与运行机制

## 1. 现有基础能保留什么，需要新增什么？

### Takeaway
采用现有 FastAPI/SQLAlchemy/Vue 模块化单体，保留业务系统权威状态与确定性报价核算，旁路增加决策记录、反馈和记忆投影。记忆、语义检索与模型分析是可重建的辅助层，不是新的正式账务/报价事实源。

### Cited Findings
- 已实际读取本地 README、docs/14、quotes/models.py、service.py、calculation.py、platform/service.py。项目开发默认 SQLite，生产拟 PostgreSQL 且尚未验证；docs/14 选择模块化单体、不引入 Redis/Kafka/Kubernetes，并保留数据库任务队列。引用本地：[架构对照](D:/Codes/010ERP/docs/14-一期架构与客户修订对照.md)。
- 当前 Quote 有主体、款式、材质、件重成色、金额、version、rule_snapshot、formula_trace、history_comparison、risk_flags、审核及说明字段；没有客户/集团/渠道、贸易条款、订单、实际成本、成交结果。update_quote 会清空旧计算和对比结果，没有不可变业务修订历史。服务按同主体、款式、材质最近一笔已审总价比较，变化可能受件重成色影响。引用本地：[报价模型](D:/Codes/010ERP/backend/app/finance/quotes/models.py)、[报价服务](D:/Codes/010ERP/backend/app/finance/quotes/service.py)。
- 金价、损耗、工费、毛利率由 RuleVersion 提供；Decimal 纯计算；审批后冻结；职责分离；claim_version 使用数据库条件更新检查版本和状态。引用本地：[计算](D:/Codes/010ERP/backend/app/finance/quotes/calculation.py)、[基础服务](D:/Codes/010ERP/backend/app/finance/platform/service.py)。
- docs/14 明确“敏感工资、报价不进入模型”“开发默认关闭外部识别”，原型没有上线。任何模型/embedding/观测服务接入均属未来方案，需要明确允许字段、部署与传输边界，当前不能把敏感报价直接传云端。引用本地：[架构对照](D:/Codes/010ERP/docs/14-一期架构与客户修订对照.md)。
- Azure CQRS 文档说明可将读写模型分开；消息并非 CQRS 必需；分别存储时须处理读模型陈旧、最终一致性，结合 event sourcing 会提高复杂度。[CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)。
- Azure 强调 Event Sourcing 在存储、并发、模式演进、查询和迁移上带来重大取舍；多数系统传统数据管理即可。[Event Sourcing](https://learn.microsoft.com/en-us/azure/architecture/patterns/event-sourcing)。

### Inferences
- 不是把硬编码替换为模型自由定价，而是分离三类可变性：①客户批准的正式核算规则，版本化生效；②Agent 可优化的检索、类比、补问、风险解释、方案排序；③统计估计的工时/损耗/成交倾向，经过验证作为建议输入。任何②③都不自动改①。
- 增加 QuoteRevision 不可变业务快照，包含当时输入、规则、成本与标准化特征、计算、用户目标、关联证据与数据版本；Quote 保持当前索引和状态。每次正式修改创建新修订，不覆盖旧修订。
- 增加 DecisionRecord：推荐方案、已知事实/假设、证据ID、参考案例及版本、估计与区间、替代方案、Agent版本包、人工选项与原因、quote_revision_id。保存可核查的决策依据，不采集/展示模型隐藏思维链。
- 增加 FeedbackEvent 与 OutcomeObservation：记录反馈者角色权限、修订前后差异、原因码与说明；结局分别记录是否采纳、获批、报出、客户回应、订单、实际工时/损耗、交付、回款。允许 unknown/pending，未成交不一定因为价格，成交不等于高利润。
- 增加 MemoryItem、MemoryEvidence、MemoryVersion、MemoryUse：语义内容与结构化条件、来源、角色/主体可见范围、适用产品客户、有效期、状态、冲突关系、支持/反对样本、人工确认、替换关系；MemoryUse 关联使用过该记忆的决策，便于纠错追踪。
- 物理上优先同一 PostgreSQL：正式业务表、Agent运行/反馈/记忆/事件表、FTS及可选pgvector；文件仍在现有存储。采用读模型思想，不必独立读库，更不必全量事件溯源。

### Gaps
- 尚无客户真实计价政策、生产数据与结果追踪；不能给出报价准确率、获利提升比例或数据量结论。

## 2. 一次报价和一次反馈怎样可靠流转？

### Takeaway
在线负责基于当前证据提供建议；离线将反馈变为候选经验，经核验与评估后发布。业务事务和分析/记忆任务通过事务 outbox 解耦，模型超时或服务故障不影响报价原有计算与审批。

### Cited Findings
- Azure Transactional Outbox 说明将业务对象与事件原子保存，后台转发；重复处理需要依赖事件ID等去重机制。文章实现使用 Cosmos DB/Service Bus，此项目只借鉴原子写业务与事件的模式，不采用其云产品。[Transactional Outbox](https://learn.microsoft.com/en-us/azure/architecture/databases/guide/transactional-out-box-cosmos)。
- LangGraph Interrupts 实际页面说明中断时通过持久层保存状态，等待外部输入；恢复从节点重新执行，因此中断前的副作用必须幂等或移至独立节点；thread_id 关联已保存状态。[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。
- LangGraph Persistence 实际正文说明内存 checkpointer 随进程重启丢失，生产应使用持久 checkpointer；需控制检查点增长。[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。注意原 durable-execution URL 重定向至 persistence，不能用旧路径假称读到了独立的 durable execution 正文。
- LangGraph Fault tolerance 正文提供节点重试、超时和错误处理机制，重试适合短暂故障；具体功能与版本要求以锁定版本文档为准。[Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)。

### Inferences
- 在线流程：授权→冻结本次 QuoteRevision 与数据版本→确定性成本计算→按主体/日期/政策硬过滤历史和记忆→检索可比案例→程序归一化、差价分解与情景计算→Agent补问/解释/方案比较→结构化输出校验→用户选择或审核。正式发送/审核依旧调用业务服务。
- 每个 AgentRun 保存 run_id、quote_revision_id、用户及授权范围、状态、目标、步骤、工具参数与结果引用、检查点、累计token/费用、超时预算。审批等待与业务单据状态分开；恢复后重新核验授权、单据版本、金价有效期和规则，过期则重算，而非机械执行旧建议。
- 模型输出不能直接写金额/规则/审批状态；工具是 get_quote_evidence、find_comparable_quotes、calculate_scenarios、create_analysis_draft 等窄业务接口。执行动作必须重新经过状态机、职责分离、数据库版本与幂等检查。
- 用户改了建议，业务服务同一事务写 QuoteRevision/FeedbackEvent/OutboxEvent；worker领取event_id→校验来源/权限→归因分类→生成候选记忆→冲突/重复/过期检查→按风险自动局部入库或进入人审→发布 MemoryVersion→更新检索投影。避免“业务提交成功但反馈丢失”以及“分析成功导致业务事务长时间占锁”。
- 至少一次投递＋消费者去重，不承诺跨模型调用和数据库的全局 exactly-once。唯一键可用 consumer_name+event_id；任务执行有租约/心跳/attempt、指数退避、失败隔离、人工重放。同一报价事件按 aggregate revision 排序，旧投影更新不得覆盖新修订。发布成功但ack失败重跑也不能重复晋升记忆。
- 记忆生产状态建议 candidate→validated→active→superseded/expired/rejected；用户直接明确的个人显示偏好可立即在私有范围保存，跨客户/全公司方法与正式政策必须经过更高等级核验。用户批准仅是反馈信号，不是价格正确标签。
- 不必一开始引入 LangGraph：当前数据库队列和明确状态机可实现首版。若调查分支、补问、跨天审批与恢复复杂，再采用 LangGraph Postgres checkpointer；由应用业务服务负责真实动作。Temporal更适合已有长时跨系统工作流需求，此项目初期不增运维负担。

### Gaps
- 未验证项目现有worker的多实例、长期租约、outbox语义，不能认定这些能力已实现；生产数据库、队列恢复与重复事件须专门验收。

## 3. 检索、版本、观测与持续发布如何组成最小平台？

### Takeaway
最小平台是业务数据库＋版本化案例/记忆＋可恢复任务＋离线评估＋受控发布。不要把向量数据库或一个“反思Agent”当成持续变好的充分条件；每个变化应可测量、限定范围、撤回，并追踪其影响。

### Cited Findings
- pgvector README 说明默认精确近邻检索；近似索引交换召回率和速度；WHERE过滤在近似索引扫描后执行，可能导致返回不足，可用 iterative scans、部分索引或分区改善；共享近似索引还可能使一租户影响另一租户召回和速度。[pgvector 官方 README](https://github.com/pgvector/pgvector#filtering)。
- CQRS 文档说明使用读模型时必须考虑数据滞后和用户基于陈旧读数据行动的风险。[CQRS](https://learn.microsoft.com/en-us/azure/architecture/patterns/cqrs)。
- LangGraph Persistence 明确建议清理旧检查点或设置保留策略。[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。

### Inferences
- 检索顺序是权限与适用域硬过滤→款式/材质/工艺/成色/结算/数量区间等结构化可比过滤→全文/向量候选→标准化价格/工时/损耗特征重排→新鲜度、证据质量、结果与冲突检查。相似文字不能凌驾于计价方式不同；语义分数不是置信概率。
- 先用SQL条件和全文检索；中文全文需要适配分词/搜索配置并通过真实查询评估。必要时加入pgvector，用精确搜索先建立召回基线；有数据规模和延迟证据再上HNSW。权限必须在服务端查询/存储隔离落实，不能先取全公司敏感内容再让模型过滤。
- 金价、客户信用、一次性促销等设短有效期和场景；通用工艺经验亦需监测工艺/供应商/设备变化。例外单据只作为例外证据，不能形成“该客户以后都可低毛利”的长期政策。
- AgentReleaseBundle 统一绑定模型、system prompt、工作流/工具schema、语义定义、检索/重排参数、memory snapshot、估计模型、规则引用与评估集版本；追踪具体本次读取版本。记忆持续更新也会改变表现，必须可定位版本和撤回单条记忆。正式规则与记忆分开审批。
- 观测关联 request_id、run_id、quote_revision、decision_id、feedback/outcome、memory ids；指标包括数据缺失、检索命中/误用、计算差异、无依据断言、权限违规、工具错误、超时/成本、人工修改原因、错误风险提醒、成交/利润/回款的延迟结果。敏感原文默认不写第三方trace。
- 离线基线采用时间切分和客户/款式分组，回放仅允许决策当时可知资料，避免将后来的成交/实际成本当作当时报价输入。固定回归集含正确建议、无可比案例、相互冲突反馈、过期例外、主体隔离、金价改变、审批中改价、重复事件与故障恢复。
- 发布顺序：无记忆基线→离线回放→影子模式→限定主体/用户灰度→业务与质量门槛→发布；允许按记忆、prompt、检索器或估计模型单独回滚。对客户价格探索须业务批准，初期不做自动随机报价实验或强化学习自动降价。
- 分期：A数据与反馈闭环（补客户/订单关联、修订、决策、原因码、结局、基线）；B受控案例记忆（检索+证据+人审+过期+撤回）；C自适应分析（策略排序、澄清、损耗工时估计，离线评估）；D数据充分后监督训练/排序优化，仍不自动覆盖政策底线。时间估算需团队和数据评估，不凭空承诺几周上线。
- 最重要的可见改善：相同信息不再重复问；更能找到真正可比案例；对新情况少武断；对本客户确认的偏好记得准确；能说明为什么此次例外不适用；人工改动与返工下降。缺资料时更克制也是进步。

### Gaps
- 未能从实际业务样本估计每类case数量和反馈延迟，当前不建议直接fine-tuning/RL；未核验模型私有部署容量和客户允许数据边界；OTel GenAI页抓取仅导航，未用作规范细节证据。
