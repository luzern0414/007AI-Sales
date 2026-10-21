# FunASR 本机 CUDA 部署与验收

本方案在独立 `.venv-asr-gpu` 中使用 FunASR 1.2.9、PyTorch/torchaudio 2.5.1 CUDA 12.1 wheels，复用现有四个 v2.0.4 模型。`.venv-asr` CPU 环境保持可单独启动。私有录音仅在本机读取、识别和保存；依赖及官方文档下载不包含录音。

## 启动和回退

```powershell
# 需要已验证的CPU环境、uv和NVIDIA驱动；下载约2.3GiB PyTorch wheel
.\scripts\setup-funasr-gpu.ps1
# 网络较慢时复用CPU环境的同版本通用包为独立副本，保留CUDA版PyTorch
.\scripts\setup-funasr-gpu.ps1 -ReuseCpuDependencies
# 独立端口验收GPU，不占用现有10096服务
.\scripts\start-funasr.ps1 -Device cuda:0 -Port 10097 -Threads 4
# CPU回退
.\scripts\start-funasr.ps1 -Device cpu -Port 10096 -Threads 4
# 优先使用GPU环境；CUDA不可用时才选择CPU，启动行显示实际设备
.\scripts\start-funasr.ps1 -Device auto -Port 10097
```

`--device cuda:0` 在 CUDA 不可用时直接报错，不会假称 GPU 成功。服务检查每个模型参数的实际设备；模型加载显存不足时提示释放显存或改用 CPU；推理显存不足时返回 `gpu_out_of_memory`，不返回结束成功确认。`auto` 不在显存不足后重新播放或切换识别中的录音；停止失败会保留平台原有音频归档行为，已归档音频不会因此自动补转写。

启动脚本默认仍是 CPU；本平台当前 `.env` 已选择10097 GPU实时服务，文件补转写固定CPU。选择 GPU 时须手动同步平台 `FUNASR_WS_URL` 与服务端口；修改平台配置后须重启平台。切换 10096 前应确认没有活动录音。绑定地址仍为回环地址，仅支持同时一路会议。

## 可复现的实测

```powershell
.venv-asr\Scripts\python.exe -u -m scripts.benchmark_funasr output/funasr/shenzhen-kechuang/realtime-check.wav --device cpu --output output/funasr/shenzhen-kechuang/benchmark-cpu.json
.venv-asr-gpu\Scripts\python.exe -u -m scripts.benchmark_funasr output/funasr/shenzhen-kechuang/realtime-check.wav --device cuda:0 --output output/funasr/shenzhen-kechuang/benchmark-gpu.json
```

基准按200ms帧运行与服务相同的2pass会话，包含VAD、流式识别、句尾离线修正和标点，不等待音频真实时长；结果记录三轮耗时、实际模型设备、PyTorch分配/保留显存峰值及识别事件。CUDA计时前后同步设备。模型加载耗时单独记录，首次依赖下载不计入识别耗时。输出包含私有文字，必须保留在被忽略的 `output/` 中，不提交或公开。

真实基线（2026-10-15）：26秒同一片段、相同音频SHA-256、相同4线程及模型。

| 项目 | CPU | GTX1630 CUDA |
| --- | --- | --- |
| 四模型参数设备 | 全部CPU | 全部cuda:0 |
| 模型加载 | 8.030秒 | 9.041秒 |
| 第一轮2pass识别 | 7.284秒 | 10.016秒 |
| 第二轮2pass识别 | 6.833秒 | 5.268秒 |
| 第三轮2pass识别 | 7.213秒 | 5.268秒 |
| 每轮句尾结果 | 4条 | 4条 |

GPU热轮约比CPU快1.3倍，首轮因CUDA首次运行开销较慢；本次最后一轮句尾文本一致，不代表所有录音结果必然相同，也不证明人工标注准确率。GPU PyTorch峰值分配2,168,386,560字节（2067.9MiB），峰值保留2,206,203,904字节（2104MiB）。设备GTX1630计算能力7.5；实际运行库CUDA12.1，驱动610.88。基准记录在 `output/funasr/shenzhen-kechuang/benchmark-{cpu,gpu}.json` 及对应日志。

CUDA张量实算、`uv pip check`均通过，依赖快照 `output/funasr/gpu-lock.txt`；CPU/GPU环境各含真实模型VAD的16项回归通过，各有上游 `torch.load(weights_only=False)` FutureWarning。本次官方CUDA包下载约37分钟后安装；通用包下载出现重试，最终以 `-ReuseCpuDependencies` 从CPU环境复制同版本通用依赖，保留独立副本，不使用跨环境 `.pth` 引用。复用安装脚本已实际运行并再次通过依赖及CUDA实算检查。

