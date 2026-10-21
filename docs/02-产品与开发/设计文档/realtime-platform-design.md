# Web AI 销售助手实时会议平台设计

版本：V2.0 设计稿；日期：2026-10-15，Asia/Shanghai。状态：架构与功能设计，未编写应用代码、运行录音或生成 PDF。采集/保存与导出协议继续有效；业务页面以[项目交付设计 V3](project-delivery-design.md)为准。本文是 V2 技术基线，替代 V1 中“会后转写、PDF 后续”的范围；V2 是文档版本，不是项目分期。

建议自建销售业务 Web 应用，以 **首页、历史纪要、产品库、工作台** 四个入口完成“现场录音 → 实时文字与持续保存 → 校对和冻结事实 → 产品能力匹配 → 纪要、方案和清单 → 编辑确认与下载”。录音可靠性独立于 ASR 与 Agent，任何模型故障都不应阻塞已支持设备上的音频落盘。前台麦克风是基础场景；手机锁屏、后台或来电不能承诺持续录音。设计通过检查点、幂等块、连续保存水位和明确缺口减少可避免损失，不能承诺绝对零丢失。

研究依据见[综合调研](<Web%20%E9%94%80%E5%94%AE%E5%8A%A9%E6%89%8B%20%E5%AE%9E%E6%97%B6%E4%BC%9A%E8%AE%AE%20%E6%9E%B6%E6%9E%84%E8%B0%83%E7%A0%94.md>)；视觉与交互见[UI 设计](ui-spec.md)；文档内容遵循[Agent 输出规范](agent-output-standard.md)和 `D:\Codes\方案格式规范.txt`，三者修改必须同步。

## 一、业务范围与页面职责

现场客户会议中，销售选择客户/项目，检查麦克风电平，点击开始；实时转写可标记重点、手工速记和记录待确认问题。会议结束先保存尾部并补传，再进行会后校正、人工校对和文档生产。无产品资料时仍能生成有来源的纪要与需求清单，方案相应能力必须列“待核实”，不能凭空给出肯定交付承诺。

| 一级入口 | 必需功能 | 业务结果 |
|---|---|---|
| 首页 | 当前会议、麦克风选择/测试、录音开始/暂停/继续/结束、实时文字、重点标记、速记、本机与服务端保存时间、补传与恢复 | 会议音频和逐字稿有可验证时间线，异常可发现 |
| 历史纪要 | 客户/项目/日期/状态筛选、会议详情、回放定位、转写与纪要修订、录音完整性、纪要 MD/PDF 下载 | 同一会议的记录、来源和版本可追溯 |
| 产品库 | 产品与有效版本、资料上传/解析、能力与限制核实、标准片段、授权与报价可见性 | 推荐依据来自真实已核实产品资料 |
| 工作台 | 选会议与产品版本、四类文档编辑、需求覆盖、来源查看、缺口与规则检查、重生成、审核和文件导出 | 有会议依据的售前方案、需求清单与甲方确认清单 |

设置、用户管理和技术配置从账户菜单或页面内入口进入，不新增一级导航。全局录音状态在切换页面时持续可见，实际采集仍由唯一录音页面/Worker 持有；页面路由不得销毁音频运行时。

| 文件 | 当前必需输出 | 约束 |
|---|---|---|
| 会议纪要 | Markdown、PDF | 同一纪要修订与结构树；未确认版标讨论稿，允许直接下载 |
| 售前解决方案 | Markdown | 正式方案扩展 Word 审核，再由已审 Word 转正式 PDF；不能将未审稿标为获批 |
| 需求清单 | Markdown | 稳定 REQ 编号；XLSX 填报版为可配置扩展 |
| 甲方资料、权限与规则确认清单 | Markdown | 沿参考 XLSX 的使用说明、主清单、回收统计、专项填写结构；XLSX 扩展共用行数据 |

当前会议没有明确分期要求，全部产物默认 `single_version`，不得继承样板文件名里的“一期”；实施工作顺序不等于项目一期二期。纪要、方案、清单只引用当前会议及经授权资料。参考 PDF 和 XLSX 只借组织/填报形式，不借客户、功能数量、工期、配置或准确率。

## 二、唯一推荐技术栈与责任边界

推荐 React + TypeScript + Vite 自建 Web 前端，FastAPI 业务 API，PostgreSQL + pgvector，私有对象存储，LangGraph + PostgreSQL checkpointer，普通 Pydantic 结构校验，独立转写/解析/PDF worker。主要页面不依赖 SEO，Vite 静态部署即可；不同时增加 Next.js 服务端运行层。实时识别先选一家经过同语料 PoC 的国内云中文 ASR，FunASR 2pass 是私有化替换候选；供应商在适配层替换，不改会议事实与音频协议。

