# 企业知识库与分析 Agent：可信取数、业务语义与证据驱动的判断

## 1. 为什么普通 RAG 不足以让企业 Agent 具有分析与判断能力？

### Takeaway
应构建“文档检索 + 受治理的业务指标查询 + 可复现计算 + 假设检验”的双通道或多工具系统。知识库检索负责制度、合同、背景和证据；语义层和数据库负责口径一致的数字；LLM 负责澄清问题、选择分析方法、结合证据解释与提出有条件的行动。

### Cited Findings
- **已实读：Introducing Contextual Retrieval（Anthropic，2024-09-19）**。传统 chunk 可能只剩“公司收入增长 3%”，失去公司与季度，因而检索或解释错误。其方法是在建立 embedding 和 BM25 前为每个片段添加约 50–100 tokens 的片段特定上下文；BM25 对错误码、专有标识等精确词匹配有优势，向量匹配补充语义关系。其特定实验的 top-20 检索失败率由 5.7% 降到 2.9%；加入 reranking 后为 1.9%，相对下降 67%。这不是企业最终回答准确率，也不是可以直接外推的统一提升。reranking 增加运行时延迟和成本，应按自有数据测试。— [原文](https://www.anthropic.com/news/contextual-retrieval)
- **已实读：Cortex Agents（Snowflake）**。官方架构将 Cortex Analyst 的结构化 semantic views/SQL 与 Cortex Search 的非结构化检索汇合，并可用隔离 Python 工具处理数据。Agent 循环为 Plan → Use tools → Reflect and respond，能澄清歧义、拆任务、选工具、检查中间结果后决定继续查或回答。官方明确 LLM 答案和引用的准确性并无保证，仍需审查。— [原文](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)
- **已实读：Security filters for trimming results in Azure AI Search（Microsoft Learn）**。文档级裁剪可在索引存 principal/group IDs，每次查询由可信服务端应用身份过滤。该 pattern 自身只是字符串过滤，不负责身份认证；retrievable=false 也不等同权限控制。— [原文](https://learn.microsoft.com/en-us/azure/search/search-security-trimming-for-azure-search)
- **已实读：Welcome to GraphRAG（Microsoft）**。GraphRAG 从文本抽实体、关系、claims，聚类成社区并生成社区摘要；Global Search 面向整个语料的主题性问题，Local Search 面向特定实体及其邻居，DRIFT 结合局部和社区信息，Basic Search 保留普通向量检索。适用弱点是跨材料连接事实和大语料全局综合。— [原文](https://microsoft.github.io/graphrag/)
- **已实读：GraphRAG README（Microsoft）**。官方明确索引可能昂贵，建议小规模开始；代码是研究演示，不是正式支持的微软产品。研究时 README 还写有 largely in maintenance mode。架构上可借鉴图检索，不应把此仓库当所有企业系统的必需依赖。— [README](https://github.com/microsoft/graphrag/blob/main/README.md)

### Inferences
- **必须有**：混合检索、重排评估、原始证据定位、权限过滤、结构化指标查询、计算与取数校验。**按需有**：GraphRAG/知识图谱；仅在供应商—合同—发票—付款、客户—订单—投诉等跨实体和多跳问题明显时上图。LLM 从文本抽出的关系也要保留原文及置信状态，不能自动成为权威事实。
- 建议 chunk 元数据包含 document_id、version、effective_from/effective_to、published_at、ingested_at、组织范围、ACL、source URL/page/section；回答“当时适用何种制度”必须用生效时间，不能用“最近入库”代替。这个完整元数据方案是本研究的设计推论，并非上述某一产品文档的现成功能清单。
- 文档与数据遇到冲突时，应指出冲突：制度可解释“应怎样”，账务或业务系统反映“实际记录怎样”，二者不能混为同一种事实。
- 真正像会思考的表现是：用户问“为什么利润下降”，Agent 先确定利润口径、期间与基准，再查询数字，检查数据有效性，提出能被数据证伪的解释，最后明确已知、推断和待验证。不能靠把检索片段写成一段自信的原因分析。

### Gaps
- 上述厂商资料说明技术模式，不能证明某一个组合在本企业里提高多少业务收益；必须有企业自己的代表性问题和标准答案。
- 没找到证明 GraphRAG 普遍优于混合 RAG、或能直接解决财务数值正确性的证据；不做此推断。

## 2. 业务语义层、可信 SQL 与数据质量如何具体落地？

### Takeaway
优先建设“业务定义 + 指标计算 + 关系与粒度 + 经审核的问题—SQL 样例”，不应让模型直接对全部原始表即兴猜测。提示词只能调用业务规则，业务规则本身需要成为可治理、可测试、可版本化的数据资产。

### Cited Findings
- **已实读：Tune Genie Agent quality（Databricks，页面显示更新于 2026-10-09）**。Knowledge store 包含表列描述、业务术语和同义词、列值匹配、join 关系、SQL expressions（measures、filters、dimensions），指导具体 SQL 语义。文档强调清除指导中的冲突与歧义，并将全局文本说明限制在真正全局适用的内容，局部规则放在对应示例、函数、表注释或元数据。— [原文](https://docs.databricks.com/aws/en/genie/knowledge-store)
- **同一文档的具体例子**：“Florida” 对应库中的“FL”，如果没有实体值映射，SQL 可能生成 ILIKE '%Florida%' 而查不到结果。Join 类型可定义 many-to-one、one-to-many、one-to-one，帮助模型选正确连接。隐藏列只移除模型上下文，不改变底层表权限。— [原文](https://docs.databricks.com/aws/en/genie/knowledge-store)
- **同一文档的 trusted 范围**：可信资产包括参数化 SQL 样例和 Unity Catalog 注册 SQL 函数；chat 模式必须原样使用参数化查询文本才能标记 verified。SQL 函数可封装复杂逻辑，模型看不到也不能修改函数内部 SQL。这里 verified 不能解读为“AI 所有陈述都被证明正确”，也不意味着原始数据无误。— [原文](https://docs.databricks.com/aws/en/genie/knowledge-store)
- **已实读：Overview of semantic views（Snowflake，旧 semantic-model-spec 链接实际返回此页）**。Semantic view 是数据库 schema 级对象，定义 business entities、relationships、facts、metrics、dimensions。文档以 gross revenue 对应 amt_ttl_pre_dsc、net revenue = SUM(gross_revenue * (1-discount)) 说明业务词与物理字段脱节、聚合口径不一致的问题。目前 Cortex Agents 读 semantic view 定义后直接向物理表生成 SQL，因此不能推断“使用 semantic view 后任意生成 SQL 都形式化地保证正确”。— [读取入口](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec)
- **已实读：Cortex Analyst Verified Query Repository（Snowflake）**。VQR 保存自然语言问题与对应 SQL，遇相似问题时为生成 SQL 提供参考；样例可带 verified_at、verified_by。文档明确需要人工检查 SQL 和结果、修正重跑后保存；不正确的 verified query 会降低模型表现。可在 API 的 confidence 字段检查使用了哪条参考查询，这不是自动校准的最终答案正确概率。— [原文](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/verified-query-repository)
- **已实读：dbt Semantic Layer（dbt）**。MetricFlow 支持在 dbt modeling 层集中定义指标、自动处理数据 join，减少各 BI/工具重复编写业务逻辑；AI 可经 dbt MCP server 查询受治理指标。托管 Semantic Layer 有账户版本与接入限制，应按企业现有栈选用。— [原文](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)
- **已实读：Add data tests to your DAG（dbt）**。data tests 是对模型、source、seed、snapshot 的断言；开箱包含 unique、not_null、accepted_values、relationships。自定义 SQL 查询返回失败行，以断言核对结果，例如汇总支付金额不应为负。— [原文](https://docs.getdbt.com/docs/build/data-tests)
- **已实读：Source freshness（dbt）**。freshness 检查验证数据更新是否满足组织 SLA；dbt build 默认不包括 source freshness，需单独配置 dbt source freshness。作为显式前置 job step 时可在过期后阻断后续步骤，单纯勾选 freshness 的行为不等于阻断。— [原文](https://docs.getdbt.com/docs/deploy/source-freshness)

### Inferences
- **最小指标契约**：metric_id、业务名称与同义词、负责人、公式、统计粒度、允许维度、分母/去重规则、币种与汇率、含税/未税、订单/发货/开票/确认收入时间、会计期间、是否已关账、排除项、版本。这比“你是资深财务专家”更能决定答案是否可信。
- 例如“利润下降”的分析需区分毛利额、毛利率、营业利润、净利润；“收入”需区分合同额、订单额、开票额、确认收入、到账现金。Agent 应先按当前上下文选择已批准默认口径，在决定会改变结论时追问；不必每次都重复问已知信息。
- 查询路径建议优先“调用已审核指标 API/参数化分析函数”，其次“引用已审核 SQL 并受限改写”，最后才是“在已批准语义域内生成新 SQL”。后两者要检查 SQL 语法/权限/资源预算、join 结果粒度、重复计数、空值、时间边界、汇总核对。
- 关键校验：总分一致、同比期间可比、未满月不能直接对整月、货币一致、join 前后记录量与唯一键检查、账务与报表对账、数据 freshness。若缺数或同步失败，先输出“数据不足以归因”，不要编原因。
- “能执行”不等于“逻辑正确”；“SQL 对”不等于“源数据对”；“指标对”也不等于“建议对”。应分别记录证据和失败状态。
- 限制模型的业务上下文并不是削弱智能，而是让其把推理用在正确的业务定义之上。组织术语、口径与指标公式应由元数据服务按域动态注入，而不是堆入一个永久增长的大提示词。

### Gaps
- 没找到可泛化为所有企业的最优 SQL 置信度阈值；不能把模型自报的 90% 当验收。
- 不同产品对权限继承、采样值共享、缓存隔离有细节差异；需针对真实连接方式测。尤其 Databricks 文档明确部分提示匹配值来自作者权限并进入共享上下文，不能只检查 SQL 行权限而忽略元数据泄漏。

## 3. 如何从“给出数字”发展到诊断、建议与可验证的行动？

### Takeaway
应该把分析工作设计成“目标与约束 → 数据检查 → 现象与驱动拆解 → 竞争解释与反证 → 决策选项 → 验证计划”。会提出假设、承认不确定性、主动补查关键证据，比展示一长段思维链更有价值。

### Cited Findings
- **已实读：Estimating Causal Effects（PyWhy/DoWhy）**。因果效应估计有四步：以假设构造 causal model、identify 可识别的 estimand、estimate、refute 做鲁棒性检验。文档强调先判断效应是否能从现有数据识别，再选择估计算法；可使用 backdoor、frontdoor、IV、ID 等识别策略。— [原文](https://www.pywhy.org/dowhy/v0.13/user_guide/causal_tasks/estimating_causal_effects/index.html)
- **Cortex Agents 的循环提供系统模式**：对每次工具结果评估是否需要澄清、继续查询或回答，而不是一次生成最终结论。成本不止 LLM token，还包括数据仓库计算、检索索引、自定义工具等，可设置 orchestration budget、resource budgets、per-user quotas。— [原文](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents)

### Inferences
- 财务诊断例子：确认毛利率下降后，先按产品、地区、客户、渠道拆分；用量价成本/组合变化分解定位贡献；结合折扣审批、采购成本、退货和合同等证据；同时排查币种、重分类、坏数据与一次性费用。分解解释“哪些项目贡献变化”，不自动证明“为何变化”。
- 可让 Agent 维护一张假设表：假设、支持证据、反对证据、缺失数据、下一次最有价值的查询、结论状态。对用户呈现的是这类可核查研究摘要，不是声称完整展示内部思维。
- 建议必须写条件：动作、适用范围、预期机制、成本、对现金流/收入/风险的权衡、证据、负责人、验证方式。没有因果识别时可给“可测试方案”，不要把情景估算包装成必然收益。
- “降价 5% 会怎样”有不同层级：纯算术情景保持销量等其他条件固定；预测需要需求模型和预测区间；因果决策需实验/准实验或明确可辩护的识别假设。Agent 必须区分这三者。
- 基础分析工具按场景选择：SQL 指标和 Python 计算必须可重现；统计检验报告样本、基准和区间；预测检查回测与泄漏；异常检测区分季节性、趋势与结构变化；财务情景使用资产负债、利润、现金流的勾稽约束。
- 最小可用平台不必开始就上多 Agent：一个能路由已审核 SQL、文档检索、Python 与业务规则的 Agent 足以覆盖多数初始任务。只有任务独立、并行收益明确、结果能汇总且有人评估时再拆 Agent。
- 推荐业务能力验收问题：同一口径是否稳定；含糊问题是否正确澄清；跨表是否避免重复计数；过期数据是否停止归因；结论能否追溯源记录；证据矛盾时是否呈现；建议是否带前提与可验证后续动作；权限是否贯穿检索、SQL、缓存、日志。

### Gaps
- 没有足够依据承诺“Agent 自主形成商业策略”一定超越有经验的经理。应先让它在具体业务决策上做到可验证、可纠错、可追踪。
- 公开搜索记录：已请求 Google 查询 enterprise text to SQL semantic layer verified queries ambiguity，页面要求跳转；DuckDuckGo 查询 Cortex Analyst semantic model ambiguous verified queries 遇反自动化挑战；Bing 两次同主题搜索返回不相关的 Cortex/Snowflake 泛词结果。未把这些命中用作事实依据，以上结论均来自实际完整读取的一手技术页面。查询/命中保存在 `.firecrawl/20261016-analytics-search*.txt`；所有正文缓存为 `.firecrawl/20261016-analytics-*.txt`。研究日期：2026-10-16。
