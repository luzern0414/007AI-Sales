# 免费本地转写

选择：FunASR 2pass；备选：sherpa-onnx流式模型、Whisper会后校订。开源自部署不收取云端转写接口费用，硬件、电力和维护由部署方承担。云服务的试用额度、期限与续费条件以账户实际规则为准。

## 当前实现

手机前台麦克风 → 独立音频归档 + 已登录WebSocket → 后端FunASR接口 → 私有模型服务 → 实时文字/句尾修正 → 数据库。密钥和识别服务地址不下发浏览器。识别失败不会取消音频归档，也不会切换到收费供应商。

2026-10-15已完成真实会议文件的本地离线识别、2pass模型服务部署及手机尺寸浏览器的真实识别闭环。本机约32GB内存、GTX 1630约4GB显存；当前使用CPU四线程、同时一路识别。手机使用时仍需联网到部署服务器；自部署不等于手机网页断网识别。手机真机、锁屏、长会议与生产部署仍未验收。

## 本次离线部署与实测

- 独立环境：`.venv-asr`，Python3.12.13；FunASR1.2.9、PyTorch/torchaudio2.5.1+cpu。完整依赖见 `config/funasr-batch.lock.txt`，未改动平台应用环境。
- 模型：Paraformer-zh + FSMN-VAD + CT-Transformer标点，各使用ModelScope的 `v2.0.4` 文件；下载器核对每个文件的官方SHA-256，模型目录保留下载清单及文件版本记录。三个模型卡标示Apache License2.0。
- 模型位置：`output/funasr/models`。音频仅在本机解码和识别，未上传外部转写服务。
- 样本：用户指定的“深圳科创项目内部会.m4a”；容器标注54:00.18，解码为3246.6735秒，时间戳以解码音频为准。
- 实测：模型加载2.891秒，识别155.437秒，音频/识别耗时约20.9倍；959条带时间戳文本、12144个字符（含标点/空格）。首次依赖及模型下载、音频转换和纪要整理不计入识别耗时。
- 完整性：原录音SHA-256未变；959条时间记录范围有效并按起始时间排序，最后一条结束于3246.415秒。该检查不证明每句均识别正确。
- 效果：通读发现部分普通发言较连贯，远距离发言、人名、设备品牌、叠音或不连贯片段有明显错误。未进行人工逐字标注，不能报告准确率。纪要由本次任务根据转写归纳，并非FunASR直接输出或平台自动生成链路已验收。
- 输出：原录音同目录的 `深圳科创项目内部会-FunASR转写稿.md`、`深圳科创项目内部会-会议纪要.md`。纪要区分讨论、结论和待确认项，保留时间依据，不根据文件修改日期推定会议日期。
- 运行记录：`output/funasr/shenzhen-kechuang/result.json`、`verification.json`、`transcribe.log`。包含私人会议文本，仅保留本机，不提交或公开。

复用已安装环境运行其他文件：

```powershell
.venv-asr\Scripts\python.exe -u scripts\transcribe_funasr.py 'D:\会议\客户会议.m4a' --work-dir output\funasr\client-meeting --model-dir output\funasr\models --threads 4
```

命令仅生成带时间戳的转写稿，不自动调用语言模型生成纪要；目标已有同名转写稿时拒绝覆盖。模型下载脚本为 `scripts/download_funasr_models.py`，默认三个离线模型，`--streaming`可补充流式模型；核对文件哈希并保留下载记录。本次离线结果不能代替手机录音、断网补识别或并发验收。

## 启动实时服务

本机已增加Paraformer流式模型，ModelScope版本v2.0.4；权重SHA-256为`4fdfb48ed4471777c9a511e96a2acae17f77cac9d709cc756634622769192a64`。下载清单位于`output/funasr/models/paraformer-zh-streaming/download-manifest.json`。四个模型复用同一独立环境，服务依赖包含websockets17.2。

在项目目录分别运行两个PowerShell终端：

```powershell
# 转写服务：模型加载后输出FUNASR_READY再接受连接
.\scripts\start-funasr.ps1
```

```powershell
# Web平台
.\scripts\start.ps1
```

默认转写地址`ws://127.0.0.1:10096`，平台地址`http://127.0.0.1:8765`。可通过`start-funasr.ps1 -Port 10096 -Threads 4`指定参数；端口变更需同步配置。两个终端须保持运行；本次未安装系统服务或开机启动。

服务入口`scripts/funasr_service.py`；分段状态机`scripts/funasr_session.py`。WebSocket限制一路会议、6400字节帧、队列和空闲时限。活动语音最长约20秒切段；静音时轮换VAD缓存，重放最多1秒且不早于已确认段尾的音频，维持连接内时间轴。适配器仅向FSMN提交完整200ms非final帧，余数在结束时处理，以绕过FunASR1.2.9余数缓存错误。平台启动缓存最多1秒PCM，停止等待句尾确认，超过时限显示失败。

