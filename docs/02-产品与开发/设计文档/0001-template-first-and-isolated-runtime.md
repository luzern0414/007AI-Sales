# ADR 0001：采用模板优先与独立运行边界

状态：**提议，未获设计批准**。日期：2026-10-12，Asia/Shanghai。
决策负责人建议：产品负责人、研发负责人、安全负责人共同评审；本记录不触发实施。

## 问题与背景

售前需要在手机上把客户访谈变成可确认的需求，再展示核心业务流程。目标产物含真实 API 和数据库，而不是仅有视觉页面。
输入资料可能含敏感内容和不可信指令，生成代码也不可信；范围、外部执行、费用和分享都需要平台约束。
团队技术偏好、样本质量和真实模型账号尚未明确，当前只能提出可验证路线。

## 备选路线

| 路线 | 获益 | 主要成本/风险 |
|---|---|---|
| 模板 + 有界单 coding worker | 固定构建、API、依赖及验收；可解释范围；便于手机交付。 | 模板覆盖有限，需要人工维护与明确拒绝超范围。 |
| 整体嵌入/fork builder | 开放的开发交互和更多栈。 | UI 服务化、多租户/授权、runtime 商业许可、升级耦合。 |
| 自由生成 + 多 Agent | 可探索复杂系统和更自由分工。 | 文件冲突、依赖漂移、工具权限、修复/预算及不确定性增大。 |

bolt.diy 的 MIT 不覆盖 WebContainers 商业 API；Dyad Pro 使用 FSL，Dify 包含附加多租户限制，gpt-engineer 已归档。不能把某个公开仓库当成无需评估的 SaaS 后端。([bolt](https://github.com/stackblitz-labs/bolt.diy/blob/main/LICENSE)，[WebContainers](https://webcontainers.io/enterprise)，[Dyad Pro](https://github.com/dyad-sh/dyad/blob/main/src/pro/LICENSE)，[Dify](https://github.com/langgenius/dify/blob/main/LICENSE)，[gpt-engineer](https://api.github.com/repos/gpt-engineer-org/gpt-engineer))

## 提议选择

采用三个受控模板：CRM-lite、工单、简单审批。每个模板有固定 React/Vite 前端、FastAPI 后端、独立 SQLite、合成数据与固定检查。
需求由销售确认后冻结版本/hash，job 只引用该输入。单 worker 顺序执行计划、有限 patch、构建/CRUD/持久化/手机检查、最多两轮修复及封装。
首轮引擎 PoC 使用 OpenAI Agents SDK + 显式 Chat Completions provider，候选百炼/DeepSeek；关闭默认 OpenAI tracing 出口。SDK 只掌握有限模型/工具循环，PG/Celery 掌握业务任务，supervisor 掌握隔离执行。
OpenHands Software Agent SDK 为第二候选，不改造整个 Agent Canvas；首期不引入 LangGraph 顶层状态及多 Agent 共同写文件。
手机访问服务端预览，不运行生成后端；平台 PostgreSQL 与各 Demo SQLite 分离。平台和 preview 使用不同可注册主域、不同 cookie/audience，分享只到指定 revision 业务端口。

## 隔离分阶段

内部受限模板 PoC 可评估独立 Linux runner 加固 Docker，非 root、资源限额、cap-drop、无 docker.sock/宿主挂载、运行时禁出网。
普通共享主机 Docker 不能成为任意不可信代码的充分边界。客户外部分享或扩大任意 patch 前，须完成独立 runner + gVisor/微 VM 或适当托管 sandbox 的隔离 PoC。([Docker](https://docs.docker.com/engine/security/)，[gVisor](https://gvisor.dev/docs/))
构建仅从审核 registry/缓存取冻结依赖；runtime 默认无外部连接。Agent/sandbox 不获得平台 DB、LLM 或对象存储管理员凭证。
E2B/Daytona 是托管候选，网络、数据驻留、tier、成本与许可另行验证；Daytona 旧公开 core 不再维护，不作为默认开源自建方案。([Daytona README](https://github.com/daytonaio/daytona/blob/main/README.md))

## 接受的限制

演示建议范围最多 3 个主要实体、5 个页面、1 条主流程；真实外部集成、支付、短信、复杂 RBAC、多级任意审批与生产交付不在首期。
同一 revision 共用合成数据，销售/访客需知道多人可能修改；每客户独立副本后置。SQLite 支持 Demo，不代表已满足多实例生产数据库需求。
队列幂等与 fencing 可限制重复产物发布，不能保证模型外部计费 exactly-once。succeeded 只表示验证过的演示产物，不是生产系统批准。
所有试点参数可调整，但变更后只影响新 job policy_version，不能静默改变正在运行的任务。

## 实施前验证门槛

同一批授权售前录音完成浏览器/ASR/需求证据对照；具体 provider 的工具、Schema、拒绝、截断、超时和 usage 行为有记录。
三模板建立真实 CRUD、重启持久化、快照恢复和手机 smoke 基线；coding worker 不允许修改验收器或锁文件。
PG/Celery/Valkey 在固定版本下做重投、worker 崩溃、lease 过期、fencing、取消和恢复实验；外部分享前完成网络/凭证/跨租户/预览域隔离证据。
实际成本记录全部分析、修复和 retry，不能只用首次模型输出估价。

## 何时重新评估

| 触发条件 | 重新评估活动 |
|---|---|
| 模板外高频需求已由售前样本证明 | 新增业务模板，先保持固定栈和质量 gate。 |
| Agents SDK 在目标 provider 工具/恢复能力未过门槛 | 对相同模板和预算比较 OpenHands SDK adapter。 |
| AI 子流程需要多分支人工暂停/回溯 | 局部引入 LangGraph，PG 仍保留最终业务事实。 |
| 单 worker 对清晰有限需求仍有系统性质量缺口 | 只读审查或模块分工 PoC，比较实际质量/成本后才采用多 Agent。 |
| 客户需要正式系统交付 | 独立生产方案：账号权限、PostgreSQL 迁移、真实集成、安全、备份/SLA 和运维。 |
| 团队已有成熟 Vue/Node 栈且迁移收益明确 | 替换平台栈，不改变证据、冻结、任务和 runtime 契约。 |

证据与方案详见[调研报告](<AI%20%E9%94%80%E5%94%AE%E5%8A%A9%E6%89%8B%20%E6%8A%80%E6%9C%AF%20%E8%B0%83%E7%A0%94.md>)和[技术架构](technical-design.md)；决策结果应更新本 ADR，不以沉默当批准。