| 层 | 推荐实现 | 明确职责 |
|---|---|---|
| Web UI | React/TypeScript/Vite、shadcn/ui 定制组件、锁定版本的可访问 primitive | 四页工作区、状态、编辑、回放与授权下载 |
| 采集与本地保存 | AudioWorklet + Dedicated Worker；OPFS 自描述日志 + IndexedDB 会话索引 | 采样、重采样、落盘、manifest、离线队列、重开恢复 |
| 实时网关 | FastAPI WebSocket + ASR adapter | 短期鉴权、厂商会话、字幕事件、速率和背压 |
| 归档接收 | 独立 HTTP 分块接收 + 私有对象存储 + PostgreSQL manifest | 校验和、幂等、持久 ACK、缺块补传、归档封存 |
| 业务服务 | FastAPI + PostgreSQL | 租户/项目授权、会议、产品、事实、文档与审计 |
| 产品资料 | Docling 验证 PDF 路径；专用 XLSX 读取；普通办公材料可选 MarkItDown | 原件与页码/工作表映射、能力核实、检索索引 |
| 检索 | PostgreSQL 全文检索 + pgvector，中文分词另验 | 硬权限过滤、关键词/向量融合、重排与出处复核 |
| 文档工作流 | LangGraph + PostgreSQL checkpointer；Pydantic schema | 有界步骤、暂停确认、按版本恢复与重生 |
| 非 Agent 作业 | PostgreSQL jobs/outbox + 普通异步 worker | 会后 ASR、解析、排版、导出重试；不负责另一套文档编排 |
| PDF | 安全 HTML 模板 + Playwright/Chromium print worker | 纪要 A4 PDF、中文字体、分页和校验 |
| 可观测与运维 | 结构日志/指标、备份、审计、限流、健康探测 | 音频队列、保存尾部、任务状态与权限异常 |

首版不同时叠加 Agents SDK、CrewAI、Temporal、Mastra 或 Pydantic AI 作为第二个主流程引擎。LangGraph checkpoint 保存处理进度，业务数据库保存权威事实，音频日志/对象存储保存音频；三者不可互相代替。Celery 如后续引入，只投递独立非 Agent 作业，并按业务 operation_id 去重，不再次接管 LangGraph 的节点重试。缓存/Redis pubsub 不作为归档持久层。

下图说明两个实时数据路径及文档生产边界。

```text
现场麦克风 → AudioWorklet → Worker（规范 PCM、采样时钟）
                              ├→ OPFS 日志 / IDB 索引 → HTTP 补传 → 归档接收 → 对象存储
                              └→ 100–200ms 音频帧 → WebSocket → ASR adapter → 实时字幕
                                              ↑                             ↓
                                     独立背压/新会话                 事件与转写修订入库

会议结束 → flush / 补缺块 / seal → 会后校正 → 人工校对 → FactSnapshot
                                                 ↓
产品库（版本/权限/已核实能力） → 受限检索 → LangGraph 文档工作流
                                                 ↓
                         共用结构树 → MD / 纪要 PDF / 可选 DOCX、XLSX
                                                 ↓
                                工作台审核 / 历史下载 / 权限与审计
```

从单机开发容器开始可部署反向代理、Web、API/实时网关、各类 worker、PostgreSQL、对象存储。正式并发增加时独立扩展实时网关与 worker；WebSocket 连接归属与重连恢复依赖持久会话映射，而不是用户恰好落回同一个进程。数据库和对象存储制定实际备份/RPO/RTO并演练恢复，未演练前不声称高可用。GPU 仅在私有 ASR/embedding 确认必要后采购；现场单麦采集无需先上 LiveKit SFU。

## 三、实时采集与保存协议

### 3.1 采样、时钟与块定义

用户点击开始后获取安全上下文的麦克风流，读取实际 AudioContext sampleRate。AudioWorklet 只捕获帧、记录采样计数并送有界队列，不进行网络/文件 I/O；Worker 做声道处理、有状态抗混叠重采样与规范 PCM16 编码。建议 ASR/标准归档统一 16 kHz、单声道，保留设备采样率元数据；不把抽样“每三个取一个”当重采样。SharedArrayBuffer 可优化，但需要跨源隔离，不能成为全部设备基础门槛。

| 块/事件字段 | 含义与校验 |
|---|---|
| tenant_id、meeting_id、session_id | 服务端身份绑定；模型/客户端不得任意扩大租户范围 |
| capture_epoch、fencing_token、seq | 每次实际采集启动一个 epoch；同 epoch 序号递增；防旧录音方并发写 |
| source_sample_rate、output_sample_rate、channels、encoding | 独立解码所需参数；标准块明确 PCM16 字节序 |
| sample_start、frame_count、payload_len | 每个epoch内部sample_start从0起，时长和字节数交叉验证；不能直接跨epoch相减 |
| SHA-256、previous_block、commit_marker | 内容完整性、前后关系、截断尾块识别 |
| capture timestamp / epoch offset | 每epoch保存到meeting统一时间轴的偏移/锚点；墙钟标会议日期，单进程monotonic clock标经过时间，sample clock标真正采到的帧 |
| gap_map | 区分主动暂停、设备中断、后台挂起、溢出与真实未知缺口；不悄悄拼成连续发言 |