## 实时验证

- 真实授权录音26秒片段通过Chrome合成麦克风输入，隔离平台`8767`、数据库`output/asr-ui.db`和文件`output/asr-ui-files`；未写入正常业务项目库。浏览器尺寸390×844，不代表物理手机测试。
- 直接流式输入11秒静音、26秒录音及25ms尾段：37.025秒音频，4条句尾修正，结束确认37.375秒收到；首段起点10770ms，末段结束37010ms，均在输入范围。事件保留在`output/funasr/shenzhen-kechuang/realtime-bounded.json`。
- 网页12.0686秒录音暂停后增加3条句尾文本；立即可见，刷新后持久存在，音频193097帧完整封存。
- 关闭真实识别服务后页面提示转写中断，音频仍持续归档；73.110875秒、1169774帧最终完整封存，无缺失序号。恢复服务后再次录音8.0805秒，2条句尾结果入库，停止确认成功。
- 已从网页下载WAV、MD、PDF，核对数据库、120个原始块哈希及连续性；WAV为1846680帧、115.4175秒，PCM与原始块拼接完全一致。MD与两页PDF包含全部12条句尾文字。验证记录在`output/funasr/shenzhen-kechuang/platform-verification.json`，截图`output/playwright/funasr-mobile-verified.png`。
- ASR独立环境9项测试通过，含真实VAD60秒静音与非整帧段尾回归；前端11项测试通过，平台48项通过，构建通过。SDK存在torch.load未来行为警告，平台测试存在Starlette/httpx弃用警告。

未实现ASR断线重连、归档音频会后补识别或跨录音段时间映射；失联期间的声音已保存，不自动补成文字。网页MD/PDF导出包含已保存的记录与转写，不能据此宣称平台AI归纳、方案生成已通过真实语言模型验收。

## 配置

根目录`.env`已配置以下两项，端口需与实际服务一致：

```dotenv
REALTIME_ASR_PROVIDER=funasr
FUNASR_WS_URL=ws://127.0.0.1:10096
```

模型服务与平台同机时绑定回环地址；跨机器在受控网络使用可信WSS。不要将无鉴权识别端口直接暴露公网。平台通过自身登录与项目所有权验证后才接入转写。

模型部署依据[官方实时服务指南](https://github.com/modelscope/FunASR/blob/main/runtime/docs/SDK_advanced_guide_online_zh.md)。代码、流式/句尾识别、VAD、标点模型分别固定版本与许可，不能把仓库代码许可推断为全部模型许可。不自动执行上游安装脚本或下载全部模型。

## 接口兼容要求

- 接受16kHz、单声道、PCM16LE二进制帧及2pass初始配置。
- `2pass-online`作为增量临时文字，`2pass-offline`作为修正后的完整句子；临时文字不入库。
- 停止后接收 `{"is_speaking":false,"is_end":true}`，返回剩余句子及 `{"is_end":true,"is_final":true}`。当前接口要求明确的结束确认，后端最多等待15秒，前端停止保护18秒；缺失则报告中断，已确认文字仍保留。
- 不能只凭单条结果的`is_final`判定全部结束；不同运行时该字段可能代表不同边界。当前官方Python运行时可查看[实现](https://github.com/modelscope/FunASR/blob/main/runtime/python/websocket/funasr_wss_server.py)，其他版本和预构建镜像需实际核验，不能直接认为兼容。
- 目前不提供FunASR文字的录音时间定位；没有稳定的会议时间轴时保存空时间值，避免虚构定位。连续重复发言不会按文本去重。

修改配置后重启平台；登录查看 `/api/integrations/status`。这只能确认配置。真实验收还需中文会议样本、专有名词、噪声、长录音、断线、最后一句、真实手机和CPU负载测试。模型效果未通过前不标记识别上线。

## 官方资料

- [FunASR](https://github.com/modelscope/FunASR)、[代码MIT许可](https://github.com/modelscope/FunASR/blob/main/LICENSE)
- [WebSocket协议](https://github.com/modelscope/FunASR/blob/main/runtime/docs/websocket_protocol_zh.md)
- [Paraformer流式模型卡](https://huggingface.co/funasr/paraformer-zh-streaming/blob/main/README.md)：该模型卡标示Apache-2.0，不代表其他组件许可。
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx)：CPU/ONNX备选，当前未集成。
- [Whisper](https://github.com/openai/whisper)：会后识别备选，当前未集成。

2026-10-15：复用当日官方资料缓存，补抓官方协议及Python运行时。Firecrawl未认证，本次新增资料通过公开GitHub原文读取。
