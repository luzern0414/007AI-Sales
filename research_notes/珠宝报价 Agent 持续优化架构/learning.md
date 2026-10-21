# 珠宝报价与企业 Agent 的反馈学习、评估和发布架构

## 哪些能力可以持续优化，以及可采用什么技术？

### Takeaway
先优化业务记忆、可比案例检索、信息补查方法和分析表达，再在数据成熟时训练成本偏差、损耗、交付与信用等监督模型。权威计价公式与政策版本仍由业务负责人控制；学习系统提出候选改进并经过评估发布，不让线上模型直接改正式价格规则。

### Cited Findings
- DSPy MIPROv2 同时搜索 instructions 与 few-shot examples，以业务指定 metric 在验证集上做 Bayesian Optimization；它优化的是语言模型程序的提示和示例组合，并不是企业收入或报价成功的自动保证。— [MIPROv2 官方文档，已全文读取](https://dspy.ai/current/api/optimizers/MIPROv2/)
- DSPy GEPA 可利用 scalar score 和 domain-specific textual feedback 演化文本组件；反馈可绑定 predictor 的子轨迹。因此“错在选了不可比历史，遗漏账期差异”比单一差评更有优化信息。文档的性能叙述属于框架方陈述，未在本企业验证。— [GEPA 官方文档，已全文读取](https://dspy.ai/current/api/optimizers/GEPA/overview/)
- LangSmith 支持对 root trace 或 child run 附加用户、标注员和自动评价反馈；具体到 retrieval 或 generation 阶段，能定位问题。— [Log user feedback](https://docs.langchain.com/langsmith/attach-user-feedback)
- LangSmith 区分 offline evaluation（有策划数据集和参考答案，可做回归与历史回放）与 online evaluation（生产 traces，通常没有标准答案）。生产问题进入离线集，离线修复再上线验证，是其文档描述的持续改进循环。— [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- Langfuse 支持 prompt version ID 和 staging/production/tenant/experiment 等 labels；回滚可以把 production 指回旧版。受保护 label 的权限功能有版本/付费层限制，不应误认为所有自托管版本均具备。— [Prompt version control](https://langfuse.com/docs/prompt-management/features/prompt-version-control)
- Langfuse Dataset 可从生产 observation 生成评估样本，关联 source trace；支持按时间戳读取 dataset version，在相同版本上跑实验。其版本化针对 dataset items，不涵盖 schema，schema 也需另行版本管理。— [Datasets，实际 URL 重定向内容已读取](https://langfuse.com/docs/evaluation/experiments/overview)
- MLflow registry 支持 lineage、模型版本、tags、annotations 与 aliases；champion alias 可指向生产模型版本。开源与托管平台治理能力有差别，不能仅部署 OSS 就宣称已有全套 RBAC。— [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/)

### Inferences
- 推荐三条相互独立的改进通道：①业务事实/案例记忆更新，②提示、检索、工具编排与方法版本更新，③数值预测模型更新。出错先归因，不能把所有问题都归为“模型不够聪明”。
- 数据输入错→修正实体/字段且追溯影响；不可比历史→修检索过滤与排序；缺检查项→修方法与提示；算术/口径错→修业务服务与公式版本；人工特批→保留有范围的一次性例外；真实成本长期偏差→候选监督模型或规则参数调整。这些是架构建议，非框架自动提供。
- 每次报价保存 DecisionRecord：quote/opportunity/subject/customer IDs；当时事实快照；rule+gold price+cost basis+prompt+retriever+tool+model+memory snapshot 版本；候选与已选方案；证据、假设、主要风险；建议、人工修改前后与理由；审批及执行结果。记录简明依据和工具轨迹，无需保存模型隐性思维链。
- 反馈 taxonomy：事实错误、选错可比案例、遗漏业务条件、公式口径问题、解释不清、建议不可执行、政策例外、客户条件变化。FeedbackEvent 绑定具体字段/引用/工具步骤，记录作者角色、时间、修正值、理由、适用范围、是否复核。点赞仅为体验信号，不直接成为“正确答案”。
- 近期专家反馈可先进入待审候选记忆；经角色核实后成为客户或工艺范围的案例。重复、高质量且无冲突经验可提出方法变更；不能靠出现次数自动晋升正式政策。
- 数据量小时先直接 A/B 离线比较 prompts/retrieval 设置；有良好标注与 metric 后才引入 MIPROv2/GEPA。可优化任务是“是否找到了真正可比案例”“是否发现需要补问的金料结算条件”“解释是否有证据”，而非把成交率作为 LLM 文本单一奖励。优化只生成 candidate，禁止直接移动生产标签。
- Langfuse 与 LangSmith 二选一即可，前者可作为自托管候选；数值模型出现后再增加 MLflow。当前项目规模可用 PostgreSQL + 对象存储 + 异步 worker 与观测平台，不必一开始引入完整 feature store、流平台和模型集群。
- 当前 ERP 敏感报价与工资“不进模型”的限制仍然有效：本次研究仅访问公开网页，不上传业务数据。以上是满足后续数据使用边界后的设计；现阶段可先记录本地反馈、做确定性标准化比较、建立脱敏/合成评估。

### Gaps
- 没有该企业可用成交、成本、回款样本量、字段完整度及权限边界证据，不能承诺模型收益、上线时长或通用通过阈值。
- GEPA 当前文档包含 Python 3.15 环境限制；实施时应锁定并验证依赖版本，不能直接照抄 latest 代码。

## 怎样接收延迟业务结果，避免越学越偏？

### Takeaway
报价被接受、生成订单、交付实现毛利、最终回款是不同结果。必须保存全漏斗、时间和报价修订关系，避免把人工批准当商业成功、把无回应当输单、把过去低价成交当降价必然有效。

### Cited Findings
- scikit-learn 官方文档指出时间相关数据应采用 time-series-aware 划分，存在组结构的数据应使用 group-wise 划分；同时强调独立测试集和防止对测试集反复优化。— [Cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html)
- Feast 的 point-in-time join 可重现过去时点的 features；文档进一步指出仅约束 event timestamp 不足，晚补录或修正值仍可能泄漏，应考虑 created_timestamp/当时可用时间过滤。相关 flag 尚非所有 store 支持。— [Point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)
- 分类概率可能未经校准；校准应使用独立于原训练数据的样本。可靠性曲线比较预测概率与实际频率；Brier/log loss 同时受校准和区分能力等因素影响，低 Brier 不单独证明更好校准。— [Probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- DoWhy 将因果推断分为明确假设、识别、估计、反驳/稳健性检验，先判断能否从现有数据识别因果效应再选算法。不是仅回归就可推断提价效果。— [Estimating Causal Effects](https://www.pywhy.org/dowhy/v0.13/user_guide/causal_tasks/estimating_causal_effects/index.html)

### Inferences
- 事件链：报价草案→提交→人工修订→审批→对外发送→谈判/再次报价→明确接受/明确拒绝/待跟进/过期未知→订单→交付/返工/退货→成本结转→发票→到账/逾期/坏账。每个阶段独立状态，迟到事件追加且可追溯更正。
- opportunity_id 把同一商业机会的多轮报价归组；不能每次降价都当独立试验，也不能让同机会版本同时进入训练和测试。按时间向前验证，另设客户/款式留出，判断新客户/新品泛化。预处理与近邻示例选择只能用训练时期可见的数据。
- 保存金价来源、取价时点、币种、成色、重量、结算方式、是否锁价、损耗、工费、账期、交付条件和政策生效版本。历史报价按同口径拆分料价/工费/条款，不直接比较总价；“重放当时决策”与“按今天成本模拟历史方案”是两个实验，不混为一谈。
- 特征必须同时考虑业务有效时间 valid_time 与系统当时已知时间 recorded/available_at；今天才更正的历史成本不能被塞回当时报价上下文，结果 label 可以后到。
- 未回复/未追踪不是确定输单；未交付不是零成本；未回款且尚未到期不是坏账。维护 label 状态、成熟日和观察窗，未成熟样本不强行贴负标签。
- 人工采纳率受权威、界面默认、人员习惯影响；高采纳不证明有效。销售选择哪些客户报价、何时降价、哪些成交被完整录入，也会造成选择偏差。记录丢单、撤回、未回复和未生成报价的可用机会范围；缺失与偏差无法靠事后字段彻底消除。
- 可以先训练实际工费/损耗偏差、返工风险、交付延迟和逾期概率等独立监督模型，有概率输出时校准并按细分市场检查。不要让 LLM 直接声称“成交概率 83%”。
- 一个历史预测模型估计的是既有销售策略下的关联分布，不能直接成为所有候选价格的反事实需求曲线。定价因果仍需明确假设或经业务授权的研究；初期不做随机对客试价或自动在线探索。
- 目标为约束下的风险调整贡献、资金与客户关系：利润底线、授信、报价一致性、产能和交付约束先满足，再比较方案。金料可能转售或客户来料，名义收入大不代表经营贡献高，采用客户确认的会计与经营口径。不能只最大化 win rate：持续降工费可能提高成交率但恶化真实贡献和回款。
- 长期结果用于评价建议组合，不将每笔利润变化全部归因 Agent；金价、客户结构、季节、销售人员、产能变化都可能影响指标。

### Gaps
- 无法从公开工具资料证明 010ERP 的报价提高利润因果效果；需企业基线和严谨评估设计。
- 通用 point-in-time 技术不能自动补齐该项目缺失的早期录入时间和历史快照。

## 怎样从上线反馈走向受控发布和回滚？

### Takeaway
采用双闭环：线上系统完成任务并收集事实、修正与结果；离线学习系统形成候选版本，经过回放、影子、有限上线和结果复查再晋升。回滚要覆盖整个 Agent 策略包及有问题的记忆，不仅切换基础模型。

### Cited Findings
- LangSmith 文档明确可对具体组件评价，实验保留每个例子的输出、评分和轨迹；离线与在线评估作用不同。— [Evaluation concepts](https://docs.langchain.com/langsmith/evaluation-concepts)
- Langfuse 能按既定数据集版本复现实验和通过 labels 切换提示版本；它提供机制而非业务发布审批和利润验收本身。— [Datasets](https://langfuse.com/docs/evaluation/experiments/overview)；[Prompt version control](https://langfuse.com/docs/prompt-management/features/prompt-version-control)
- MLflow 模型 aliases 支持受控切换生产版本，但完整业务执行、审批、事件一致性仍需应用实现。— [Model Registry](https://mlflow.org/docs/latest/ml/model-registry/)

### Inferences
- 架构：业务交易服务→事务 outbox→反馈/结果异步投影→候选记忆与标注队列→版本化训练/评估集→候选提示/检索/工具/模型→离线 replay→shadow→有限角色/主体/场景 rollout→监控→晋升/回滚。对于现有模块化单体，outbox + worker 足够，不必立即引 Kafka。
- 回放：冻结当时可见资料、工具 fixture、权限、规则、候选记忆集，测试过期金价、客户来料、异主体数据、特批、工艺变更、重复报价、缺证据、不该给建议等案例。数值和权限由程序校验；领域专家盲审；LLM judge 可辅助找问题，不能独自裁定财务正确性。
- 影子：候选读相同授权请求但不展示、不写业务、不发客户、不改变价格；比较检索、证据、建议、时延、成本，并注意额外读取本身也必须符合权限。
- 有限上线：先内部分析建议，不自动发价；以机会或用户/团队为分配单元防止同机会来回穿透多版本。控制客户/产品和金价时期差异；保留业务人员负责决策。不必也不应为了技术 A/B 随机对客户改变价格。
- 发布物 AgentRelease 包含 model/prompt/retriever/tool schema/method/policy binding/embedding+index/data contract 版本、memory epoch、eval dataset+evaluator 版本、权限和数据边界。执行交易前再次验证当前单据版本、权限、有效报价政策和金价，重放复现不意味着允许使用过期报价。
- 热更新记忆应有发布流水和 lineage。错误记忆撤销后停用检索、清缓存，追溯受影响分析并标记过期；恢复旧 release 不能恢复已撤销权限、被删除证据和错误记忆。
- 分四组指标：①确定性正确性/金额口径/权限/重复执行；②检索可比性、证据覆盖、缺证据拒判、人工修正率；③审阅工时、出价耗时、补证轮次、延迟成本；④机会成交、交付实贡献、返工退货、逾期与客户一致性。按客户、工艺、新旧品、业务主体、金价波动等分层，报告不确定性和成熟度。
- 发布门槛由风险、样本数与基线确定，不宣称“准确率超过 90% 就上线”。违反硬性约束可直接阻断；软指标需业务负责人判断权衡。
- 监控变化区分：数据质量/Schema 漂移、业务输入分布漂移、效果漂移、政策改变；金价变动先更新受控数据和有效期，不自动触发对所有模型微调。模型不擅长的分布应降级到规则+人工。
- 迭代顺序：①关联链+快照+反馈；②人工审核案例记忆+检索；③评估集+可回滚提示/方法优化；④成熟结果与监督模型；⑤确有足够干净合规数据且提示/检索瓶颈明确时再考虑微调。微调学稳定任务行为，不用于存储实时金价、客户权限和频繁变动政策。

### Gaps
- 搜索履历已保存 `.firecrawl/20261016-qlearn-search-*`、`search-bing*`、`search-ddg*`：Google 返回 JS 挑战页，DuckDuckGo 返回验证码；Bing 第一条 DSPy 查询有相关官方及 GitHub 命中，LangSmith 查询返回不相关 YouTube 结果，后者未作为证据。主要结论来自逐一读取官方全文（HTML 与提取 txt 均缓存）。
- Firecrawl 按协调者提示处于依赖故障，本子任务没有修改工具或安装依赖。无对外通信，无 ERP 代码修改。