建议 100–200 ms 小帧供 ASR，约 1 秒自描述块供归档。块时长、flush 频率和 UI 更新频率是不同参数，均需设备实测。16 kHz PCM16 经过重采样和单声道处理是“标准语音归档”，不宣传为设备原生无损音频。可选保真多声道备份独立计算容量与策略。

### 3.2 本地持久确认

首选 OPFS append 日志记录“块头 + payload + hash + 提交标记”，Dedicated Worker 定期 flush；IndexedDB 保存 manifest 和会话索引。OPFS 与 IDB 不构成跨存储原子事务：恢复扫描音频日志，校验完整记录，舍弃截断尾部，重建索引。未 flush 的内存数据不推进本机保存水位。较简单备选是 payload+metadata 在同一 IDB strict transaction 中存储，等待整笔 transaction complete；request success 不代表事务已提交。strict/OPFS 支持、性能和降级语义须逐设备验证。

录音前查询 storage.estimate()，请求 persist() 并记录实际结果；持久请求可被拒，不能阻止用户清缓存、隐私模式清理或硬件故障。低剩余空间分级提醒，QuotaExceededError/写盘失败立即显式告警；不得自动清理尚未得到服务端持久确认的块。已确认的本地数据按企业保留政策清理，待上传数据单独提醒用户，不用 LRU 静默删除。恢复需要同浏览器/同源且存储仍存在；换设备只能获取已上传部分。

同源 Web Locks 协调唯一采集方，BroadcastChannel 同步其他页状态；服务端 capture_epoch/fencing token 拒绝过期采集方。恢复旧epoch补传不是允许旧token继续采集：新的恢复所有者从服务端获得仅限指定旧epoch/缺失序号范围的restore authorization，hash幂等补传，不能追加新的采样块。真正继续录音建立新epoch与采集授权。令牌刷新不创建第二场会议。导航可切页，关闭或强杀后重新开页只能恢复已存音频并重新请求麦克风，不能补录关闭期间的声音。

### 3.3 云端确认与补传

归档通过独立 HTTP 上传，不依赖实时 ASR WebSocket 成功。块主键为 `(tenant, meeting_id, capture_epoch, seq)`：同 hash 重试返回既有结果，不同 hash 冲突返回 409 并报警。服务端校验 payload_len/hash/sample 范围后写私有小对象，再提交 durable manifest；仅在约定持久层成功、manifest 可恢复时 ACK。对象写成功而数据库失败允许幂等重试，定期 reconciliation 清理孤儿对象；数据库不得先把尚未持久成功的对象标完成。对象覆盖策略与存储成功语义在选定供应商部署中验证。

每块可有独立 ACK，首页“已完整保存到”只使用最高**连续**确认水位；不能拿最大的 seq 掩盖中间缺块。查询接口同时返回 missing_ranges、acknowledged_ranges、gap_map 与连续水位；既计划暂停又真实丢失时，UI 不能都写成“完整录音”。

| 指标 | 业务意义 |
|---|---|
| captured_sample_end + 最近采样心跳 | 实际采到的位置；心跳冻结时采集可能已中断 |
| local_durable_sample_end | 此前连续块已满足本地持久条件 |
| cloud_contiguous_durable_sample_end | 此前连续块已满足服务端持久条件 |
| asr_processed_sample_end / estimated / unknown | 提供商实际支持的处理水位；文字时间戳不能假充全量音频 ACK |
| captured − local durable | 进程崩溃下已知尚未本地落盘尾部，按采样率转秒 |
| captured − cloud contiguous durable | 设备损坏下尚未服务端持久区间；另保留离散缺块 |
| gap duration / dropped frames | 采集停摆/队列溢出的真实缺失，不由两个保存水位差代替 |

重连先获取服务端 manifest，按缺块范围补传本地完整记录，hash 去重，按采样位置恢复回放。每个epoch内部水位映射到统一meeting时间线，暂停和真实gap分别保留；总已保存音频时长由已持久区间并集计算，不把包含暂停/缺口的最大时间戳当累计时长，不用不同epoch的sample数直接相减。服务端可快速接受归档补传；ASR 音频发送按厂商实时节奏另行处理。停止顺序为：停采集 → flush 尾块 → 等待/记录缺块 → seal manifest → 验证采样数/解码/缺口 → 发起会后转写与文档作业。云端尚未追平时允许保存本机会议并返回历史恢复入口，明确“待补传”，不能虚报完成。

