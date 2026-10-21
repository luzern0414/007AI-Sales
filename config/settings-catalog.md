# 配置参数目录草案

日期：2026-10-12，Asia/Shanghai。只有文字定义，无真实密钥或可执行配置。
默认值均为试点政策建议；provider/模型/endpoint 需实际账号验证，不用未知值伪装可运行配置。
作用域标记：环境、平台策略、组织、用户、项目、job 冻结策略、attempt、runtime。秘密标记为“是”的值只能经 secret store/受控注入，不写源码或文档。

## 环境、身份与数据

| 参数名 | 目的 | 暂定默认/选择活动 | 作用域 | 秘密 |
|---|---|---|---|---|
| environment_name | 区分部署资源与日志。 | dev / staging / prod 分开，尚未创建。 | 环境 | 否 |
| deployment_region | 业务/数据处理地域。 | 境内候选，负责人验证企业账号/合同/网络后固定。 | 环境 | 否 |
| organization_timezone | 汇总/到期显示时区。 | Asia/Shanghai。 | 组织 | 否 |
| auth_invitation_only | 试点注册入口。 | 开启。 | 平台策略 | 否 |
| auth_session_secret_ref | 服务端 session 签名/保护。 | secret store 引用，未生成。 | 环境 | 是 |
| auth_session_policy | session TTL/撤销/CSRF。 | 安全负责人在身份 PoC 固定，host-only cookie。 | 平台策略 | 否 |
| platform_domain | 销售 Web/API 域。 | 待实际域名选定，无共享 Domain cookie。 | 环境 | 否 |
| preview_domain | 与平台不同可注册主域。 | 运维选域并验证 cookie/CSP/移动网络。 | 环境 | 否 |
| platform_database_secret_ref | PostgreSQL 最小权限连接。 | 平台服务专用，sandbox 不可得。 | 环境 | 是 |
| object_storage_endpoint | S3 兼容私有对象服务。 | 境内服务候选，签名/生命周期 PoC 后固定。 | 环境 | 否 |
| object_storage_credentials_ref | 按服务划分取件/写件权限。 | admin 不发 worker/sandbox。 | 环境 | 是 |
| object_storage_buckets | 原音/结果/产物分区。 | 私有、环境隔离、tenant/task 路径授权。 | 环境 | 否 |
| upload_signed_url_ttl | 临时上传授权时效。 | 根据大 Blob/手机弱网 PoC 固定，绝不长期公开。 | 平台策略 | 否 |
| idempotency_retention | 重试键保存窗口。 | 技术负责人按最长客户端重试及人工恢复周期确定。 | 平台策略 | 否 |

## 录音与 ASR

| 参数名 | 目的 | 暂定默认/选择活动 | 作用域 | 秘密 |
|---|---|---|---|---|
| recording_max_minutes | 单次会话采集上限。 | 30 分钟。 | 组织/用户 | 否 |
| upload_max_source_bytes | 会话源音/文件总大小。 | 100 MiB，转码副本另预算。 | 组织 | 否 |
| recording_target_chunk_seconds | 提示分片 cadence。 | 5 秒，实际事件可延迟，不作为时间真值。 | 平台策略 | 否 |
| recorder_mime_candidates | 运行时探测候选。 | webm/opus、mp4 等，采纳真实 mimeType。 | 平台策略 | 否 |
| local_audio_buffer_limit | IndexedDB 有界缓冲。 | 浏览器容量 PoC 固定上限/报警，best-effort。 | 用户/平台策略 | 否 |
| upload_request_limit | 单请求及大 Blob 处理。 | P0 大 Blob/代理实验确定，不由 5 秒推断。 | 环境 | 否 |
| asr_primary_provider | 主识别服务。 | 阿里文件 ASR 首轮候选，腾讯/火山同语料对照。 | 平台策略 | 否 |
| asr_engine_region | 具体引擎、地域和版本。 | 企业账号/同语料/合同确定；不写未测试型号。 | 环境/组织 | 否 |
| asr_credentials_ref | ASR 提交/查询鉴权。 | 授权服务持有，手机不持有长期 key。 | 环境 | 是 |
| asr_hotword_policy | 术语/名称词表。 | 项目允许词表，经误召回评测。 | 项目/组织 | 否 |
| asr_diarization | 匿名说话人聚类。 | 在通过该引擎 PoC 后开启，不建声纹库。 | 平台策略 | 否 |
| asr_task_timeout | 提交/轮询 deadline。 | 依据样本耗时及厂商接口固定，未给时延保证。 | 平台策略 | 否 |
| asr_result_download_policy | 避免临时结果到期。 | 完成即拉取并持久保存，自有引用。 | 平台策略 | 否 |