独立GPU服务已运行于 `ws://127.0.0.1:10097`（本次监听PID4156，启动器PID1688）；`output/funasr/gpu-service.log` 包含 `device=cuda:0` 的就绪行。真实WebSocket按200ms发送26秒授权片段，收到4条句尾、合法范围时间戳及结束成功确认；总耗时27.141秒（包括发送等待），停止后0.411秒确认。证据 `output/funasr/shenzhen-kechuang/gpu-websocket.json`。CPU10096服务保留为备用，本次未重启。

GPU服务运行时 `nvidia-smi` 观测整卡使用约3589MiB、空闲约354MiB（桌面及其他程序占用也计算在内），与PyTorch单进程分配峰值含义不同。文件批处理建议用 `.venv-asr` + `--device cpu`；在这张4GB显卡上同时启动独立GPU批处理会再加载模型，尚未验证可稳定并行，不能因为两个单独入口通过就认定并行可用。服务目前是单路会议，未验收长会议、物理手机、并发、显存挤占或生产稳定性。

离线文件入口同样支持 `--device` 和 `--output`，例如：

```powershell
.venv-asr\Scripts\python.exe scripts/transcribe_funasr.py input.wav --work-dir output/funasr/job --model-dir output/funasr/models --device cpu --output output/funasr/job/transcript.md
```

输出已存在时拒绝覆盖；省略参数时仍使用CPU并写在源录音旁。离线入口对同一26秒片段实测CPU识别1.563秒、GPU识别1.625秒，均10条带时间句，短样本未显示GPU加速收益。GPU离线结果 `output/funasr/batch-gpu-check/result.json` 记录实际cuda:0；目标稿件 `chosen-transcript.md`。离线批处理与实时2pass的输入切分不同，耗时不能直接当作GPU加速比。

## 选择依据及适用边界

- [PyTorch历史版本安装](https://pytorch.org/get-started/previous-versions/)明确列出2.5.1在Linux/Windows的CUDA12.1安装命令。选择与现有CPU环境相同的PyTorch主版本，减少模型行为差异。
- [NVIDIA CUDA兼容性](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html)说明较新驱动可运行旧CUDA应用；`nvidia-smi`显示的CUDA上限不等于当前PyTorch实际运行库版本，应检查 `torch.version.cuda`。
- [PyTorch2.5 CUDA语义](https://docs.pytorch.org/docs/2.5/notes/cuda.html)说明CUDA异步执行，计时需要同步；分配显存、保留缓存和系统总占用含义不同。本基准分别记录PyTorch峰值与设备剩余显存。
- [FunASR官方说明](https://github.com/modelscope/FunASR)要求GPU示例前确认 `torch.cuda.is_available()`，Paraformer和Paraformer streaming均提供CUDA调用示例。最新README可能对应新版本功能；本项目固定1.2.9并以已安装源码和真实识别验证兼容性。
- 本机GTX1630显存4GiB且同时承担桌面显示，空闲显存随其他程序变化。4个模型的权重文件共约1.93GiB，运行还需CUDA上下文、激活值和缓存；不能根据权重大小直接承诺并发、长会稳定性或性能提升。
- 模型版本及许可证沿用 `config/funasr.md` 的核验记录；CUDA运行库包含NVIDIA组件，分发时还须遵循所包含组件的许可，不能把FunASR代码MIT许可套用到全部依赖。

本次 Firecrawl CLI 不在PATH，按已授权降级读取公开官方URL。原始资料缓存 `.firecrawl/20261015-gpu-pytorch-previous.txt`、`20261015-gpu-cuda-compatibility.txt`、`20261015-gpu-pytorch-cuda-notes.txt`、`20261015-gpu-funasr-readme.txt`、`20261015-gpu-funasr-automodel.txt`；不上传私有会议内容。

## 平台连接验收补充

GPU服务经过平台真实WebSocket转发、认证与数据库持久化的隔离验证通过：26秒样本、4条最终转写、complete确认。隔离库位于TEMP，不写正式会议；证据 `output/funasr/gpu-web-platform.json`。平台在实时转写完全无正文时会对已完整封存WAV进行本机离线补转写；非完整封存不能补转写，静音会明确提示未识别到语音。仍不能据此认定部分断流区间已自动补齐。
