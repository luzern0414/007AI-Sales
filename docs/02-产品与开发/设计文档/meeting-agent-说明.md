# Web AI 销售助手与会议 Agent 文档索引

> 当前范围已更新：项目全流程、面客产品库、跨项目工作台、手机优先。见[项目交付设计 V3](project-delivery-design.md)。已开始编码；实际验证状态见开发记录。

当前基线：2026-10-15，Asia/Shanghai，V3。已经实现本机前后端与数据库链路，并运行隔离自动测试、Chrome手机视口操作及合成音频恢复验证。真实模型/ASR、真机与上线尚未验证。运行方式见[根目录README](../../../README.md)，实际结果见[开发记录](../%E5%BC%80%E5%8F%91%E8%AE%B0%E5%BD%95/development-log.md)。

面向现场客户会议，自建四页 Web：**首页、项目管理、产品库、工作台**。首页实时麦克风录音/文字，本机与服务端持续保存、断点补传和缺口提示；会议结束经校对生成可下载 MD/PDF 纪要，再结合已核实产品能力生成售前方案、需求清单、甲方资料权限规则确认清单。严格遵循指定格式，未明确分期时单版，配色低饱和。

| 当前文档 | 阅读目的 |
|---|---|
| [项目交付设计V3](project-delivery-design.md) | 当前业务、项目完整链路及手机体验基线 |
| [综合技术调研](<Web%20%E9%94%80%E5%94%AE%E5%8A%A9%E6%89%8B%20%E5%AE%9E%E6%97%B6%E4%BC%9A%E8%AE%AE%20%E6%9E%B6%E6%9E%84%E8%B0%83%E7%A0%94.md>) | 42项开源/接口/模型候选、许可与官方来源、三条路线和唯一推荐主栈 |
| [实时平台设计 V2](realtime-platform-design.md) | 四页功能、音频双路径与恢复、产品依据、Agent、数据/API、PDF、实施顺序和验收 |
| [四页 UI 规范 V2](ui-spec.md) | 低饱和色板、桌面/手机线框、录音状态、空白/错误、编辑/版本/下载和可访问性 |
| [Agent 输出规范 V1.1](agent-output-standard.md) | 参考PDF/XLSX格式、总体框架与章节映射、默认单版、跨章节同步、纪要PDF与正式方案审核区别 |

推荐主栈为 React/TypeScript/Vite 自有界面、FastAPI、PostgreSQL+pgvector、私有对象存储、AudioWorklet/Worker+OPFS/IndexedDB、可换中文ASR、LangGraph+PostgreSQL checkpointer、Chromium纪要PDF worker。浏览器保存和Agent检查点独立，不承诺锁屏/后台持续采集或零损失；设备支持、尾部损失、字体与成本需开发PoC测量。

## 历史文档与替代关系

2026-10-14 的[功能文档 V1](functional-spec.md)和[开发文档 V1](meeting-agent-technical-design.md)保留原文用于追溯，其会后转写、PDF后续和旧导航/额度不再代表当前范围；如与V3冲突以项目交付设计V3和最新输出规范为准。V2是文档修订，不是甲方项目分期。

2026-10-12 的[旧售前方案](../../01-%E5%95%86%E5%8A%A1%E4%B8%8E%E9%9C%80%E6%B1%82/%E5%AE%A2%E6%88%B7%E8%B5%84%E6%96%99/functional-spec.md)及[旧调研](<AI%20%E9%94%80%E5%94%AE%E5%8A%A9%E6%89%8B%20%E6%8A%80%E6%9C%AF%20%E8%B0%83%E7%A0%94.md>)面向“访谈到可运行Demo”，仅供后续独立扩展参考，本次不开发代码Demo。三个参考来源保持原样，其路径/版本指纹见输出规范。
