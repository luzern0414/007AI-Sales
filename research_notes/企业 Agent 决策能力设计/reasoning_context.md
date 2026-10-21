# 企业 Agent 的推理、上下文、记忆与评估设计

## 如何把“思维链”变成可验证的决策过程？

### Takeaway
用户实际在问产品智能：能否理解经营目标、主动发现问题、检验解释并提出可执行建议。应区分模型内部推理、工程中可控制的分析工作流、用户看到的证据化解释；增长点在后两者，不能用冗长的内心独白代替业务判断。

### Cited Findings
- OpenAI《Reasoning best practices》明确建议对推理模型使用简单直接的指令，避免“think step by step”“explain your reasoning”式 CoT 提示，因为模型已在内部进行推理；应明确目标、约束和成功标准，先尝试 zero-shot，需要时再加入匹配任务的示例。该页面包含较旧 o 系列模型案例，不宜据此推荐具体旧型号。— [官方文档](https://developers.openai.com/api/docs/guides/reasoning-best-practices)
- Anthropic《Building effective agents》（2024-12-19）区分 workflow（预定义代码路径）与 agent（模型动态决定过程和工具）；推荐最简单的可行方案。固定任务用 workflow 可获得可预测性，开放探索才需要 agent，复杂性增加必须体现于实际效果。— [原文](https://www.anthropic.com/engineering/building-effective-agents)
- 同一原文要求 agent 在执行中从环境获得 ground truth，例如工具结果和执行反馈；强调循环、退出条件、明确工具契约；evaluator–optimizer 适用于评价标准清晰且迭代改进可测量的情况。它并不证明任意任务加“反思角色”都会改善结果。— [原文](https://www.anthropic.com/engineering/building-effective-agents)
- ReAct（ICLR 2023）将推理与工具行动交错，使模型能更新计划、处理例外、访问外部知识或环境；论文在 HotpotQA、FEVER、ALFWorld、WebShop 等任务上展示效果。属于特定模型与基准结果，不能直接等同于企业财务判断正确率。此处实际读取论文摘要。— [论文原始页面](https://arxiv.org/abs/2210.03629)
- Reflexion（2023）让 agent 反思任务反馈、把反思文本写入 episodic memory，影响之后的尝试，而不是更新模型权重。其 HumanEval 成绩来自特定实验设置，不能用作“自我学习必然有效”的证据。此处实际读取论文摘要。— [论文原始页面](https://arxiv.org/abs/2303.11366)
- Huang 等《Large Language Models Cannot Self-Correct Reasoning Yet》（ICLR 2024）在 GPT-3.5、GPT-4、GPT-4-Turbo、Llama-2 和 GSM8K/CommonSenseQA/HotpotQA 上研究无外部反馈的 intrinsic self-correction：自检后经常降分。例如其 GPT-4 GSM8K 样本中由 95.5 降至第一轮 91.5、第二轮 89.0；有 oracle 正确性反馈时则提升。重要限制：这些是旧模型、选定提示、最多两轮和特定任务，不能推断 2026 所有模型都不能自纠错。实际读取全文与实验设置。— [全文](https://arxiv.org/html/2310.01798v2)
- 同一研究对多 agent debate 作等响应数比较：GSM8K 上 9 次响应的 debate 83.0，self-consistency 88.2；说明“多个角色相互讨论”的收益不能脱离计算预算比较，不等于证明所有多 agent 都无效。— [全文第四节](https://arxiv.org/html/2310.01798v2)
- 《Why Do Multi-Agent LLM Systems Fail?》（arXiv 2025，已读取 v3 摘要）分析 7 个框架的 1,600+ 标注轨迹，提出 14 类失效，归于系统设计、agent 间失配、任务验证三大类别。其样本模型包括 GPT-4、Claude 3、Qwen2.5、CodeLlama，不能当成所有新架构的普遍失败率。— [论文原始页面](https://arxiv.org/abs/2503.13657)

### Inferences
- 建议对“思维链”采用三层表述：①模型内部推理，由模型能力与推理预算影响；②工程分析流程，由检索、查询、计算、检验、状态与控制逻辑组成；③面向用户的分析依据，包含证据、假设、计算方法、反证、未知项、建议。只承诺可追溯的②③。
- 推荐企业分析循环：明确决策和约束 → 校验数据/口径 → 形成少量竞争假设 → 找区分假设的证据 → 调工具计算和核对 → 比较可选行动及其成本/风险 → 给出建议或暂缓判断 → 执行经授权动作 → 追踪实际效果。它是研究综合出的设计建议，不是某一论文已证明的通用最优框架。
- 举例（虚构）：若收入下降，先区分成交量、客单价、产品组合、退货、收入确认时点，再验证 CRM 转化、订单与总账；若是回款下降，另外检查账龄、付款条款、开票/验收节点。收入与现金流不是同一问题。对立假设要能被不同证据支持或排除。
- “有想法”可操作化为主动提出有证据的新问题、指出原问题假设可能错误、知道下一条最有信息价值的查询、比较选项、在证据不足时给出补证计划。不是强制每个答复输出固定三条建议。
- 对反思加硬约束：只有新证据、计算不一致、规则冲突、明确反例或专家反馈才触发修正；限制轮数和预算，记录改变结论的依据。避免同一模型在同一信息上反复说“再想想”。
- 多 agent 可用于相互独立的业务域检索/验证，收益是分工、上下文隔离、并行；不要把互相同意当正确性证明。财务数字最终仍由公式、账表勾稽、数据源与专家标准约束。

### Gaps
- 未找到足以证明“一套通用提示即可产生可靠企业战略判断”的可信证据。
- 不能从上述旧模型论文量化当前模型的企业场景自纠错收益，需要用本企业数据与模型版本重测。
- 因果诊断、预测、财务归因须引入相应业务模型、统计识别或实验设计；LLM 说得合理并不等于完成因果证明。

## 上下文、记忆和提示词怎样配合？

### Takeaway
长提示词不会自动带来深思熟虑；关键是把正确、最新、适用当前用户权限的信息，在正确阶段送入上下文。长期记忆应帮助恢复任务与复用经过验证的经验，而不是积累未经核验的模型结论。

### Cited Findings
- Anthropic《Effective context engineering for AI agents》（2025-09-29）将 context engineering 定义为在推理时维护最佳 token 集合，包括系统指令、工具、外部数据、历史；倡导最小但高信号的上下文。文章指出窗口扩大仍可能出现 context rot、注意力分散。属于工程经验总结，并非所有模型精确统一的性能曲线。— [原文](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- 同文建议系统提示处于“足够具体但不过度硬编码”的层级；明确划分背景、指令、工具和输出；工具功能边界清晰、参数可理解、返回高效；过多重叠工具会制造选择歧义。Anthropic 推荐精选多样典型例子，OpenAI 对推理模型则建议先 zero-shot；应视模型与任务用评测决定，不存在统一示例数量。— [Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)；[OpenAI](https://developers.openai.com/api/docs/guides/reasoning-best-practices)
- 同文提出 just-in-time 检索：保留文件路径、存储查询、链接等轻量标识，运行时加载所需信息；可以与预先检索混合。代价是运行时探索更慢，需要良好工具与引导，可能浪费上下文或走进死胡同。— [原文](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- 同文列出长任务的 compaction、结构化笔记、子 agent 隔离；压缩应保留决定、未解决问题和关键细节；过度压缩会丢失后续才显示价值的信息。结构化笔记是外置记忆，不意味着模型权重更新。— [原文](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Anthropic《Effective harnesses for long-running agents》（2025-11-26）发现即使具备 compaction，高层提示也可能使 agent 一次做太多、留下未完成状态或过早宣告完成；其编码实例通过初始环境、明确 feature 清单、增量工作、进度日志、git 与端到端检查改善。作者明确指出实验针对全栈 Web 开发，迁移到金融建模等仍是未来方向，不能把工程类比说成金融实证。— [原文](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

### Inferences
- 企业上下文建议分层：长期稳定的职责/底线；公司目标、业务实体与指标语义；用户/部门/权限；当前任务的时间范围、币种、口径和决策约束；本轮检索证据与计算结果；历史已确认结论和待办。检索不能只按文本相似度，还需公司、实体、有效期、来源、权限、口径过滤。
- 将知识库从“文档仓库”升级为“证据与业务语义库”：指标定义、计算规则、实体关系、财务/经营机制、流程 SOP、历史案例、数据质量规则、已验证决策及结果。模型才能理解“为什么重要”和“下一步查什么”。这是设计建议，跨域实际实施需专项验证。
- 记忆建议分为：事实记忆（来源和有效期）、任务记忆（目标、假设、已查/未查、状态）、经验记忆（经验证方法与失败条件）、偏好记忆。每条应保存来源、时间、适用范围、确认状态；过期/被否定需撤销或降权。不要将一次猜测写为永久事实。
- 提示应像可测试的工作合同，包含职责与目标、数据语义、工具选择原则、证据标准、边界与退出条件、输出合同。公司全部制度不要塞进系统提示，而是按权限和任务检索。
- 可给主文使用的提示示例（设计草案）：“你帮助经营负责人做可执行的判断。先明确要支持的决策及评价标准；使用企业定义的指标和有效期内数据；必要计算调用工具并保存可复算依据；区分已验证事实、待验证假设与建议；对重要判断主动寻找可能推翻它的证据；缺少关键数据时说明结论边界并优先获取最有区分力的信息；建议需说明影响范围、主要代价、风险、负责人/前置条件与验证指标；遵守授权边界。最终给出核心判断、证据、备选行动和下一步，不输出逐字内部推理。”
- 角色提示“你是 CFO”主要提供方向和文风，不能提供公司真实账表、指标定义、正确工具或业务验证；必须与知识、工具、状态和评估配套。

### Gaps
- 最佳压缩比例、检索片段数、记忆保留期、是否采用图谱等没有跨企业统一最优值。
- 记忆写入的准确性、权限隔离、版本冲突与遗忘机制是实施问题；以上来源主要提供 agent 工程方向，不能替代完整安全设计。

## 如何判断 agent 真在改善经营决策，而非更会说？

### Takeaway
将“像有想法”改成明确成功标准，以真实业务案例、外部状态与专家评价检验。评估单位应是完整任务与实际结果，不能只测答案文采或单轮问答准确率。

### Cited Findings
- Anthropic《Demystifying evals for AI agents》（2026-01-09）强调 agent eval 应同时考虑 transcript（工具、步骤与过程记录）和 outcome（环境最终状态）；“说已订票”不等于数据库中存在预订。评估的是 model + harness，不只是模型。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- 同文建议从 20–50 个真实失败的简单任务起步，不必等数百个案例；使用明确成功标准、参考解、隔离环境和多次 trial。20–50 是启动建议，不能充当成熟金融系统充分样本量。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- 同文区分 code-based、model-based、human graders；尽可能用确定性评分，必要时用 LLM，且与专家校准。研究 agent 可评估 groundedness、coverage、source quality，而非只看引用数量。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- 同文建议覆盖“应发生”和“不应发生”两侧，避免为了让模型多搜索而变成什么都搜索；更偏向评价最终产物，不把某一工具调用顺序当成唯一正确路径；可用部分分数刻画复杂任务。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- 同文区分 pass@k（至少一次成功）与 pass^k（k 次均成功）；示例每次成功率 75%，三次均成功仅约 42%，说明演示偶尔成功不等于稳定交付。其公式示例隐含独立同分布近似；现实多次运行可能相关。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
- 同文强调离线 eval、生产监测、A/B、用户反馈和人工检查互补；没有一种方法覆盖全部失效。其工具附录列 Braintrust、LangSmith、Langfuse、Arize Phoenix 等，只是可选基础设施，数据集与评价规则才是核心。— [原文](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

### Inferences
- 推荐企业任务评估维度：①数值/口径正确；②引用确实支持结论且有效；③识别关键异常并过滤假警报；④能区分竞争解释、避免无依据因果；⑤建议满足资源与业务约束；⑥能适当说证据不足；⑦动作符合授权且最终状态正确；⑧时延、成本和跨运行稳定性；⑨后续业务效果。不要只评分“建议看起来专业”。
- 财务题库可包括：收入增长但现金流恶化；账龄集中于少数客户；利润下降因产品组合而非成本；季节性异常；缺失汇率；重分类使同比失真；相互冲突的版本；本来不应采取行动的正常波动。每个场景需业务专家给出可接受判断范围和必要证据。
- 产品中可见的工作产物建议为：本次目标、正在核查的问题、已获得证据、重要不确定性、推荐行动与备选项、下一步验证。它们都是可核验对象，也比打字动画或冗长“思考过程”更能产生信任。
- 验证建议可分三级：观察性分析可提供线索；对账/规则检查能给确定性约束；策略成效须通过跟踪、对照或适合的统计设计判断。企业结果受很多因素影响，不能把 AI 上线前后差异直接称因果收益。

### Gaps
- 没有公开证据证明某一平台框架对所有企业场景优于其他框架。
- “好商业建议”往往存在多解，需要企业专家定义约束、可接受范围与长短期权衡；现有通用 benchmark 无法代替。
- 检索记录：实际执行 Google 查询 `enterprise agents context engineering self reflection evaluation Anthropic OpenAI`（只返回跳转页）；Bing 查询 `Anthropic context engineering agents self reflection evaluation`（返回 Anthropic 官方主页等泛化结果）；DuckDuckGo 查询精确短语 `effective context engineering`（人机挑战页）。搜索结果质量有限，最终引用均来自实际读取的官方原文或论文，未把搜索摘要当证据。缓存位于 `.firecrawl/20261016-reason-*`，包含官方页面、论文摘要、自纠错全文及搜索页。由于 Firecrawl 的缓存 zod 损坏，按协调者指示采用只读 HTTP 获取；不声称执行了全面文献系统综述。