1 秒 32 KB 的 PCM 块不能直接作为普通 S3 multipart part（通常最小 5 MiB，末块除外）。基础实现采用独立小对象/持久块接收，异步合并回放文件；聚合 5 秒只可 ACK 已实际持久的范围，不能对未上传 4 秒称逐秒上云。tus 可用于大文件导入/续传底座，仍需业务采样时间线、hash 与会议版本协议。S3 multipart 记录 upload_id/part/ETag 并清理超时未完成上传；ETag 不通用等于整文件 MD5。

### 3.4 背压、降级与故障边界

监控 Worklet/Worker 队列、写盘延迟、WebSocket bufferedAmount、未上传秒数、ASR 延迟；所有内存队列有限。网络慢优先保存音频，字幕可延后；本地处理或空间不够时明确中断/安全停止，不静默丢帧。溢出写 dropped_frame_count 和缺口。设备被拔出、权限撤回、AudioContext interrupted、track ended/mute、visibilitychange、采样心跳消失均产生事件。Wake Lock 是可释放的前台辅助，PWA/Service Worker 不能保证后台麦克风持续运行。

MediaRecorder 仅作为经测试 MIME 的兼容路径；timeslice Blob 可能不能独立播放，必须保留首块、所有 seq 与 mimeType，完整结束后组合/校验。崩溃尾流需 remux/解码验证，失败必须标恢复不完整。频繁 stop/start 的独立文件法可能产生边界空隙，不作默认路径。兼容录音未经同等验证不得套用主路径恢复指标。

| 支持矩阵初稿 | 上线门槛 | 产品表述 |
|---|---|---|
| Windows Chrome/Edge 前台 | 60/120 分钟、断网、强杀、设备切换与存储故障通过 | 优先支持；记录实际浏览器/设备版本 |
| macOS Safari 前台 | 同上，另测 AudioContext 中断/恢复及实际 MIME | 通过后列入支持 |
| Android Chrome 前台 | 温升、电量、蓝牙切换、来电、锁屏与系统节电测试 | 前台支持待测；锁屏时提示可能停止 |
| iOS Safari 前台 | 短时及长时、来电/离页/锁屏/恢复测试 | 前台支持待测；后台不作持续保证 |
| 微信等内置浏览器 | 独立 PoC，不能继承系统浏览器结论 | 未验证设备引导打开受支持浏览器或导入录音 |

不承诺“永不丢失”或“任何异常最多丢 1 秒”。可设置指定设备前台、容量充足条件下 p95 本地未持久尾部 ≤2 秒的待验收目标，并测实际分布；硬件断电/OS 强暂停/用户清理的范围单独说明。采样停止时两个水位一起冻结，其差为零也不代表现场声音没有缺失。

## 四、实时 ASR 与文本版本

后端 ASR adapter 统一 ingest PCM、发包节奏、会话握手、热词、partial/final 事件与样本位置映射；长期供应商密钥不进入浏览器。云方案先对比阿里/腾讯/火山的同一现场语料，选一家上线，不预设准确率/价格赢家。FunASR 2pass 私有化另做 CPU/GPU/模型许可/远场 PoC；代码许可不能概括全部模型。

断线归档继续本机保存。ASR 重连按厂商要求新 provider_session_id，并记录会议 sample offset；积压过去音频转独立补识别/文件任务，不盲目十倍速灌入 live session。有限上下文重叠以音频时间区间去重，不按相同文字删真实重复发言。provider session 的 speaker_0 不跨会话自动认同一人；会后全局分离或人工映射，不能凭声线推断身份或决策权。

| 文本对象 | 保存/显示行为 |
|---|---|
| 原始厂商事件 raw | 追加保存原响应、provider session、时间映射，供复核 |
| 实时 partial | 同 segment_id 替换，弱化显示；不是事实定稿 |
| streaming_final | 本厂商本会话句子稳定；不等于甲方已确认 |
| postprocessed_final | 会后完整音频识别、标点、术语与说话人校正的新 revision |
| human_corrected | 人工修改人/时间/差异/理由；保留前版本与原音 |

会后 ASR 不破坏性覆盖人工校对，采用版本差异合并。根据最近已选/确认转写 revision 生成文档；人工改稿使关联旧产物显示“来源已更新”，不静默改旧 PDF。未听清、否定条件、数量、金额、日期与权限是重点核对字段。会议内 AI 可给追问建议，必须标建议且频率可控；每个字不触发 LLM 调用或弹窗，不影响录音主链路。

## 五、产品库与受控 Agent 文档生产

### 5.1 产品事实不是普通知识切片

产品库保存企业真实产品、有效版本、已核实能力、限制、集成条件、交付方式、资料出处与授权。资料入库先保存不可变原件/校验和，然后解析/定位/审核/索引。Docling 保留文档 JSON 和页码/坐标；XLSX 专用读取保留工作表/单元格和必要公式语义，不能因通用解析器支持 XLSX 就宣称完全保真。产品资料中的指令只作材料，不能改变工具权限。