## 模型与 coding worker

| 参数名 | 目的 | 暂定默认/选择活动 | 作用域 | 秘密 |
|---|---|---|---|---|
| model_primary_provider | 需求/代码模型路由。 | 百炼/Qwen、DeepSeek 首轮候选；用途分别评测。 | 平台策略 | 否 |
| model_endpoint_region | 企业 endpoint/base_url 与地域。 | 按 workspace/账号官方配置核验，不硬编码历史 URL。 | 环境 | 否 |
| model_allowed_strategy | 可用 provider/model/API/mode 策略。 | capability PoC 后按 purpose 冻结允许清单；retry 不扩大。 | job 冻结策略 | 否 |
| attempt_model_id_and_mode | 本次具体执行型号和接口。 | 从冻结允许策略选择，保存实际 provider/model/API/mode/capability_version。 | attempt | 否 |
| model_credentials_ref | 模型网关鉴权。 | 网关持有，不进入 sandbox/生成物。 | 环境 | 是 |
| provider_capability_version | strict/schema/tool/stream/usage 能力。 | 每 model+API+mode 的测试结果版本。 | 平台策略 | 否 |
| schema_validation_policy | 结构与语义校验。 | native strict 经验证才启用，否则校验+有界纠正。 | job 冻结策略 | 否 |
| schema_correction_limit | 分析坏结构纠正上限。 | 模型样本 PoC 固定次数/token；禁止无限纠正。 | job 冻结策略 | 否 |
| model_timeout_retry_policy | 超时/拒绝/限流分类处理。 | 无外部副作用阶段有限重试，不自动重放已提交操作。 | job 冻结策略 | 否 |
| coding_engine | 工具循环引擎。 | Agents SDK 首轮 PoC；OpenHands SDK 第二候选。 | job 冻结策略 | 否 |
| agents_default_tracing_export | 默认 OpenAI trace 外发。 | 关闭，接入前验证无外发。 | 环境 | 否 |
| custom_trace_retention | 自定义最小化审计保留。 | 运维按目的定义，禁普通日志写业务全文。 | 组织/环境 | 否 |
| tool_policy_version | 受限文件/固定检查集合。 | patch/read/list/fixed-check；无通用宿主 terminal。 | job 冻结策略 | 否 |
| generation_attempt_walltime_minutes | 活动执行上限。 | 15 分钟；从 lease acquisition 累计，排队不计，恢复不重置。 | job 冻结策略 | 否 |
| generation_auto_repair_rounds | 检查失败自动修复上限。 | 2，属于同一 attempt。 | job 冻结策略 | 否 |
| model_token_call_tool_budgets | token/调用/迭代上限。 | 样本成本分布决定，job/attempt 都有硬边界。 | job 冻结策略 | 否 |
| generation_user_concurrency | 单用户同时活动生成数。 | 1。 | 组织/用户 | 否 |
| generation_tenant_concurrency | 单组织同时活动生成数。 | 2。 | 组织 | 否 |
| tenant_monthly_budget | 全用途累计支出边界。 | 业务负责人根据实际价/样本决定预警与硬上限。 | 组织 | 否 |
| manual_retry_budget_policy | 手动重试追加费用。 | 新 attempt、同 frozen 输入，仅冻结允许策略内切换模型并记录原因，job/租户累计预算继续生效。 | job/组织 | 否 |

## 队列、runtime、模板与分享

