# 手机 Web 录音与中文销售访谈转写调研

调研基准：2026-10-12，Asia/Shanghai。
业务假设：软件公司售前，销售把客户访谈整理为需求，再生成可演示的业务系统。
本笔记只提供研究结论和设计建议，没有执行应用开发、依赖安装或模型部署。
事实、设计建议、待验证项分别列于 Cited Findings、Inferences、Gaps。
公开资料描述能力，不构成本项目的准确率、延迟、兼容性或采购价格承诺。

## 1. 手机 Web 怎样可靠地录音、上传与恢复？

### Takeaway

MVP 应以 HTTPS 页面在前台采集麦克风为入口，优先适配 iOS Safari 与 Android Chrome；微信内置浏览器单独做兼容性 PoC。
录音必须按完整流保留原始分片、顺序与最终片，不能把每个 MediaRecorder Blob 当成独立音频提交 ASR。

### Cited Findings

- `getUserMedia()` 访问媒体输入前需要用户授权；安全上下文才可用，在非安全页面中 `navigator.mediaDevices` 可能为 undefined。正式移动访问应使用 HTTPS。— [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- 本地开发的 localhost 属于安全上下文例外；手机访问电脑局域网 HTTP 地址不能简单套用 localhost 例外。— [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- `NotAllowedError` 可来自拒绝权限或非安全上下文；`NotFoundError` 表示没有匹配输入设备，硬件或系统层面的读取问题可产生 `NotReadableError`。— [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- iframe 需要顶层页面明确授予麦克风权限，单纯把录音页嵌在 iframe 中不能保证出现授权提示。— [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- WebKit 的历史公告说明 Safari 在 iOS 14.3 beta 阶段默认启用 MediaRecorder，当时支持 MP4 容器和 AAC 音频；该历史公告不能当作所有当前 Safari 的完整格式清单。— [WebKit MediaRecorder API](https://webkit.org/blog/11353/mediarecorder-api/)
- `MediaRecorder.isTypeSupported()` 可探测 MIME/编码支持，但返回 true 仍可能因资源不足导致录制失败。— [MDN isTypeSupported](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static)
- `timeslice` 不是精确调度周期：Safari 暂停麦克风、Android Chrome 锁屏暂停 `dataavailable`、任务阻塞等可延迟事件，产生较大的 Blob。— [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event)
- 因此不能按收到的 Blob 数量乘以 timeslice 计算实际录音时长，MDN 建议使用独立时间计量。— [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event)
- W3C 规范明确：timeslice 或 `requestData()` 得到的独立 Blob 不必可播放；完成录制后全部 Blob 的组合必须可播放。— [W3C MediaStream Recording](https://www.w3.org/TR/mediastream-recording/)
- 规范中的 `stop()` 先停止采集，再发送最后的 `dataavailable`，随后发送 `stop` 事件；调用 stop 返回并不表示最后一段上传已经完成。— [W3C MediaStream Recording](https://www.w3.org/TR/mediastream-recording/)
- IndexedDB 等默认采用 best-effort 存储，浏览器可因存储压力等条件回收；请求 persistent 存储可能被自动批准或拒绝，达到配额可能抛出 `QuotaExceededError`。— [MDN storage quotas](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- WebKit 公告指出 WKWebView 能否暴露 `getUserMedia()` 与宿主 App 的原生采集能力有关，宿主环境因此需要独立核验。— [WebKit MediaRecorder API](https://webkit.org/blog/11353/mediarecorder-api/)

### Inferences

以下均为本项目设计建议，并非浏览器或云厂商的功能承诺。

- 首页主按钮为“开始录音”；开始前选择客户/商机、确认参与者已知情，并展示麦克风权限提示。
- 麦克风录制是面对面访谈能力，MVP 不承诺采集普通电话、微信通话或其他 App 的系统音频。
- 当前支持范围先写为“前台录音，经测试的 Safari/Chrome 版本”；不能宣传锁屏、切后台持续录音。
- 微信内置浏览器作为候选入口：能力探测失败时提示使用系统浏览器，提供上传录音文件的兜底。
- 录音前探测 `getUserMedia`、`MediaRecorder`、`isTypeSupported` 与权限状态，拒绝权限后给出可操作引导。
- 可探测 `audio/webm;codecs=opus`、`audio/mp4` 等候选，不按 User-Agent 硬编码格式；记录实例最终 `mimeType`。
- 在目标浏览器中测试噪声抑制、自动增益、回声消除的效果，不把 constraints 的请求值当作实际采样规格。
- 浏览器保留原始容器格式；服务端完整合并后解码，按具体 ASR 要求转为 WAV/PCM 或其支持的其他格式。
- 在录音会话中建立 `recording_stream_id`；每片记录 `seq`、字节数、hash、MIME、客户端事件时间和服务端确认状态。
- 建议周期性产出分片并上传，但周期只是资源与网络配置；上传分片只是保存字节，不立即调用 ASR。
- 服务端幂等确认 `(recording_stream_id, seq, hash)`，客户端只在确认持久保存后移除上传队列中的对应内容。
- 分片重试使用退避策略；上传失败不等同于录音失败，界面分别显示录音状态与待上传数量。
- 一个流的所有分片必须按 seq 拼接，不遗漏第 0 片；浏览器重新创建 MediaRecorder 时产生新 stream，不能直接当成同一连续流。
- 中断后恢复为新 stream，服务端对每条完整流分别合并、解码，再按会话顺序组合标准音频并建立时间映射。
- 停止后等待最终 `dataavailable`、`stop` 与所有上传确认，再提交“完成上传”清单；后台校验缺片、总大小、可解码性和音频时长。
- 只有校验通过且对象持久保存，才能进入“可转写”；服务端采用业务任务 ID，避免供应商任务 ID 代替自己的主键。
- 页面展示“停止并保存”“暂停”“取消”“上传中”“网络断开、仍在本地暂存”等清晰状态。
- 监听页面可见性、track mute/ended、录音 error、联网变化等事件；事件用于发现问题，不保证在操作系统终止页面前一定触发。
- 录音期间给出“保持页面在前台”的常驻提示；返回页面发现中断时显示可保存的部分与缺失提示。
- IndexedDB 只作为恢复辅助；即使 persistent 申请成功，也不把用户清理数据、磁盘故障或进程终止当作可恢复保证。
- 浏览器被 kill 时，未触发或未上传的尾部可能丢失；部分容器在缺尾时也可能不可播放，应保留原件并显示“录音不完整”。
- 不将 `beforeunload`、后台请求、唤醒锁或 PWA 安装当作最终片上传和后台录音的可靠保障。
- 时长至少分“会话经过时间”“已确认音频时长”“有效语音时长”；暂停、缺失段和 VAD 裁切需要明确映射。
- 在弱网场景优先保证录音保存，不在每个分片上追加生成任务；音频完整后统一发起异步转写。
- 示例容量预算：假设压缩音频为 64 kbit/s，一小时约 28.8 MB；16 kHz/16-bit/mono PCM 一小时约 115.2 MB。这是计算示例，实际码率由设备和编码决定。

### Gaps

- 本轮没有运行 iPhone、Android 或微信实机测试；尚不能给出经过验证的浏览器最小版本与微信支持承诺。
- 微信旧 JS-SDK 官方链接返回当前“微信网页开发”页面，未取得可核查的录音接口正文；本笔记不引用传闻中的时长限制。
- 来电、蓝牙耳机切换、锁屏、音频路由变化、低电量、系统省电模式等必须分别测验。
- 待验证每种 MIME 在停止、暂停、恢复、缺头/缺尾、多次录音流情况下的完整性和服务端解码方式。
- 待验证 5/30/60 分钟的内存、发热、耗电、IndexedDB 配额、离线恢复与大 Blob 处理能力。
- 待测拒绝权限、授权后撤回权限、刷新、关页、清理浏览器缓存和强制结束进程的提示与恢复范围。

### 核心来源与本地证据表

| 编号 | 官方来源 | 本地材料 | 支持的核心结论 |
|---|---|---|---|
| S1 | [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia) | `.firecrawl/audio-mdn-getusermedia.md` | HTTPS、权限、错误类型、iframe |
| S2 | [MDN dataavailable](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event) | `.firecrawl/audio-mdn-dataavailable.md` | timeslice 不精确、锁屏/暂停风险 |
| S3 | [MDN MIME 探测](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/isTypeSupported_static) | `.firecrawl/audio-mdn-mime.md` | 探测格式仍可能录制失败 |
| S4 | [WebKit 公告](https://webkit.org/blog/11353/mediarecorder-api/) | `.firecrawl/audio-webkit-mediarecorder.md` | Safari 历史支持、WKWebView 约束 |
| S5 | [W3C 录制规范](https://www.w3.org/TR/mediastream-recording/) | `.firecrawl/audio-w3c-recording.md` | 完整 Blob 组合与最终事件顺序 |
| S6 | [MDN 存储规则](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) | `.firecrawl/audio-mdn-storage-direct.txt` | 本地存储配额与回收 |
| S7 | [FunASR](https://github.com/modelscope/FunASR) | `.firecrawl/audio-funasr.md` | 中文 ASR/VAD/标点/说话人流水线 |
| S8 | [Whisper](https://github.com/openai/whisper) | `.firecrawl/audio-whisper.md` | 多语言模型、代码与权重 MIT |
| S9 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | `.firecrawl/audio-faster-whisper.md` | CTranslate2、量化、VAD |
| S10 | [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | `.firecrawl/audio-whisper-cpp.md` | C/C++、CPU/原生移动/WASM |
| S11 | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | `.firecrawl/audio-sherpa-onnx.md` | ONNX、本地流式/非流式、多平台 |
| S12 | [阿里文件识别 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api) | `.firecrawl/audio-ali-file.md` | 异步任务、说话人、结果有效期 |
| S13 | [火山标准文件 API](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh) | `.firecrawl/audio-volc-standard-file.md` | submit/query、格式、分离限制 |
| S14 | [腾讯 CreateRecTask](https://cloud.tencent.com/document/product/1093/37823) | `.firecrawl/audio-tencent-create-task.md` | 任务、音频限制、身份与分离区别 |
| S15 | [讯飞语音转写](https://www.xfyun.cn/doc/asr/lfasr/API.html) | `.firecrawl/audio-xfyun-file.md` | 分片上传、长音频、分离警告 |
| S16 | [网信办个人信息保护法](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm) | `.firecrawl/audio-pipl-cac-direct.html` | 告知、最短保存、敏感信息、删除 |

## 2. 应先做录后转写还是流式 ASR？

### Takeaway

建议第一版采用“前台录音与分片保存 → 完整音频确认 → 异步录后 ASR → 销售校对 → 需求生成”。
实时字幕与实时建议作为后续阶段，用业务实测决定价值，不把流式 ASR 当作后台录音或数据恢复手段。

### Cited Findings

- 阿里非实时接口采用提交任务、轮询结果的异步模式，并通过链接读取录音文件；返回结果含分句/词与时间信息。— [阿里文件识别 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)
- 火山标准版明确分为提交音频链接与按任务 ID 查询结果两个阶段，另支持回调字段。— [火山标准文件 API](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh)
- 讯飞录后识别流程包括预处理、分片上传、合并、查询进度、获取结果；结果受音频时长与队列影响。— [讯飞语音转写](https://www.xfyun.cn/doc/asr/lfasr/API.html)
- 腾讯文件识别可使用回调或轮询，接口返回 TaskId；文档明确结果和 TaskId 存在有效期限制。— [腾讯 CreateRecTask](https://cloud.tencent.com/document/product/1093/37823)
- 火山流式 API 使用 WebSocket 二进制协议，涉及握手鉴权、音频配置、连续音频包、序号与终止标记。— [火山流式 ASR](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelstreamingautomaticspeechrecognitionAPI?lang=zh)
- 火山流式文档提供语音判停窗口、确定分句等配置；这些参数影响何时输出稳定结果。— [火山流式 ASR](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelstreamingautomaticspeechrecognitionAPI?lang=zh)
- faster-whisper 将 Whisper-Streaming、WhisperLive 列为实时模式的外部集成，不能直接把该库离线文件接口等同于原生实时转写协议。— [faster-whisper](https://github.com/SYSTRAN/faster-whisper)

### Inferences

| 维度 | 录后异步转写，MVP 推荐 | 实时流式 ASR，后续候选 |
|---|---|---|
| 销售体验 | 会后查看完整文字、录音定位、需求草稿 | 谈话中看到字幕或问题建议 |
| 浏览器要求 | 可靠保存压缩录音，完整上传后转码 | 还需持续发送供应商要求的音频帧 |
| 连接管理 | HTTP 上传、后台任务、轮询/回调 | WebSocket、重连、终止包、背压、会话超时 |
| 转写稳定性 | 完整音频上下文，允许单次重试与重新识别 | 临时结果会变化，必须区分 partial 与 final |
| 失败恢复 | 保存原件可重新转写 | 仍需另存原音频，不能只依赖实时连接 |
| 成本控制 | 按完整文件与任务统计，容易设置预算 | 需额外统计连接时长、重复窗口、并发额度 |
| 研发范围 | 与 MVP 业务闭环直接相关 | 适合已验证实时提示有价值后投入 |

- 不能从“流式”这个标签推断单价更高或更低；不同厂商按时长、内容时长、资源包或并发计价，应取实际模型报价。
- 录后任务与录音任务分离；页面关闭后 ASR、需求提炼仍由服务端队列完成，客户重新打开可查看状态。
- 页面状态建议：录音中、上传中、校验中、转写中、待校对、需求已生成、失败可重试。
- 原始转写与人工校对分版本保存；需求必须引用音频区间、转写片段 ID 和校对版本。
- AI 需求提炼只消费稳定的转写版本；客户明确需求、销售建议、未确认问题分字段表达。
- 未来实时功能先做字幕；不要直接用未稳定的 partial 文本启动代码 Agent，避免错误内容触发昂贵任务。
- 若未来增加流式服务，建议浏览器连接自己的鉴权网关，再由服务端对接供应商；长期 ASR 密钥不可放进手机页面。
- 浏览器压缩 Blob 与厂商实时 PCM/Opus 帧不是同一数据契约，不能把 MediaRecorder timeslice 原片直接视为通用流式帧。
- 成本估算应包含音频时长/有效语音时长、ASR 重试次数、存储和流量、LLM 提炼次数、代码 Agent 消耗、Demo 存续资源。
- 设置租户月预算、每次访谈限制、重复提交去重、失败重试上限；策略值是产品配置，不是调研事实。

### Gaps

- 没有同一批真实售前录音的云 ASR 与自托管 CER、说话人 DER、处理时间和实际账单对比。
- 本轮没有验证特定账号的厂商额度、地域、SLA、付费模型和资源包折扣，因此不填入固定单价。
- 尚需访谈销售确认“录音中字幕”是否比“会后准确需求和 Demo”更值得首期投资。

## 3. 中文 ASR 云服务和开源项目怎样选择？

### Takeaway

中文 MVP 默认采用境内云 ASR，经业务样本评测后固定一个主供应商；阿里录音文件服务为首轮候选，腾讯与火山为同批对照。
FunASR 与 faster-whisper 是自托管候选，whisper.cpp 与 sherpa-onnx 用于将来原生移动、CPU/边缘与离线场景。

### Cited Findings

- FunASR README 展示中文 Paraformer 与 VAD、标点、CAM++ 说话人组合，以及 streaming/offline 方案；能力依赖选定 checkpoint 和组件。— [FunASR](https://github.com/modelscope/FunASR)
- FunASR 仓库代码为 MIT，预训练权重另行许可，README 要求逐个核查模型卡；它不意味着全部模型可以按 MIT 使用。— [FunASR LICENSE](https://github.com/modelscope/FunASR/blob/main/LICENSE)；[FunASR 模型条款](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)
- 核查时 `MODEL_LICENSE` 为 1.1，除署名、保留模型名称外，含行为条件、违反条件自动终止及协议修订条款；这是自定义模型协议。— [FunASR 模型条款](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)
- SenseVoiceSmall 模型卡元数据写明 `license: other`，并链接 FunASR MODEL_LICENSE；不能因使用 FunASR toolkit 而省略权重条款。— [SenseVoiceSmall 模型卡](https://huggingface.co/FunAudioLLM/SenseVoiceSmall)
- Whisper 官方仓库说明其多语言识别、语音翻译、语言识别能力，并明确代码与模型权重均 MIT；官方同时说明不同语言表现差别明显。— [Whisper](https://github.com/openai/whisper)
- faster-whisper 是 CTranslate2 上的 Whisper 重实现，支持 CPU/GPU 8-bit 量化、批处理和 Silero VAD；其仓库许可为 MIT。— [faster-whisper](https://github.com/SYSTRAN/faster-whisper)；[LICENSE](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE)
- faster-whisper README 的最高 4 倍速度来自项目特定 benchmark，包含硬件、精度与 batch 条件；该数字不能直接当作本项目吞吐或延迟。— [faster-whisper benchmark](https://github.com/SYSTRAN/faster-whisper#benchmark)
- whisper.cpp 支持 CPU、多个 GPU 后端、量化、VAD、iOS/Android 示例及 WebAssembly，仓库为 MIT；原生移动示例不证明手机网页有同等性能。— [whisper.cpp](https://github.com/ggml-org/whisper.cpp)
- sherpa-onnx 支持本地流式/非流式 ASR、VAD、说话人分离/识别/验证及多平台/WASM；代码为 Apache-2.0。具体模型权重仍需查看模型自身条款。— [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)；[LICENSE](https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE)
- 阿里文件 API 支持说话人分离，限制为单声道，启用后建议录音不超过两小时；指定 speaker_count 只是参考，不能保证输出人数。— [阿里文件识别 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)
- 阿里文件 API 的转写下载链接有效期 24 小时，多声道独立计费；文档当前说明按模型判定的语音内容时长计量，不能套用为所有模型服务规则。— [阿里文件识别 API](https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api)
- 火山标准文件 API 支持 `raw/wav/mp3/ogg`，说话人聚类开关默认关闭；文档表示 10 人以内效果较好，且音量/远近明显变化时无法保证区分效果。— [火山标准文件 API](https://docs.volcengine.com/docs/DoubaoVoice/LargemodelrecordingfilerecognitionstandardversionAPI?lang=zh)
- 腾讯 CreateRecTask 文档支持多种文件容器；URL 文件限制为不超过 5 小时/1 GB，本地文件不超过 5 MB；识别结果服务端保存 24 小时。— [腾讯 CreateRecTask](https://cloud.tencent.com/document/product/1093/37823)
- 腾讯 diarization 与 SpeakerRoles 角色认证是不同参数；后者要求声纹样本和特定引擎，且是增值能力。— [腾讯 CreateRecTask](https://cloud.tencent.com/document/product/1093/37823)
- 讯飞所核查的 Long Form ASR 接口支持不超过 5 小时/500 MB，列举 wav/flac/opus/m4a/mp3，支持热词；该文档明确其说话人分离仍可能达不到商用标准。— [讯飞语音转写](https://www.xfyun.cn/doc/asr/lfasr/API.html)
- 讯飞页面写明转写结果保存 30 天、获取结果次数限制 100 次；这是该接口规则，不代表本项目应保留 30 天音频。— [讯飞语音转写](https://www.xfyun.cn/doc/asr/lfasr/API.html)

### Inferences

| 选择 | 首期定位 | 主要理由 | 决策条件 |
|---|---|---|---|
| 阿里境内文件 ASR | 第一轮主候选 | 完整异步协议、说话人/时间戳、境内部署路径 | 真录音测试与当期商务条款 |
| 腾讯文件 ASR | 同批对照与备选 | 文件任务、热词、说话人能力明确 | 选择会议适用引擎，核查增值开关 |
| 火山文件 ASR | 同批对照与备选 | submit/query、热词、聚类分离明确 | 容器转码、长音频限制与回调测试 |
| 讯飞文件 ASR | 采购备选 | 中文、热词、文件分片协议 | 核验所购版本，特别测说话人能力 |
| FunASR | 中文私有化 PoC | 中文 ASR/VAD/标点/说话人组件完整 | 权重逐项许可、机器实测、运维投入 |
| faster-whisper | 多语言/对照自托管 PoC | Python 服务、量化与批处理成熟路径 | 显存/CPU、CUDA依赖、中文 CER 实测 |
| whisper.cpp | 原生/CPU/边缘后续候选 | C/C++、量化、多平台 | 客户真实硬件与模型大小评估 |
| sherpa-onnx | ONNX/流式/离线后续候选 | 本地多功能与多平台 | 挑模型、查权重协议、核查模型导出链 |

- 首期不自建 ASR 训练平台，不优先在手机浏览器内加载大模型；应先完成可验证的销售业务闭环。
- 统一供应商适配契约：源音频 ID、引擎/模型版本、语言、词表、分句 start/end、匿名 speaker ID、文本、供应商原始结果和 usage。
- 对阿里/腾讯 24 小时结果窗口，任务完成后立即下载原始 JSON，保存至自己的受控存储；界面不能长期直接引用供应商临时结果链接。
- 用不少于 20 段取得授权的录音做 PoC：普通话、中英产品名、行业术语、口音、远场、噪声、重叠说话、短暂停顿与长会议。
- 给词表添加客户名称、产品缩写、业务实体；过强热词可能将无关词误改成目标词，必须同时检查漏识别和误召回。
- ASR 的 ITN/顺滑/去语气词会改变可读文本；保留原始结果，预算、数量、日期、否定和“可以/不可以”重点人工校对。
- 比较维度为中文 CER、关键实体准确率、否定/金额错误、分离 DER、人工修订时间、完整任务耗时 P50/P95、失败率和实际成本。
- 模型选择应以关键需求事实准确度为业务指标，不只依赖通用 CER，更不按 GitHub stars 排序。

### 维护证据

以下日期来自本轮 GitHub 官方 commits API；最新提交仅证明仓库有活动，不证明成熟度或生产可靠性。

| 项目 | 核查到的最近提交 UTC 日期 | 直接证据 |
|---|---|---|
| FunASR | 2026-10-08 | [e7e6129](https://github.com/modelscope/FunASR/commit/e7e61293d308f4342ab9307895e710e4b51b949c) |
| Whisper | 2026-08-31 | [8609812](https://github.com/openai/whisper/commit/86098128c0b4f24f0e2aa2994de830614b474227) |
| faster-whisper | 2026-10-10 | [a52b026](https://github.com/SYSTRAN/faster-whisper/commit/a52b026ac844c02117865e61968547639b60a6f8) |
| whisper.cpp | 2026-10-11 | [7e26d3b](https://github.com/ggml-org/whisper.cpp/commit/7e26d3b0d5bced6c8217ef09710ec2f969001241) |
| sherpa-onnx | 2026-10-12 | [6e7ea3e](https://github.com/k2-fsa/sherpa-onnx/commit/6e7ea3e409f90aaf1541c87f21a013c4f20b9680) |

### Gaps

- 云页面可随时变更模型名与参数；编码实施前需重新核查采购地域、当期文档和已开通服务，不直接固定为本轮“最新版本”。
- 没有取得各家付费账号；不能核实当前商务单价、折扣、额度、限流、供应商音频删除方式与完整数据处理协议。
- 已核查 FunASR/SenseVoice 的自定义模型条款；Paraformer、CAM++、VAD 等每一个实际 checkpoint 仍需独立归档模型卡和许可证。
- faster-whisper/whisper.cpp 自带代码许可不自动覆盖第三方模型、VAD、转换后 checkpoint 和追加组件。
- 尚未做 GPU/CPU 吞吐和并发测试，不能决定自托管什么时候比云服务便宜。

## 4. 说话人、授权、保存与境内部署有什么边界？

### Takeaway

说话人分离只输出匿名聚类，销售/客户的真实身份须由销售人工映射；MVP 不建立声纹识别库。
录音与转写均需明确的业务授权、保存目的和删除规则；推荐音频及中文 ASR 处理默认选择境内地域。

### Cited Findings

- FunASR README 说明 CAM++ 提取 embedding，流水线聚类后产生录音内的 speaker indices，并强调这些索引不是已知个人身份。— [FunASR](https://github.com/modelscope/FunASR)
- VAD 用于检测/过滤非语音区间；faster-whisper 的 Silero 集成说明其默认保守地移除较长静音，不等同于身份识别或完整语音理解。— [faster-whisper VAD](https://github.com/SYSTRAN/faster-whisper#vad-filter)
- 个人信息保护法第 13 条列明处理依据，第 14、15 条规定基于同意的知情、自愿、明确和撤回；第 17 条要求处理前告知目的、方式、种类与保存期限等。— [网信办法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)
- 第 19 条规定保存期限应为实现处理目的所需的最短时间；第 21 条规定委托处理需约定目的、期限、方式、信息种类、保护措施和双方权责。— [网信办法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)
- 第 28、29 条将生物识别列入敏感个人信息范畴，并规定敏感个人信息处理的严格保护与单独同意要求；不能由此断言所有普通访谈音频一律属于生物识别。— [网信办法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)
- 第 39 条对向境外提供个人信息规定告知境外接收方等事项和单独同意；第 47 条规定目的实现、保存期届满、撤回同意等情况下的删除义务。— [网信办法律全文](https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm)

### Inferences

- 录音开始前销售应告知客户录音、AI 转写和需求提炼的用途；浏览器麦克风权限只代表设备操作许可，不替代客户的业务授权。
- 建议记录授权方式、时间、参与者、所用说明版本与销售确认；具体法律依据及合同表述由团队按实际业务确定。
- speaker_0/1 由销售标为“我/客户 A/客户 B/未知”；允许合并、拆分与纠错，不自动推断谁有预算决策权。
- 同一人的 speaker index 可在另一段录音中变化；映射的作用域应限定于会话/转写版本。
- 重叠说话、远近变化、电话扬声器、噪声可能产生错误分离；无法区分时保留“未知”，不要让 LLM 猜真实身份。
- 不把情绪标签当成客户购买意愿、真实性或成交概率；需求来源应是有证据的发言与人工确认。
- 需求生成需要保留“原话—时间段—角色映射—校对版本—需求条目”的来源链；未确认信息进入待澄清问题。
- 对单麦克风访谈保留原音；VAD 只辅助分段，若裁切静音需保存完整时间映射，避免证据跳转错位。
- 境内对象存储、ASR、数据库和日志采用租户权限隔离；只给转写服务临时取件权限，不将访谈音频公开分享。
- 默认保存期限应由业务目的确认，可提出试点策略但不能当作法定期限；音频、转写、需求及备份分别明确保留与删除周期。
- 删除路径覆盖原音、分片、转码副本、供应商结果、自有转写、向量索引、任务日志中的内容与备份到期处理。
- 委托 ASR/LLM 服务前核验数据用途、训练使用政策、保存期限、删除能力、地域和分包处理，不用“境内域名”代替合同确认。
- 音频与转写属于客户材料；Demo 广场不自动带入原音或原始访谈，公开展示前使用脱敏的需求与模拟数据。
- 导出的 Demo 只应包含确认需求与合成样例；客户真实姓名、电话、财务数据和录音 URL 不传入代码 Agent 工作区。
- 若未来接海外 LLM 或海外 Agent，不要把原音或完整客户资料无条件转发；先明确脱敏策略及适用的数据出境处理条件。
- 记录 ASR/需求调用审计的任务 ID、模型、用量、结果状态和版本，业务内容日志应最小化并有独立访问控制。

### Gaps

- 法律全文已核查；企业实际业务处理依据、授权文本和数据出境流程仍需在实施前按真实主体与合同确认。
- 尚未核查候选云厂商对源音频的完整留存/删除合同，不把“结果有效期”视为源音频删除保证。
- 同意撤回后对已经产生的需求、共享链接、客户 Demo、备份如何联动删除，需要产品与运维共同定义。
- 没有客户访谈真实样本，因此不能承诺匿名聚类准确率，亦不能预设每次访谈一定只有两人。

### 调研方法与材料限制

- 首选 Firecrawl CLI 1.26.3 的 keyless scrape 与 `search --sources web --scrape`，未要求用户注册或提供密钥。
- 默认 search 因 Alexandria 鉴权失败，改用纯 web 查询成功；后续 keyless 达到速率限制后没有重复提交同一受限请求。
- search-feedback 尝试触发 CLI 登录提示，未完成登录或发送反馈；这不影响已保存的官方来源证据。
- LICENSE、模型卡、MDN 存储原始文档、GitHub commit API 和网信办法律全文补充使用 PowerShell HTTP 抓取。
- 原始文件均为 `.firecrawl/audio-*`；GitHub API JSON 保存完整 sha/日期，许可文件与模型卡可追溯。
- gov.cn 历史法律链接返回首页，未将其作为法律依据；改读网信办官方全文。
- 微信旧链接返回当前网页开发文档入口，未提取到录音 API 正文；因此微信只列为待实机核验项。
- Firecrawl 网页抓取和 GitHub API 可能存在采样时间差，sherpa-onnx 首页与 API 的最新提交不同；维护表采用 API 快照。
- 报告没有运行麦克风、真实音频转写、云付费请求或任何代码 Agent，所有项目选择均待 PoC 证据收敛。