| 业务实体 | 核心字段 |
|---|---|
| Product、ProductVersion | 产品、厂商、所有者、状态、版本、生效期、审核记录 |
| Capability | capability_id、版本、功能、核实状态、实现方式、输入、限制、验收、证据、核实人/时间 |
| ProductDocument、Chunk | immutable revision、hash、原件 key、页码/坐标/表格位置、解析器版本、全文/向量、ACL |
| CommercialTerm | 版本、地区、币种、生效期、审批、面客报价/内部成本受众区分 |
| ProductCapabilitySnapshot | 某次文档包实际采用的产品版本、能力、限制与证据的不可变副本 |

关键词、向量、重排都先限定服务端会话确定的 tenant/project/product/document 允许集合；可采用 SQL/RLS 硬隔离。索引召回后再次 join 权威权限/有效版本表，在进入模型前重新过滤；来源补全、缓存、预览、导出与下载同样校验。重排不能召回越权文本，提示词“不要泄密”不算权限。中文关键词分词、产品型号、版本号、专业缩写与近义语义使用实际资料离线评估；embedding 模型/版本写入索引，变更重建而不混算。

匹配状态固定为“可满足 / 有前提 / 需定制评估 / 不支持 / 待确认”。规划能力不能写“已有”，接口开放/授权未知不能写“已对接”。价格、时间、硬件精度只能引用有效授权证据或明确待确认。客户诉求即便不支持也保留清单与核查去向。

### 5.2 明确节点与一次冻结输入

长会按模型真实token预算分段，每个segment有唯一主归属和coverage manifest，重叠上下文不重复算需求。完整会议抽取必须遍历全部有效段，不能只top-k检索或截前N字却声称生成完整需求；结尾决定、否定、例外和后文修正都保留。RAG用于产品库和来源回查，不替代会议全量抽取；合并校验覆盖范围与未处理段，有缺段则明确标不完整并补处理。

| 工作流节点 | 输入与产出 | 质量约束 |
|---|---|---|
| 整理会议证据 | transcript revision / 速记 → facts/decisions/open questions | 每项保留来源、时间、身份与确认状态 |
| 提取需求 | facts → 稳定 REQ、条件/排除/依赖 | 不漏否定、数字；不加模板业务 |
| 核对范围 | 会议分期证据/冲突 → scope_mode | 默认单版；明确分期需要证据与人工确认 |
| 检索并核查产品 | REQ + 授权有效产品 → capability/evidence match | 限制、版本和不支持项一同返回 |
| 冻结底稿 | 人工选择/修改 → FactSnapshot + capability snapshot | 不可变输入，旧稿可重现 |
| 生成四类结构文档 | snapshot → minutes/proposal/requirements/client checklist | 共用编号/范围/数字；遵守完整框架与章节映射 |
| 一致性与规则检查 | 四类结构 → errors/warnings/coverage | 程序计算，禁止编造分期/承诺/成本；有界修复 |
| 人工确认 | 差异/来源/待确认 → review record | 销售确认不冒充甲方确认，不扩张工具权限 |
| 导出 | 固定修订 → MD、纪要 PDF、可选文件 | 同内容版本，失败独立重试 |

Agent 使用明确有界图，长会议按稳定分段抽取再合并，章节改动重算依赖节点。每次模型调用保存模型/参数/提示词模板版本与输入引用；设置调用次数、token、超时和最多修复次数，耗尽返回具体问题而非无限循环。PoC初稿策略：每次作业最多20次模型调用，规则修复最多2轮，单调用90秒超时，累计执行deadline 15分钟；总token/货币预算按所选模型计价配置，未配置硬预算不允许启用生产生成。长会超预算拆为有编号的独立抽取子作业并先估量，不能绕过父级总预算。上述是待调优门槛，不是15分钟生成承诺。Pydantic验形状，引用检查和人工核查验事实；格式正确不等于内容真实。

LangGraph 使用持久 PostgreSQL checkpointer，重要节点采用 sync durability，人工确认通过 interrupt持久暂停并释放worker，不为人工等待占连接或轮询worker；恢复由授权确认事件触发。执行deadline不计人工等待，但人工等待期限初稿7天，过期标待重新确认而非自动批准。重放节点可能重复模型/API调用，所有副作用配 `operation_id` 和业务结果复用。业务变更与 outbox 事件同事务提交；投递可重复，worker 检查幂等键并持久写结果，不宣称跨模型、DB、对象存储 exactly-once。取消是 `cancel_requested`，已开始调用可能完成，最后持久确认后标 canceled；检查节点边界停止新增调用，旧输入任务不得写入新的当前修订。