| 参数名 | 目的 | 暂定默认/选择活动 | 作用域 | 秘密 |
|---|---|---|---|---|
| broker_adapter_version | 作业投递。 | Celery + Redis 协议；Valkey 指定版本先做兼容 PoC。 | 环境 | 否 |
| broker_credentials_ref | broker 访问。 | worker/派发专用最小权限。 | 环境 | 是 |
| lease_heartbeat_fencing_policy | 防旧 worker 发布与恢复。 | timeout/heartbeat 结合最长任务故障 PoC 固定。 | 平台策略 | 否 |
| celery_ack_visibility_prefetch | ACK/重投/公平性。 | 与 lease/deadline 固定版本组合实验，不预设 exactly-once。 | 环境 | 否 |
| template_catalog_version | 模板、hash、锁和许可。 | CRM-lite、工单、简单审批固定版本候选。 | job 冻结策略 | 否 |
| demo_scope_limits | 控制需求自由度。 | ≤3 主要实体、≤5 页面、≤1 主流程，未经覆盖率证明。 | job 冻结策略 | 否 |
| sandbox_isolation_profile | runner/runtime 强隔离。 | 内部加固 Docker PoC；外部分享须独立 host + gVisor/微 VM/适当 managed。 | 环境 | 否 |
| sandbox_control_credentials_ref | 创建/停止/查询 sandbox。 | supervisor 独持，绝不分享客户。 | 环境 | 是 |
| sandbox_cpu_memory | 起始配额。 | 2 vCPU / 2 GiB，须容量验证。 | job/runtime | 否 |
| sandbox_pid_disk_output_limits | 防资源耗尽。 | 模板构建/检查器容量实验固定并硬限制。 | job/runtime | 否 |
| build_registry_allowlist | 构建依赖来源。 | 审核缓存/内部 registry，依赖/image digest 冻结。 | 环境 | 否 |
| runtime_egress_policy | 运行时代码外联。 | deny-default，阻断内网/metadata/DNS/IPv6 绕过。 | runtime | 否 |
| preview_idle_sleep_minutes | 无访问休眠。 | 30 分钟。 | runtime | 否 |
| preview_wake_policy | 快照唤醒。 | 一致 SQLite snapshot+source/lock 后 health，不延长 share。 | runtime | 否 |
| share_default_days | 私密客户分享建议期。 | 7 天；实际取该政策与产物剩余寿命最小值。 | 组织 | 否 |
| share_token_secret_ref | 生成/保护窄授权 token。 | 网关独持，token_digest 存库，日志脱敏。 | 环境 | 是 |
| share_scope_policy | 访问面。 | 指定 revision 业务端口 demo-only，无平台/terminal/导出管理。 | 平台策略 | 否 |
| gallery_client_case_publication | 客户派生案例公共发布。 | 首期默认关闭；owner/admin 脱敏审阅才允许。 | 组织/平台策略 | 否 |

## 保留与删除

| 参数名 | 目的 | 暂定默认/选择活动 | 作用域 | 秘密 |
|---|---|---|---|---|
| raw_audio_retention_days | 原音、分片、转码清理。 | 30 天；到期 audio_available=false。 | 组织 | 否 |
| transcript_fulltext_retention_days | 原始/更正全文保存。 | 180 天；到期全文不可读，必要摘录单独策略。 | 组织 | 否 |
| confirmed_spec_evidence_retention | 确认需求与必要摘录。 | 按项目目的保留至删除；组织可更短。 | 组织/项目 | 否 |
| source_snapshot_retention_days | 源码 bundle、构建产物、SQLite 快照。 | 30 天；到期 runtime expired，不承诺仍可恢复。 | 组织/runtime | 否 |
| deletion_policy | 撤销与物理清理顺序。 | 即刻逻辑撤销+取消任务，异步对象/缓存/索引清理。 | 平台策略 | 否 |
| backup_retention_days | 隔离备份窗口。 | 滚动 30 天；恢复先重放删除清单，窗口后移除副本。 | 环境/组织 | 否 |
| supplier_data_policy_version | 厂商保存、训练、删除和地域。 | 数据责任人按实际企业合同核验，不以结果 TTL 替代。 | 环境/组织 | 否 |

参数校准证据见[阶段与验收](../docs/03-%E6%B5%8B%E8%AF%95%E4%B8%8E%E4%BA%A4%E4%BB%98/%E6%B5%8B%E8%AF%95%E9%AA%8C%E6%94%B6/phase-plan-and-acceptance.md)。业务限制调优不改变既有 job 的 spec/template/policy hash；紧急撤销分享、删除和安全封禁即时生效。
