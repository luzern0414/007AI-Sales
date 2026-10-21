# Web 销售助手：实时会议录音、转写与断点恢复调研

调研日期：2026-10-15，Asia/Shanghai。范围：客户现场会议优先；手机/电脑前台麦克风为主；线上会议声音为可选入口。本文是架构研究，不是已经实现或实测的产品能力。Firecrawl CLI 的本地缓存依赖损坏，`npx --yes firecrawl-cli@latest --status` 返回 SyntaxError；采用官方站点/项目原始源码的直接 HTTP 读取，缓存统一在 `.firecrawl/20261015-audio-*`。共读取 46 个成功的官方 URL，另有 12 个 HTML 的 txt 派生文件（不将派生文件计为来源）。所有 GitHub main/master 来源会变化，实施时应固定 commit、依赖和模型版本。

## 1. 现场会议的浏览器采集主路径、兼容边界如何确定？

### Takeaway

建议把“AudioWorklet 捕获 → Worker 转换和持久化固定 PCM 块 → 实时 ASR 与云端归档两条独立消费路径”作为主架构。MediaRecorder 可作压缩录音和兼容采集路径，但其 timeslice Blob 不能直接等同于独立可播放文件，也不能据此承诺崩溃时只丢最后一秒。

### Cited Findings

- `getUserMedia()` 获取用户授权的麦克风 MediaStream，需要安全上下文；权限拒绝、无设备和设备读取失败应作为正常产品状态处理。— [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- AudioWorklet 在单独的 Web Audio 线程执行音频处理，面向低延迟；MDN 标注为跨主要浏览器广泛可用，自 2021 年 4 月起进入该范围。— [MDN AudioWorklet](https://developer.mozilla.org/en-US/docs/Web/API/AudioWorklet)
- MDN 浏览器兼容数据库记录 AudioWorklet：Chrome 66、Firefox 76、Safari 14.1 开始支持；MediaRecorder：Chrome 47、Firefox 25、Safari 桌面 14.1、iOS Safari 14 开始支持。这些是 API 存在的历史证据，不代表每个编码、设备和持续录音场景已兼容。— [AudioWorklet BCD](https://github.com/mdn/browser-compat-data/blob/main/api/AudioWorklet.json)、[MediaRecorder BCD](https://github.com/mdn/browser-compat-data/blob/main/api/MediaRecorder.json)
- W3C 录音规范明确：由于 timeslice/requestData 返回的各个 Blob **不一定可播放**；只有一次已完成录音所产生的全部 Blob 的组合必须可播放。不能把未完成、浏览器崩溃的录音等同于 completed recording。— [W3C MediaStream Recording](https://www.w3.org/TR/mediastream-recording/)
- `dataavailable` 的 timeslice 并不精确；Safari 可能暂停摄像头/麦克风，Chrome Android 锁屏可能暂停 dataavailable 事件，导致间隔延迟、单个 Blob 明显变大。MDN 明确要求不要用“块数 × timeslice”计算录音时长。— [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event)
- MediaRecorder 支持 `isTypeSupported()` 检查 MIME；编码/容器仍应运行时探测，不能所有浏览器硬编码 `audio/webm;codecs=opus`。— [MDN MediaRecorder](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder)
- AudioContext 可能因为电话/会议应用争用音频设备、合盖、系统中断而进入 interrupted；iOS Safari 离开页面、最小化浏览器或锁屏会进入 interrupted，需要恢复处理。— [MDN AudioContext.state](https://developer.mozilla.org/en-US/docs/Web/API/AudioContext/state)
- Screen Wake Lock 可以阻止可见、活动页面的屏幕变暗/锁屏，但系统可释放锁，后台页面不能据此获得持续运行保证。— [MDN Screen Wake Lock](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API)
- `getDisplayMedia()` 获取屏幕/窗口/标签页共享，要求视频轨道，即 `video:false` 会失败；音频是可选的，系统音频支持受浏览器、操作系统和共享目标约束。`systemAudio:include` 只是提示，返回流仍可能没有音轨；每次需要用户交互授权。— [MDN getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)
- 当前 BCD 中 Chrome Android 和 Firefox Android 的 getDisplayMedia 支持值为 false；不能将桌面屏幕声音入口作为手机基础能力。页面记录的 Safari iOS 版本信息与实际用户安装版本可能不同，应按目标设备实测，不能仅照抄兼容表宣称可用。— [MediaDevices BCD](https://github.com/mdn/browser-compat-data/blob/main/api/MediaDevices.json)
- Web Speech 的 SpeechRecognition 被 MDN 标注为 Limited availability；部分浏览器（如 Chrome）使用服务端识别，离线不可用。它不替代产品自有录音归档、恢复和审计链。— [MDN SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition)

### Inferences

**建议主链路（设计选择，尚需 PoC）：**

1. 首页由用户点击“开始会议”获取麦克风；默认现场麦克风，显示输入设备、音量、录制时长、录音/本地保存/云端保存/转写四种独立状态。
2. AudioWorklet 只捕获音频帧、读取采样计数和将数据送往有界队列，不在音频实时线程内进行网络或存储 I/O。使用 Worker 做声道处理、校验、编码、归档和上传；避免 UI 渲染阻塞采集。主线程消息转发也应可监控；SharedArrayBuffer 方案需要额外跨源隔离配置，不作为基础浏览器门槛。
3. 读取实际 AudioContext sampleRate，不能假定采样率请求一定满足。Worker 用有状态、带抗混叠低通的重采样器把连续音频转成配置目标（建议 ASR 标准流 16 kHz、单声道、PCM16），维持分块间滤波状态，不能“每三个样本取一个”代替重采样。
4. ASR 使用约 100–200 ms 的小帧；持久归档初始建议按约 1 秒形成自描述块，字段至少含 session_id、capture_epoch、seq、source_sample_rate、output_sample_rate、channel_count、sample_start、frame_count、PCM 编码、payload_len、SHA-256、前后块关系。块时长与刷盘间隔是不同参数，需由实测确定。
5. 同一份规范 PCM 块同时供实时识别与归档。若采用“16 kHz 单声道 PCM16”作为标准归档，每小时是 `16000 × 2 × 3600 = 115,200,000 bytes`，约 **115.2 MB / 109.86 MiB**；两小时约 **230.4 MB / 219.73 MiB**。这只是纯音频负载，还需索引、缓冲、上传副本和安全余量。48 kHz 单声道 PCM16 则为 345.6 MB/h。旧文档的 100 MiB 总限额不能直接套到一小时 PCM 会议。
6. 标准语音归档与“设备原生采样率原音保真备份”分开标注。经重采样/降为单声道的录音不能宣传为原始无损音质；如果保留多麦克风/原生声道，容量需单独计算。说话人分离也不能将单麦克风声道直接映射成每个人。
7. 直接 PCM 块无需依赖 WebM/MP4 的尾部索引，恢复时能根据编码参数独立封装成 WAV 或重新编码为 FLAC；跨采集 epoch、暂停/中断的块按时间线拼接并保留 gap_map。不要把缺失间隔悄悄拼成连续发言。
8. Worker/AudioWorklet 不可用或目标设备 PoC 不通过时，走 MediaRecorder 的已验证 MIME 路径，按 seq 保存全部 Blob、首块和 mimeType；服务端尝试 remux/恢复并验证可解码性。若没有经过崩溃恢复验证，UI 必须将其称为“兼容录音，恢复能力受浏览器影响”，不能套主路径的损失目标。
9. 如必须通过 MediaRecorder 获得每段独立文件，可评估短周期完整 stop/start（每段正常结束）或专门独立封装编码器，但 stop/start 可能造成边界空隙，需要测量，不能先认定无缝；不建议为了伪装固定 1 秒独立文件而频繁重启 Recorder。
10. 手机产品定位为“前台录音”。监听 AudioContext statechange、track ended/mute、devicechange、visibilitychange 与采样心跳；中断时立刻显示/记录缺口并尽可能恢复。PWA、Wake Lock、Service Worker 都不构成手机锁屏/来电时持续采集的保证。用户强依赖后台录音时，应评估原生 App/桌面客户端或独立录音器导入路径。
11. 桌面线上会议可选“麦克风 + 共享标签页/屏幕声音”，启动后检查实际 audio track；没有远端声音就明确提示并提供导入音频入口。需要避免回声/重复输入，混音前保留来源标识；不假设网页能静默读取腾讯会议、飞书或所有系统声音。

### Gaps

- 尚未在真实 Windows Chrome/Edge、macOS Safari、Android Chrome、iOS Safari 对 2 小时连续录音、后台/锁屏、来电、蓝牙切换、低电量、设备拔出做 PoC；API 支持不等于可靠持续录音支持。
- 1 秒归档块、本地刷盘和 UI 进度的尾部损失目标是待测指标，非已验证上界；Android/iOS 不同厂商和系统版本仍需设备矩阵。
- 浏览器音量显示不能证明麦克风在物理上录到了所有与会者。远场、重叠发言、房间混响应通过真实会议样本和外接麦克风测试。

## 2. 如何把实时保存、断点续传、转写修订做成可验证的恢复协议？

### Takeaway

录音持久化、云端持久化和 ASR 已处理是三个不同进度。必须以音频采样时间线与块 manifest 为恢复事实来源，保留离线待传队列；实时文字只用于会议中查看，会后建议对完整归档做一次校正转写，再生成有证据引用的纪要/方案/需求清单。

### Cited Findings

- IndexedDB 用于浏览器大量结构化数据和索引；OPFS 提供 origin 私有、面向性能的文件读写，并能在 Worker 使用。— [MDN IndexedDB](https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API)、[MDN OPFS](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API/Origin_private_file_system)
- OPFS 同步访问句柄 `flush()` 在 Dedicated Worker 中可用，作用是把文件修改持久化到磁盘；不是每次 write 返回就已 flush。— [MDN flush](https://developer.mozilla.org/en-US/docs/Web/API/FileSystemSyncAccessHandle/flush)
- IndexedDB transaction 可指定 durability:strict，浏览器在确认更改已写到持久存储后才可视作提交完成；relaxed 可以在数据交给 OS 后即视为完成。需要特性探测和性能评估。— [MDN IDB transaction](https://developer.mozilla.org/en-US/docs/Web/API/IDBDatabase/transaction)
- IndexedDB/OPFS 等按 origin 共享配额，默认 best-effort；`persist()` 请求可以被批准或拒绝，隐私浏览通常会在会话结束时清理数据；配额用尽会抛异常。持久化请求不能防止用户主动清理或磁盘/设备故障。— [MDN quotas/eviction](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)、[MDN persist](https://developer.mozilla.org/en-US/docs/Web/API/StorageManager/persist)
- WebSocket API 本身不提供背压；发送端可读 bufferedAmount 看到队列字节，但要由应用自行控制内存和速率。— [MDN WebSocket](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- Web Locks API 可以协调同一 origin 多个标签页/Worker 对资源的访问。— [MDN Web Locks](https://developer.mozilla.org/en-US/docs/Web/API/Web_Locks_API)
- tus 通过 HEAD 查询 Upload-Offset，然后 PATCH 续传；偏移不匹配应返回 409，支持 checksum、expiration、concatenation 扩展，具体能力由服务端协商。— [tus resumable protocol](https://tus.io/protocols/resumable-upload)
- S3 Multipart 允许失败后只重传某一 part，完成时必须提交 part number 和 ETag 列表；上传未完成前不能当成一个最终可访问对象；未 complete/abort 的 parts 持续占用存储。ETag 不能普遍当成整文件 MD5。— [AWS multipart overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- 当前 S3 multipart 官方限制列出通常每 part 最少 5 MiB（最后一个 part 除外），每 upload 最多 10,000 parts。因此 1 秒 32 KB PCM 块不能直接逐块当作普通 S3 multipart part 上传。— [AWS multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)
- 阿里实时 ASR 分别返回 TranscriptionResultChanged（中间结果）、SentenceEnd（句子结束）和 TranscriptionCompleted（任务结束）；它们语义不同。— [阿里 WebSocket ASR](https://help.aliyun.com/zh/isi/developer-reference/websocket)
- 腾讯官方要求建议每 200 ms 按 1:1 实时率发送音频；速率过快或包间隔超过 6 秒可能使服务端报错断开。每次新连接必须新 voice_id，任何中断后不能沿用旧 voice_id；slice_type=1 是非稳态文字，2 是该句稳态文字。— [腾讯实时语音识别](https://cloud.tencent.com/document/product/1093/48982)
- 火山流式 ASR 推荐 100–200 ms 包，双向流式优化接口只在识别结果变化时回包，不能把“输入一帧”与“必然收到一帧回包”当成统一 ACK 机制。— [火山流式 ASR](https://www.volcengine.com/docs/6561/1354869)

### Inferences

**本地持久化协议：**

- 优先 PoC：AudioWorklet → Worker → OPFS 追加式自描述日志（块头 + payload + 校验 + 提交标记），按目标间隔 flush；IndexedDB 只存 manifest、进度和会话索引。因为 OPFS 和 IndexedDB 不是一笔跨存储原子事务，启动恢复必须扫描自描述日志、丢弃截断尾记录、校验 hash 并重建索引，不能仅信任索引完成标记。
- 更简单的备选：块 payload 与 metadata 同存在 IndexedDB 一笔 strict 事务，提交完成后推进 local_committed_seq。先验证目标浏览器 strict 支持及写入速度；不支持时应显示持久化降级状态。**request.onsuccess 不能直接当整笔事务已提交**。
- 内存队列与未 flush 数据不标成“已保存”。请求 persist()，记录实际返回值；调用 storage.estimate() 预估剩余空间，设置分级预警与硬阈值；捕获 QuotaExceededError。不可静默删除尚未获得云端持久确认的录音来腾空间。
- 一个 session 在同一 origin 只允许一个采集所有者，使用 Web Locks + 后端 capture_epoch/fencing token；BroadcastChannel 可以展示其他标签页的状态。服务端 fencing 是防止租约过期后旧标签继续写入的最终校验。录音标签关闭后，新标签只能恢复已保存数据并重新请求麦克风，不能补录关闭期间声音。

**云端协议：**

- 数据块主键 `(tenant, meeting_id, capture_epoch, seq)`，同时记录 sample_start/frame_count/hash/codec。重复同 hash 返回已存在；同主键不同 hash 拒绝冲突并报警。seq 连续不等于时间线连续，还需验证 sample_start 和 frame_count。
- 应用网关接收到 WebSocket bytes 后，可立即把数据转给 ASR，但该动作不代表云端归档已完成。`durable_ack` 只能在约定的持久层写入成功且块 manifest 可恢复后返回；部署若用服务端 append journal，需明确 flush、容灾和备份策略，不能把内存 Redis/pubsub/ASR 缓冲叫持久化。
- 建议基础实现使用独立小对象或持久分块接收服务，再异步合并成回放文件。小对象可按 1–5 秒聚合，但每次 ACK 要对应实际持久块范围；不能聚合 60 秒却 UI 宣称每秒上云。选择 1 秒对象每小时约 3,600 PUT，必须测请求、DB 索引和成本。
- tus 更适合恢复已存在/持续增长文件的字节上传，不能直接解决 PCM 时间线、会议分块幂等和 ASR 状态；可以用于导入大文件或作为归档上传底座。S3 multipart 适合较大合并文件；需记录 upload_id/part/ETag、清理过期未完成上传，不能每个小音频块盲用一个 part。
- 客户端 reconnect 先查询服务器缺块区间/最高连续 durable seq，重传本地持久队列；后端按 hash 幂等、按采样顺序拼接；token 过期只刷新鉴权，不生成另一场重复会议。
- 状态应分为 `captured_sample_end`、`local_durable_sample_end`、`cloud_contiguous_durable_sample_end`、`asr_processed_sample_end`。ASR 厂商没有给出某类处理水位时，该值标记 estimated/unknown，不能把文字最后时间戳当完整音频消费确认。
- UI“已保存至某时刻/已保存时长”必须使用 **连续确认水位 contiguous watermark**，本地和云端都不能拿最大 seq/sample_end 掩盖中间缺块。协议可以返回 per-chunk ACK 供重传优化，但“已完整保存到 15:30”必须证明此前对应时间线无未解释缺口；计划暂停另在 gap_map 标明，真实丢失不能算完整。

**实时 ASR 和会后校正：**

- ASR adapters 统一接收规范 PCM，但连接、采样率、发包速率、最大时长、热词和结果字段按提供商配置。浏览器只持平台短期会话 token，厂商长期密钥仅在后端。
- 断线时原归档继续存本地；重连录音云端可快速补传，但不能默认按 10 倍速度把过去音频灌给厂商 live session。后端将“当前实时流”与“积压区间补识别任务”隔离；厂商要求新 session 时生成新 provider_session_id，并保存它与 meeting sample offset 的映射。
- session reset 选择有限重叠上下文，并按音频时间区间和结果 revision 去重，不能只按文字相同删除，以免删掉真实重复话语。未赶上的积压转为离线识别；UI 显示“录音已保存，转写追赶中”。
- 文本模型至少分 `partial`、`streaming_final`、`postprocessed_final`、`human_corrected`。partial 同 segment_id 覆盖，不不断追加；streaming_final 仅表示厂商该次会话稳定，并不等于业务事实已核准。保留提供商原始响应、修改记录、词级时间戳（若有）。
- 原始提供商响应、实时字幕、会后校正、人工作品分版本保存，不相互破坏性覆盖。不同 provider session 的 speaker_id 通常仅在各自 session 内有意义；不能把 session A 的 speaker_0 与 session B 的 speaker_0 自动认作同一人，需会后全局分离或人工映射。
- 实时字幕可早于 1 秒归档提交显示，但它只是可重建的 projection：字幕出现不证明音频已持久化，ASR ACK 也不证明音频云端保存。录音归档连续性与明确 gap_map 才是恢复权威。
- 建议停止录音后：flush 本地尾块 → 缺块上传 → seal 完整 manifest → 音频可解码/时长/缺口校验 → 全量或按确定边界离线重转写 → 标点/说话人分离/产品术语校正 → 人工可校对 → 生成会议纪要 PDF、方案和需求清单。归档有 gap 必须让文档展示来源不完整提示，不能让 LLM 补成事实。
- 围绕最新已审核转写版本生成文档，引用 meeting_id + transcript_revision + 时间区间。人工修订后下游文档标“待更新”，而不是静默保留过时方案。全量重转写不能覆盖人工修改，应用差异合并。

**背压与可测损失：**

- 监控 Worklet→Worker 队列、存储提交延迟、WebSocket bufferedAmount、待上传时长、ASR 延迟；设有限内存。网络慢时优先本地归档，让实时转写延迟；超出本地空间/处理能力时提示并停止/切换，不静默丢帧。Worker 阻塞或 ring buffer overflow 必须产生缺口事件和准确 dropped_frame_count。
- `sample_clock` 用来描述真正采到的音频帧；`monotonic_clock` 描述进程内经过时间；墙钟用于会议日期。重启后 monotonic_clock 不能直接跨进程比较，因此用 capture_epoch + 稳定偏移映射。pause、系统挂起、设备故障分别记录 pause/gap 事件，不能插入伪造转写。
- 风险指标要分：①进程崩溃的未本地持久尾部 `captured_end - local_durable_end`；②设备损毁的未云端持久区间 `captured_end - cloud_contiguous_durable_end`；③采集停摆时的真实缺口 duration。①②以 sample_count/sample_rate 转秒，③不能通过“最后块仍在”掩盖。
- 若在浏览器冻结后无法采到新的帧，最后已知 captured_end 也可能落后于现实时间；UI 需展示最近采样心跳和已知中断时间，不能以两个冻结水位差为 0 宣称无丢失。
- 可以设“在指定前台设备、容量足够、无系统强制暂停条件下，实测 p95 本地持久尾部≤2秒”的**待验收目标**，不能承诺所有浏览器任何异常最多丢2秒；设备断电、OS缓存行为、用户清理和后台采集停止均超出绝对零损失保证。

### Gaps

- 未实现服务端 durable journal 或对象存储 ACK，本地严格事务/OPFS flush 的耗时、频率、电量消耗及强杀后的恢复成功率均未测量。
- 对象存储不同供应商的持久成功语义、S3兼容差异、区域恢复和费用需单独验证；不能由 AWS 文档推断所有“兼容 S3”供应商完全一致。
- 会议中说话人命名、多人重叠、热词导致误改、跨 session 时间戳偏移需要本项目样本集评估，不应先承诺字错率或时延数字。

## 3. 可选开源组件和中文 ASR 路线如何取舍？

### Takeaway

业务平台自己管理会议音频、文档证据和可靠性；ASR 通过 adapter 可替换。现场中文会议建议并行 PoC 一家国内云流式 ASR 与 FunASR 2pass，自建离线校正可采用 FunASR/faster-whisper；LiveKit/Pipecat 适合未来多人在线语音和语音对话，不是本次现场录音所必须的基础层。

### Cited Findings

下表为 **13 项候选**，含开源组件和商业接口。许可证从仓库 LICENSE 或模型卡直接核实；代码许可证不自动覆盖模型、训练数据、厂商 API 条款或托管服务。

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

### Inferences

- 推荐初始产品链路：Web前端负责采集/本地归档/恢复；业务API管理会议、产品库、文档任务；实时网关管理音频连接与ASR adapter；持久块接收服务和对象存储管理音频；后台任务做会后转写和文档生成。实时WebSocket连接与长耗时文档任务不要绑定同一请求生命期。
- 选择一条稳定云端中文实时ASR作为首先交付的识别能力，同时做FunASR 2pass的私有化样本PoC。用统一adapter而非每家都同时上生产。没有实测前不声称自建一定更便宜或中文一定更准。
- “会后校正”与“实时修正”可以同一供应商也可以不同模型；产品库中已确认的产品名、客户系统名和行业术语可供热词与校对，但禁止让LLM把未听清内容直接改为产品承诺。
- 生成会议纪要、售前方案和甲方资料/权限/规则需求清单时，使用已持久保存的转写revision、产品知识revision与会议约束。严格按用户现有规范：无分期要求就单版；参考材料只借结构，不能把参考ERP方案内容当本场会议已确认事实。
- UI首页录音区保持低饱和色，红色只用于正在录音/异常等必要状态；文本用“识别中”“该句已稳定”“会后校正完成”“人工已确认”区分，不用同一种绿色对勾混淆。录音页离开时显示剩余未上传时长与已本地保存状态，历史纪要页可找到恢复入口；最终PDF下载与原始录音下载是不同按钮。
- 验收建议至少包含：网络断10分钟继续录制并后续幂等补传、服务端重启/ACK丢失、前端强杀后仅恢复完整校验块、多标签竞争、配额不足、写盘变慢、ASR会话过期/限流、暂停恢复、设备切换、恢复片段ffprobe解码与采样计数对齐、缺口明确显示、会后文本revision不覆盖人工修订。标注这些是实施验收计划，非已执行测试。

### Gaps

- 未比较各云服务当前价格、并发采购和数据区域条款，也未执行客观中文字错率/热词/远场/重叠发言对比；推荐基于架构适配，不是性能排名。
- GitHub活跃分支、模型卡和厂商接口可能在实施前变更；所有候选需要固定版本、核对近期维护状态和模型许可后再选型。
- 未实现PDF/方案文档模块；其格式、分页、字体、表格和可下载性由主研究的文档生产架构负责，不能把浏览器录音能力推导成PDF已经可用。