FactSnapshot 固定 meeting/transcript revisions、manual notes、source evidence、product capability snapshot、format/rule/template revision、scope_mode 与确认记录。DocumentBundle 绑定 snapshot，各文件记录 generator/renderer/font hash；产品新版本到来不改旧文件，只提示重生。总体框架、建设清单、数据来源、业务流程、实施、交付、验收、甲方配合和风险通过需求依赖表共同校验，不能只局部加一节。

## 六、数据与 API 契约

### 6.1 权威业务表与状态

| 表/对象 | 核心关系与约束 |
|---|---|
| tenant、user、project、membership | 所有会议、产品和附件拥有可验证归属 |
| meeting | 客户、主题、Asia/Shanghai 日期、参与者确认、状态、当前 revision |
| recording_session / capture_epoch | 设备/采样配置、唯一所有者、fencing、暂停和缺口 |
| audio_block / recording_manifest | 唯一块键、hash、sample 范围、存储状态、连续水位、sealed 状态 |
| transcript_event / revision / segment | raw/live/final/human 分层，来源音频范围、说话人映射、编辑记录 |
| evidence / fact_snapshot / requirement | 出处、事实/建议/未知、确认人，稳定 REQ，当前与历史快照 |
| product tables / capability_snapshot | 有效产品与不可变文档包依据 |
| document_bundle / revision / block | 四类结构树、章节依赖、模板与范围，旧版本保留 |
| job / operation_result / outbox | leased worker、心跳、attempt、幂等、重试时间、错误分类 |
| export / artifact / audit | MD/PDF key/hash/版本、下载授权、确认与访问审计 |

meeting 可经 draft → recording/paused → ending → saved_pending_upload/processing → ready；需要异常状态 interrupted 或 recovery_required。录制、存储、ASR、文档作业分别有状态，不压成一个“处理中”。文档 draft/reviewed/approved/superseded 与任务 queued/running/waiting_review/succeeded/failed/canceled 区分。缺口不能被 ready 自动抹去。

### 6.2 接口草案

接口是后续契约，不是已运行 API。所有 id 校验归属，变更采用幂等键和 revision/If-Match 冲突检查，服务端从身份注入 tenant。WebSocket 短期会话 token 过期能重新鉴权。

| 接口 | 用途与必要返回 |
|---|---|
| POST /meetings | 创建会议；返回 meeting_id/revision、权限 |
| POST /meetings/{id}/recording-sessions | 建立采集 epoch、fencing、配置和短期 token |
| WS /recordings/{id}/live | ASR 小帧与 transcript/status 事件；不承担归档 ACK |
| PUT /recordings/{id}/epochs/{epoch}/blocks/{seq} | header+PCM+hash；返回块持久状态/连续水位；同键异 hash 409 |
| GET /recordings/{id}/manifest | 已确认范围、缺块、gap_map、sealed、连续水位 |
| POST /recordings/{id}/seal | 固定 final sample/seq，核对缺块；缺失不虚报 complete |
| GET /meetings/{id}/events?after=cursor | 事件恢复；cursor 持久、去重，不能只靠内存 SSE |
| POST /meetings/{id}/transcription-jobs | 会后校正/补识别，异步 job |
| PATCH /transcript-revisions/{id}/segments/{segment} | 校对生成新修订、保留原文、并发冲突响应 |
| GET/POST /products；POST /products/{id}/documents | 产品管理/原件上传/解析任务，版本和 ACL |
| PATCH /capabilities/{id}/verification | 授权人员核实能力/证据/限制，审计 |
| POST /meetings/{id}/document-bundles | 固定转写/产品/规则，创建 FactSnapshot 与生成 job |
| PATCH /documents/{id}/revisions/{revision} | 编辑、依赖章节变更标记，不覆盖旧稿 |
| POST /document-bundles/{id}/review | 人工确认记录；甲方确认需明确主体与证据 |
| POST /document-revisions/{id}/exports | format/template 形成幂等 export；重复返回相同任务 |
| GET /jobs/{id}；POST /jobs/{id}/cancel | 持久状态/进度/错误/可重试；取消异步确认 |
| GET /artifacts/{id}/download | 权限校验/短效下载/审计；object key 本身不是授权 |

WebSocket 事件至少带 event_id、meeting_id、provider_session_id、segment_id、revision、sample_range、kind 与时区映射。raw provider 事件敏感存储，客户端只接业务投影。历史页面刷新从数据库恢复，同任务只补订阅不重新生成。

## 七、PDF 与多文件一致性

MinutesDocument 是带稳定 block ID 的结构树，含会议基本信息、参与者确认状态、录音完整性、现状痛点、需求约束、决定、待确认、行动项与来源索引。MD renderer 与安全 HTML renderer 读取同一树；不能两个模型各写一遍。PDF 导出幂等键由 `revision + format + template + renderer + font_bundle_hash` 构成，持久任务 queued/running/ready/failed，检查有效文件后才 ready。

| 排版/下载事项 | 必须实现 |
|---|---|
| 页面与字体 | A4；上 2.5cm/下 2.3cm/左右 2.5cm；正式文档按黑体/宋体/Times New Roman及源规范字号；字体许可、来源、嵌入和 hash 登记 |
| 字体缺失 | 不静默替换并称符合规范；合法部署指定字体，或明确提出替代字体待接受；Web 字体与文档独立 |
| 跨页 | 表头重复；普通行尽量不拆；过高行拆续表并保留 REQ；避免整长表禁止分页导致空白 |
| 标题与图 | 标题随下段、图前引导与图题；SVG/PNG 本地静态化；页码和总页数正确 |
| 页眉页脚 | Playwright 模板独立样式，不假定继承正文 CSS；为页眉页脚预留边距 |
| 安全资源 | 文本净化/转义，禁任意远程请求；只加载受控本地字体/图；等待字体 ready/图解码 |
| 校验 | 提取 PDF 关键文本、数字与编号同结构树比对；逐页渲染检查缺字/裁切/孤题/空白，模板变更重复验证 |
| 下载 | 生成/查询/下载均校验会议权限；私有对象、短效签名或鉴权代理；PDF不含token/内部成本。已有签名URL可能在到期前继续有效，需要即时撤权的场景采用鉴权代理/网关检查，不能只撤数据库权限就声称旧URL失效 |
| 失败 | 保留 MD/结构树；字体或资源错误可理解，允许同版本重试，不重跑整个 Agent |

正式售前方案仍是“结构底稿 → 按规范 DOCX → Word 审核 → 已审修订转 PDF → 逐页检查”；python-docx 不是 PDF 引擎。目标 Word/LibreOffice 转换环境分别验证目录、字体和分页。当前用户要求的纪要 PDF 可从明确讨论稿/已确认纪要直接导出；下载不等于甲方批准。

清单 XLSX 扩展与 MD 共用稳定行数据：主清单、权限专项、回收统计、填写模板按编号关联。宽表拆表不能丢字段，公式与下拉状态验证实际样板；回收率、规则确认率和开工条件分别计算，不把资料已提供等同规则已确认。

## 八、容灾与验收

本节是开发验证计划，没有本轮已通过的录音/模型/PDF测试。每次测试保存设备/浏览器版本、场景、录音 hash、预期采样数、manifest、恢复日志、缺口与耗时，以证据决定上线支持范围。

| 场景 | 可审阅通过依据 |
|---|---|
| 60/120 分钟连续录音 | 采样时长一致、可解码、无未知缺块，写盘/队列/温升数据完整 |
| 断网 60 秒与 10 分钟后恢复 | 本地完整块继续，缺块幂等补传，连续服务端水位追平，无重复音频 |
| ACK 丢失/重复/乱序、服务端重启 | 同 hash 复用；不同 hash 冲突拒绝；最大 seq 不掩盖中间缺块 |
| 浏览器强杀/刷新/断电模拟 | 扫描恢复所有完整已提交块，截断尾块明确，实测尾部损失而非预设保证 |
| OPFS 与 IDB 不一致 | 日志重建索引、孤索引不会假报完整，恢复 hash 校验 |
| 配额满/写盘慢/Worker 阻塞 | 明确告警或安全停采，溢出有缺口事件，无静默丢帧 |
| 设备拔出/权限撤销/蓝牙切换 | 停采与采样心跳可见，新 epoch 继续，时间轴不伪连续 |
| 来电/后台/锁屏 | 记录真实暂停、告警与恢复；未通过设备不宣传后台录音 |
| 多标签竞争/旧 owner | 唯一采集方、过期 fencing 拒绝，不产生重复 seq |
| ASR 断线/限流/过期 | 录音独立存，厂商新会话及偏移正确，积压独立补识别 |
| 转写校正/人工修改 | raw/live/final/human 可追溯，重识别不覆盖人稿 |
| 产品检索与事实 | 型号/版本/否定/限制检索，未核实不承诺，所有关键结论能打开出处 |
| 跨租户/权限撤销 | 搜索、缓存、模型上下文、引用、作业和下载均拒绝越权 |
| 生成崩溃/重复投递/人工续跑 | checkpoint 恢复，副作用去重，重复导出同版本，旧任务不覆盖新稿 |
| 文档内容 | 无分期证据时全产物单版；否定/数字/条件不丢；框架章节与四文档一致 |
| PDF | 长中文/长表/图片逐页可读；字体合规可用，MD/PDF同版本，失败仍可下载MD |
| UI | 四页导航、保存状态区分、读历史不被滚动抢位、键盘/对比度/移动前台验证 |

优先收集授权现场样本，包含远场、噪声、多发言、产品名、金额、否定与权限要求；人工基准评测字错率、关键字段错漏、校对时间、需求召回与产品证据正确性。结果是模型选择依据，不能变为面客“AI文字准确率承诺”。

## 九、开发顺序、成本与待确定决策

按照先保存证据、再生成文档的顺序实现；每一步有可审阅产物，未通过的基础能力不能被华丽 UI 遮盖。以下是工程工作包，不对应客户项目分期。

| 顺序 | 工作包 | 进入下一步的门槛 |
|---|---|---|
| 1 | 真实样本/设备矩阵、云 ASR/FunASR、OPFS/IDB/PDF 字体 PoC | 确认支持设备、采样协议、持久边界、字体来源和供应商 |
| 2 | 四页壳/设计系统、鉴权、客户项目、音频持久与补传 | 断网/强杀/配额/ACK故障证据通过 |
| 3 | 实时 ASR、时间轴、回放、人稿修订、历史 | 完整转写版本及中断恢复可解释 |
| 4 | 同底稿纪要 MD/PDF、长表分页、导出任务 | 会后校对与纪要下载闭环、同版本比对及逐页验证通过 |
| 5 | 产品入库/版本/核实/权限混合检索 | 真实检索集与越权用例通过 |
| 6 | FactSnapshot、LangGraph、方案/需求/甲方清单、规则与人审 | 会议事实/产品能力/默认单版/跨章节检查通过 |
| 7 | 配额/保留/备份/观测、移动前台与负载 | 恢复演练、实际成本和支持矩阵发布 |

16 kHz 单声道 PCM16 的一小时纯音频是 115,200,000 bytes，即 115.2 MB / 109.86 MiB；两小时 230.4 MB / 219.73 MiB。还需索引、队列、导出和可能的临时副本，不能沿用旧 100 MiB 一小时总额度。建议一小时标准归档逻辑配额初稿 256 MiB，双小时初稿 512 MiB；**逻辑服务端配额不等于本机有此可用空间**，本地根据估算容量和实际复制数预检。压缩音频、原生多声道与保真备份分别计费/限制；具体策略待真实资源与保留政策确定。

| 成本项 | 计算方式/取舍 |
|---|---|
| ASR | 实时分钟 + 会后重转写分钟 + 增值能力；不能忘记第二次识别开销 |
| 模型 | 分段提取/产品匹配/四稿/修复输入输出 token；限制上下文与重复调用 |
| 对象存储 | 音频总字节×保留期、冗余、PUT/GET、下载流量；1秒小对象约3600 PUT/小时 |
| DB/检索 | 事件、块索引、checkpoint、向量与审计；比较聚合与可见保存延迟 |
| 私有 ASR | GPU/CPU时长、峰值容量、模型许可与运维；未实测不能说必然便宜 |
| PDF | Chromium worker 并发/内存、合法字体、逐页检查与缓存 |

仍需在开发准备中确定：部署地域与客户数据授权、ASR/模型账号合同与预算、真实产品材料/可见范围、会议与本地缓存保留时间、审批角色、峰值并发、实际支持设备及指定字体的部署许可。先用样本和资源测量收敛这些选择；本次架构已具备独立实现与评审所需边界。

## 十、最小权限、保留删除与备份恢复

| 权限/数据生命周期 | 设计规则 |
|---|---|
| 账户与工具 | 角色区分销售、产品核实人、审阅人、管理员；按项目成员授权，工具tenant/project由服务端注入；管理员权限不默认授予模型 |
| 密钥与网络 | ASR/LLM长期密钥由服务端密钥配置提供，不入浏览器/文档/日志；工具只调用固定授权服务，输出模板renderer禁止任意外链请求 |
| 模型与追踪 | 模型/ASR数据地域和合同核实；原始音频/全文不得默认发到未批准tracing或分析服务，日志最小化且脱敏 |
| 保留初稿 | 原音建议30天，转写/事实/文档建议180天，滚动备份建议30天；均为待数据责任人按用途/客户授权确定的策略，不自动开通永久保留 |
| 本地副本 | 待补传不自动清理；已上云副本按配置期限清理并让用户知道；共享设备退出时提示未上传草稿，清理操作不能伪装上传完成 |
| 删除流程 | 授权删除立即撤可见性/新下载，写删除tombstone及审计，异步清理音频/原件/向量/派生文件/缓存/checkpoint敏感内容；有法定保留单独记录依据 |
| 备份删除边界 | 说明备份轮换保留窗口；恢复后重放tombstone/权限撤销后再开放访问，不能从备份把已删客户资料重新公开 |
| 备份与灾备 | 数据库+对象manifest/版本映射一致恢复，定期试演音频与文档hash核验；账号/签名权限也恢复正确，记录实测RPO/RTO |
| 审计 | 记录确认、导出、访问、删除与规则/产品变更；限制审计读权，不在审计复制凭证/全文客户材料 |

客户现场录音须有业务上适当的说明/授权入口，浏览器麦克风权限不是客户对AI处理的确认。部署时按企业实际数据政策配置保留和删除，不由Agent自主决定。
