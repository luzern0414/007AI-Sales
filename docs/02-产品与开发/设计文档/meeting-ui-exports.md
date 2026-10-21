# 会议开源参考、产品库、四页 UI 与中文文档导出

调研日期：2026-10-15，Asia/Shanghai。本文是调研与建议，不是已实现功能。现场客户会议为主要场景；浏览器麦克风录音为主，远程会议机器人不进入首版必需路径。仅更新本文件及 `.firecrawl/20261015-ui-*` 证据文件。

## 一、哪些开源项目适合借鉴或集成

### Takeaway

会议记录项目可借鉴录音、时间轴、转写编辑和本地优先体验，但没有一个经本次核验即可直接交付本项目全部要求。建议自建四页 Web 应用和可靠录音管线，集成文档解析、检索、排版组件；桌面会议助手只作设计和实现参考，会议机器人留作明确需要远程平台接入时的可选连接器。

### Cited Findings

本次核验 15 个项目/组件的官方 README 与许可证，另外核查 2 个排版 API 文档。以下表格中“建议使用位置”是本项目设计判断，不是上游承诺。

| 项目 | 官方已核实能力 / 形态 | 许可证及边界 | 建议使用位置 |
|---|---|---|---|
| Meetily | 本地会议录音、实时转写、摘要；README 明示单体 Tauri 应用，Rust 后端 + Next.js 前端。[README](https://github.com/Zackriya-Solutions/meetily/blob/main/README.md) | 社区代码 MIT；README 说明 PRO 是不同代码库，不能据社区 MIT 推断 PRO 功能可以自由复用。[LICENSE](https://github.com/Zackriya-Solutions/meetily/blob/main/LICENSE.md) | 参考录音状态、转写/摘要分离设计；不能当现成 Web SaaS 底座。 |
| Hyprnote（本次 README 称 anarlog，团队正在构建 char） | 无机器人、设备音频、本地 SQLite 与文件、Markdown 导出；可分别选择转写与文本智能提供方。[README](https://github.com/fastrepl/hyprnote/blob/main/README.md) | 社区 MIT；`enterprise/` 不受 MIT 授权，生产使用等需书面商业协议。[MIT](https://github.com/fastrepl/hyprnote/blob/main/LICENSE)、[Enterprise](https://github.com/fastrepl/hyprnote/blob/main/LICENSE.enterprise) | 参考实时记录、原始音频留存和模型供应商分离；不要复制商业企业组件。 |
| Vexa | 机器人进入 Google Meet、Teams、Zoom，流式输出带说话人的转写；支持自托管。README 对 Jitsi 明确写 live validation pending。[README](https://github.com/Vexa-ai/vexa/blob/main/README.md) | Apache-2.0 代码；托管服务与自托管能力范围不同；模型、云服务仍各有独立条款。[LICENSE](https://github.com/Vexa-ai/vexa/blob/main/LICENSE) | 可选远程会议连接器；现场麦克风录音无需机器人。 |
| Scriberr | 自托管音视频转写、内置录音、转写编辑/笔记、对录音问答、PWA，截图描述有跟随播放及文字定位跳转。[README](https://github.com/rishikanthc/Scriberr/blob/main/README.md) | 应用代码 MIT；其模型和提供方不因包装层 MIT 自动获得相同授权。[LICENSE](https://github.com/rishikanthc/Scriberr/blob/main/LICENSE) | 最接近可参考的 Web 会议记录界面；需要另建销售产品库、证据底稿、方案规则、录音恢复保障。 |
| Docling | PDF 版面、阅读顺序、表格、OCR、多格式输入，统一 DoclingDocument，可输出 Markdown/JSON，可本地执行。[README](https://github.com/docling-project/docling/blob/main/README.md) | 代码 MIT；README 明确 individual model usage 需核对原模型许可。[LICENSE](https://github.com/docling-project/docling/blob/main/LICENSE) | 复杂 PDF/扫描产品资料的首选验证对象；保留 JSON 及页码位置，不只保存扁平 Markdown。 |
| MarkItDown | 轻量 Python 多格式转 Markdown，保留标题、表格、列表、链接；README 强调面向文本分析而非高保真文档转换。[README](https://github.com/microsoft/markitdown/blob/main/README.md) | MIT；插件、Azure 或额外模型调用独立核实。[LICENSE](https://github.com/microsoft/markitdown/blob/main/LICENSE) | 普通办公资料快速解析路径；不能以其 Markdown 输出充当原文件的精确保真副本。 |
| Unstructured | 文件分区、预处理及各种格式 ingestion；本地 PDF 路径有 tesseract/poppler 等系统依赖。[README](https://github.com/Unstructured-IO/unstructured/blob/main/README.md) | 核心库 Apache-2.0；托管 API、inference 模型和系统依赖不能仅凭该许可概括。[LICENSE](https://github.com/Unstructured-IO/unstructured/blob/main/LICENSE.md) | 备选解析框架；若已用 Docling，不为同一流程同时引入三套重型默认依赖。 |
| pgvector | PostgreSQL 向量近邻检索；README 提供与 PostgreSQL 全文检索结合，RRF 或 cross-encoder 融合的说明。[README](https://github.com/pgvector/pgvector/blob/master/README.md#hybrid-search) | PostgreSQL 风格宽松许可，非 MIT。[LICENSE](https://github.com/pgvector/pgvector/blob/master/LICENSE) | 初始产品库使用 PostgreSQL + pgvector + 全文检索，减少独立数据库；中文分词单独验证。 |
| shadcn/ui | 可定制、可扩展、用于建立自己的组件库，Open Code。[README](https://github.com/shadcn-ui/ui/blob/main/README.md) | MIT；图标、所选底层组件、字体另查。[LICENSE](https://github.com/shadcn-ui/ui/blob/main/LICENSE.md) | 四页低饱和定制工作区的推荐 UI 基础。 |
| Radix Primitives | 低层 UI 组件，关注可访问性、可定制性，可用作设计系统底层。[README](https://github.com/radix-ui/primitives/blob/main/README.md) | MIT。[LICENSE](https://github.com/radix-ui/primitives/blob/main/LICENSE) | 对话框、下拉、标签页、键盘交互；选择实际锁定版本所用 primitive，不宣称全部 shadcn 版本固定依赖 Radix。 |
| Ant Design | React 企业 UI 库。[README](https://github.com/ant-design/ant-design/blob/master/README.md) | MIT。[LICENSE](https://github.com/ant-design/ant-design/blob/master/LICENSE) | 表格、复杂筛选与权限后台优先时的备选；不建议与整套 shadcn 同时大面积混用。 |
| Playwright | 浏览器自动化；`page.pdf` 提供 A4、页边距、背景、CSS 页面尺寸、页眉/页脚、PDF 缓冲输出等。[API](https://playwright.dev/docs/api/class-page#page-pdf) | Apache-2.0；Chromium、字体及镜像中其他依赖有各自许可。[LICENSE](https://github.com/microsoft/playwright/blob/main/LICENSE) | 纪要 HTML → Chromium PDF 导出服务；也是后续页面和导出可视验证工具。 |
| python-docx | Python 创建/修改 Word `.docx`，项目 README 指向官方文档。[README](https://github.com/python-openxml/python-docx/blob/master/README.md) | MIT；不包含 Microsoft Word/LibreOffice 的运行或字体授权。[LICENSE](https://github.com/python-openxml/python-docx/blob/master/LICENSE) | 售前方案按指定 Word 模板生成；它本身不是 PDF 排版引擎，不能直接宣称可转 PDF。 |
| WeasyPrint | HTML/CSS 到 PDF 的专用排版引擎；支持字体配置、PDF 链接和书签。[README](https://github.com/Kozea/WeasyPrint/blob/main/README.rst)、[API](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html) | BSD-3-Clause。[LICENSE](https://github.com/Kozea/WeasyPrint/blob/main/LICENSE) | 如果复杂分页要求超过 Chromium 可控程度，可用作独立服务备选；需重测 CSS 与图表静态化，不默认与浏览器预览一致。 |
| ReportLab | 以 Python 直接构造 PDF 与图表的 toolkit，README 区分开源 toolkit 与商业 RML。[项目镜像 README](https://github.com/MrBitBucket/reportlab-mirror/blob/master/README.txt) | 开源 toolkit 使用 BSD 风格许可，商业 RML 另计；本次证据是项目 GitHub 镜像，不应把它称成唯一上游权威。[LICENSE](https://github.com/MrBitBucket/reportlab-mirror/blob/master/LICENSE) | 固定报表备选；复杂中文长方案维护成本需试验，不作首选。 |

上游营销措辞不等于本项目验收依据。尤其 Scriberr README 的赞助内容包含说话人识别“100%”措辞，本项目不继承该承诺；现场多人共享麦克风的姓名识别需人工绑定，真实姓名、岗位及决定权不能凭声纹推断。[Scriberr README](https://github.com/rishikanthc/Scriberr/blob/main/README.md)

### Inferences

- 不对整个上游仓库、模型、云 API、字体打包作“全 MIT、商用无约束”的结论；锁定组件版本和来源，按文件及运行资产维护 SBOM/许可台账。MIT/Apache/BSD 的版权及 NOTICE 保留义务按各自文本落实。
- Web 前端推荐沿用项目现有 React 技术栈（若存在），或 Next.js + TypeScript + shadcn/ui；不为套用桌面项目而搬入 Tauri。复杂行政配置较多时才选 Ant Design；业务工作区保持同一设计语言。
- 产品库解析主路径推荐 Docling 做 PDF，结构化 XLSX 用专用表格读取器，常见 DOCX/PPTX 可评估 MarkItDown。只有实测证明必要才引入 Unstructured 备选，避免依赖和模型重复。
- Vexa 的远程机器人不是现场录音容灾方案；即使以后接入，仍独立保存原始音频、录音分片、转写事件和确认记录。

### Gaps

- 没有实测以上项目的中文会议准确率、现场回声与噪声表现、长时录音恢复、导出质量；不提供排名、百分比或无测量的容量保证。
- 本次抓取的 README/许可证是在线分支快照，不是锁定提交的历史审计。实施前须固定 commit/release 并复查子目录 LICENSE、NOTICE、模型卡与依赖。
- Firecrawl CLI 通过 `npx --yes firecrawl-cli --status` 可运行（v1.26.3），但未认证；GitHub API 本机出口返回 403 rate limit。因此采用公开官方 Raw README/LICENSE、官方文档直接 HTTP 的只读降级，不使用第三方搜集文章代替原始证据。未进行登录或更改认证。
- `python-docx.readthedocs.io` 在本次环境返回 403；其能力依据官方仓库 README 及许可证，不声称已阅读被阻止页面。

## 二、产品库如何支撑有证据的方案和需求清单

### Takeaway

产品库应保存“已核实的产品能力、版本、证据与授权范围”，而不是只把 PDF 切片后交给模型。会议事实、客户需求、产品事实和乙方建议在单一版本底稿中显式区分，四种文档共享引用、编号和范围规则。

### Cited Findings

- Docling 支持统一结构及 JSON 输出，并具有 PDF 页序、版面、表格理解，适合建立能追溯页码/位置的产品资料解析结果。[Docling README](https://github.com/docling-project/docling/blob/main/README.md)
- MarkItDown 是面向文本分析的转换器，不能将其输出质量推断为 PDF、Word、Excel 的完整保真。[MarkItDown README](https://github.com/microsoft/markitdown/blob/main/README.md)
- pgvector 官方明确提出与 PostgreSQL 全文检索组合，并给出 RRF 和 cross-encoder 方案；这支持同一数据库内的混合检索选择，但中文领域召回仍需本项目测试。[pgvector Hybrid Search](https://github.com/pgvector/pgvector/blob/master/README.md#hybrid-search)
- 当前项目输出规范要求共用一个证据底稿、稳定需求编号、明确事实/建议/未知、禁止无依据分期、未经核查的功能不能写成交付承诺。[本地 Agent 输出规范](</D:/Codes/007AI Sales/docs/02-产品与开发/设计文档/agent-output-standard.md>)
- 最新源规范要求：总体框架和各章节有映射、设备与 AI 统一描述模板、新增内容跨章节同步、完整方案默认不分期、先 Word 审核再生成正式 PDF。[本地格式规范](</D:/Codes/方案格式规范.txt>)

### Inferences

建议的产品库实体如下。字段是设计提案，未声称已开发。

| 实体 | 最少字段 | 作用 |
|---|---|---|
| Product | `id/name/vendor/owner/status` | 可查产品卡与业务归属。 |
| ProductVersion | `id/product_id/version/effective_from/effective_to/review_state` | 旧版功能、最新功能不混用。 |
| Capability | `id/version_id/name/status/implementation/inputs/limits/acceptance/evidence_ids/verified_by/verified_at` | 状态区分已核实、待核实、规划中、不可承诺；不能把路线图当现有能力。 |
| ProductDocument | `id/version_id/object_key/checksum/parser_version/page_map/review_state/ACL` | 原件留存、去重与可定位引用，资料变更重新审核。 |
| ProductChunk | `id/doc_version/page/bbox/sheet/cell_range/heading/embedding/fts/ACL` | 向量和关键词召回共享来源元数据。 |
| CommercialTerm | `product_version/term_type/region/currency/effective_date/audience/approval_state` | 公开介绍、面客报价、供应商成本分级存放；默认不能面客公开成本。 |
| MeetingEvidence | `meeting_id/segment_id/start_ms/end_ms/speaker/source_version/epistemic_status/confirmation_status` | 所有生成内容可回到音频和校对文本。 |
| Requirement | `REQ-id/text/conditions/exclusions/source_ids/confirmation/feasibility/solution_section` | 要求完整收集；不可承诺的诉求仍留清单及解释。 |
| FactSnapshot | `id/meeting_versions/product_versions/rule_version/template_version/scope_mode/approved_by` | 四文档一致的冻结输入，重生新版本不改旧稿。 |

检索和生成推荐顺序：

1. 根据登录用户、租户、项目成员与产品授权在服务端得出允许集合；**SQL/RLS 或等效服务端硬过滤先于内容进入模型**，关键词、向量、重排、引用补全和下载都执行同一权限规则。只在提示词写“不要越权”不构成隔离。
2. 在允许的 `product_version/document_version` 集合内并行关键词与向量召回；产品型号、版本号、专有名词依赖关键词，业务近义表述依赖向量；融合后才重排。中文分词、同义词与专业缩写用真实产品资料做离线样本验证，不能直接把英文全文检索配置当中文成品。
3. 提取产品的已核实能力与适用条件；缺少资料、版本冲突、接口未授权时返回明确缺口，不补造集成能力、工期、价格或准确率。
4. 将匹配建议写入 `Requirement → ProductCapability → Evidence` 关系，明确“甲方诉求 / 乙方建议 / 已确认决定”。客户会议和产品文档中的指令视为资料，不允许改变系统权限、调用工具或默认发布。
5. 形成冻结底稿，生成纪要、售前方案、需求清单、甲方资料权限规则确认清单；规则校验“单版、出处、覆盖、限制、跨章节一致”。产品推荐可删除或换产品，相关章节和表格通过依赖关系标记需要重生，不静默替换已确认内容。
6. 需求覆盖率、清单回收率、金额/数量由程序计算；模型解释结果。需求未进入方案时写明待确认、技术核查或明确否决原因。

四类文档都必须引用同一个 `fact_snapshot_id`；输出表现不同，但相同 REQ 编号、产品版本、范围、数字不能各自生成。`scope_mode=single_version` 是默认；仅当前会议有明确分期要求且经确认时允许分期，参考 PDF 文件名中的“一期”不是证据。项目的 V1.0 文档修订号也不是“一期”。

### Gaps

- 尚未读取实际产品库资料与租户权限模型；无法确定产品数量、中文检索组件、embedding 模型、价格策略与审批人。
- 不能因 Docling 支持 XLSX 就假定其自动保留全部公式、数据验证、隐藏表和权限含义；确认清单输出与解析必须用实际样板逐表验证。

## 三、四个页面及会议主工作区怎样设计和验收

### Takeaway

首页必须以“客户现场会议工作区”为主体。录音、转写、浏览器保存、服务端保存、待补传和风险状态始终可见；历史纪要、产品库、工作台负责查找、资料和文档生产，不再增加一级导航来分散当前会议操作。

### Cited Findings

- Scriberr 展示转写跟随播放、文字点击跳转，支持内置录音、注释和 PWA，可作为会议记录信息架构参考。[Scriberr README](https://github.com/rishikanthc/Scriberr/blob/main/README.md)
- shadcn/ui 提供可以自主定制的组件代码；Radix 强调可访问性与定制，适合建立统一的键盘、焦点和对话框基础。[shadcn README](https://github.com/shadcn-ui/ui/blob/main/README.md)、[Radix README](https://github.com/radix-ui/primitives/blob/main/README.md)
- 本地规范已有藏青、石板灰、雾蓝和暖金的低饱和色板，且要求待确认、来源及修订状态明确。[Agent 输出规范](</D:/Codes/007AI Sales/docs/02-产品与开发/设计文档/agent-output-standard.md>)、[格式规范](</D:/Codes/方案格式规范.txt>)

### Inferences

以下均为本项目设计规格，不是上游现成功能或已经验收的页面。

| 一级页面 | 主区域及操作 | 必需状态和数据 |
|---|---|---|
| 首页 | 当前会议；选项目/客户与麦克风；开始/暂停/继续/结束；实时转写和手工速记；重点/决定/疑问标签；底部时间轴；结束后进入校对、生成纪要。 | 麦克风输入电平、录音计时、实际音频累计、ASR 延迟、临时/已定稿转写、本地已存到的时间、服务器已存到的时间、待补传秒数、异常恢复入口。 |
| 历史纪要 | 按项目、客户、时间、状态搜索；列表/卡片；进入会议详情、回放、逐字稿、纪要版本、待确认项、关联方案；下载 PDF 和 MD。 | 录音是否完整、缺口、转写是否校对、当前纪要版本、PDF 任务状态、关联底稿版本、发布与审批记录。 |
| 产品库 | 产品卡/表格、分类与搜索；上传资料；产品详情中的能力、限制、版本、来源与审批；可维护标准方案片段、适用场景。 | 解析进度和失败、文档版本、能力核实状态、可见范围、最新有效期、资料待补；成本/报价需权限单独展示。 |
| 工作台 | 左侧会议/项目输入与产物树，中间 Markdown/结构化编辑，右侧需求、产品证据、资料缺口；生成/重生成选定章节；导出任务。 | 纪要、售前方案、需求清单、甲方确认清单；共享底稿版本；来源引用、待确认、规则检查、需求覆盖；审核通过/失败/旧版本提示。 |

桌面首页文字线框（推荐约 1440px 视口；具体值为设计初稿）：

```text
┌──────────────┬────────────────────────────────────────────────────┐
│ 销售助手     │ 客户 / 项目 > 当前会议             账户 / 项目切换   │
│ 首页         ├────────────────────────────────────────────────────┤
│ 历史纪要     │ 客户需求沟通会   2026-10-15         录音中 00:24:18 │
│ 产品库       │ [麦克风]  输入电平  [暂停] [结束会议] [标记重点]     │
│ 工作台       ├───────────────────────────────┬────────────────────┤
│              │ 实时文字                      │ 会议要点           │
│ 最近项目     │ 00:22:05 发言人 A   已定稿      │ 人工速记 / 重点    │
│ 客户 A       │ 原话 + 重点 + 点击回放         │ 待确认问题         │
│ 客户 B       │ 00:24:16 发言人 B   转写中…     │ 已标记决定         │
│              │ [跟随最新：开] [搜索]          │ 推荐追问（建议）   │
│              ├───────────────────────────────┴────────────────────┤
│              │ 音频时间轴 / 重点 / 暂停区间 / 异常缺口             │
│              │ 本机已保存 00:24:16 · 服务端已保存 00:24:12         │
│              │ 待补传 4 秒 · 转写已定稿至 00:24:09 · 网络正常      │
└──────────────┴────────────────────────────────────────────────────┘
```

上图时间和客户仅为 UI 示意，不是录音完整性或性能承诺。录音计时与 ASR 定稿时间分开，不能用“文字已保存”替代“音频已保存”。

| 视觉项目 | 设计初稿 |
|---|---|
| 布局 | 左侧导航约 220px；顶部 64px；内容外边距 24px；会议文字为主要可读区域，右栏约 320px；1280 以下右栏可折叠。 |
| 色板 | 主色 `#1F3A5F`，次色 `#3E5C76`，辅助 `#7489A3`，背景 `#F5F7FA`，卡片 `#FFFFFF`，边线 `#D5DDE6`，正文 `#1F2933`，次字 `#66727F`，人工确认/风险暖金 `#A8875A` 配 `#F7F2EA`。 |
| 字体 | Web 用本地可用的中文系统字体栈，正文 14–16px、行高 1.6；时间和保存进度数字用等宽/表格数字；正式文档字体按格式规范独立处理。 |
| 层次 | 标题清楚，卡片少而大；圆角约 10px，细边框、轻阴影；线性图标；不使用多色渐变、拟真机器人、无价值的发光背景。 |
| 录音强调 | 用录音图标、文字和轻量状态点，不能只依赖红绿颜色；暂停按钮与结束按钮位置稳定，结束前展示待补传但不能阻止当前分片落盘。 |
| 实时转写 | 临时文字弱化但足够对比，定稿替换同一片段 ID；滚动读历史时停止自动跳转，显示“有新内容”；选文后可标重点、校对、建立需求。 |
| 来源编辑 | 每条来源用时间标签或页码标签，点击右侧打开原话和音频定位；引用更新需要重新检查，不能用来源装饰来掩盖不一致。 |
| 动效 | 仅用于状态变更和反馈；遵从 reduced motion；转写更新不得挤走当前光标。 |
| 小屏 | 导航折叠，保留底部录音状态和操作；右侧要点移至标签页，表格横向滚动；移动端长时间后台录音需实测，不承诺跨系统锁屏持续。 |

会议容灾 UI 必须围绕真实状态而非虚拟百分比。事件如下：

| 事件 | 必需 UI 行为 | 后续恢复 |
|---|---|---|
| 网络断开 | 显示“离线录音，正在本机保存”，服务端时间停止，待补传增长；录音与本地写入独立继续。 | 网络恢复后按分片序号补传并校验，不重复显示/计算。 |
| ASR 服务失败 | 显示“录音继续，转写暂时不可用”；不要把文字不动误称录音停止。 | ASR 恢复或会后批转写补齐；不覆盖人工校对而无版本记录。 |
| 麦克风被拔出/权限撤回 | 立即显式显示录音停止和最后确认写入时间；已落盘不丢；允许重新选设备继续同会话新片段。 | 缺失区间标记在时间轴与纪要来源完整性中，不伪造静音文本。 |
| 本地存储空间不足/写入失败 | 明确告警和可操作的安全停止/下载已存材料，不能继续显示“安全保存”。 | 已在服务器的分片仍可恢复；仅上传成功不能替代本地失败告警，二者分别显示。 |
| 页面刷新/浏览器崩溃后重开 | 首页可恢复草稿卡显示会话、最后本机/服务端确认位置、未补传量。 | 扫描 IndexedDB 会话日志，恢复并补传已提交分片；不能自动恢复崩溃前尚未产生/落盘的最后数据。 |
| 浏览器关闭 | 关页提示和明确“保留本机待补传”；尽力上传仅为补充，不能依赖 unload/sendBeacon 完成大音频上传。 | 回到同浏览器/同源且数据仍在时补传；换设备、清缓存、浏览器驱逐数据均不能许诺必定恢复。 |
| 其他标签页打开同会话 | 提醒已在另一页录制，使用页面锁/租约决定唯一录音方。 | 可查看状态，但不能重复采集和生成冲突序号。 |

可测试的 UI 验收项：

1. 用户只看首页就能辨认“音频录制正常 / 临时文字 / 定稿文字 / 本地持久化 / 服务端持久化 / 待补传”。
2. 录制时断网 60 秒再恢复，时间轴和片段列表能显示本地继续录制、补传、服务端确认追平；无重复、未确认分片不会假装已保存。60 秒是验收场景建议而非系统保证。
3. ASR 停止但音频仍在录制时，状态明确区分，结束会后能提交批处理补齐。
4. 每个已定稿片段可回放到对应时间；手工校对保留原转写和修改人/版本。
5. 刷新恢复、权限撤回、设备拔出和本地写入失败有可见状态；只验证“beforeunload 提示”不算容灾通过。
6. 键盘可完成选择输入设备、开始/暂停、标重点、搜索和跳转；焦点可见，弹窗焦点管理和 screen reader 状态可感知；实时文本不每个字触发打断式播报。
7. 未核实产品能力不能生成肯定交付承诺；点击出处能够落到来源；跨项目越权检索、预览与下载被服务端拒绝。
8. 新会议无明确分期时，纪要、方案、清单、页面标签和导出名均不自动出现一期/二期；业务模块不等于期次。

### Gaps

- 本次没有创建或运行 UI，因此文字线框、布局尺寸、颜色组合仍需在真实中文长文本和多设备上完成视觉、对比度与可访问性检查。
- 具体录音分片容灾机制由独立实时音频调研汇总；UI 不得把目标恢复指标写成绝对“零丢失”。

## 四、PDF 纪要和方案/清单文件怎样生成

### Takeaway

本次明确需要“可下载的 PDF 会议纪要”，应作为必需能力。纪要从同一冻结结构生成 MD/PDF；售前方案和清单以 Markdown 为必需交付，后续正式方案遵循现行格式规范：先出 Word 审核，确认后由该已审 Word 转 PDF，不能把两条流程混成一键未审发布。

### Cited Findings

- Playwright `page.pdf` 使用 print CSS，支持 `format`、`margin`、`preferCSSPageSize`、`printBackground`、`displayHeaderFooter`、`headerTemplate`、`footerTemplate`；页眉页脚模板内脚本不会执行，页面样式不可直接用于模板。[Playwright PDF API](https://playwright.dev/docs/api/class-page#page-pdf)
- WeasyPrint API 支持 `FontConfiguration`、PDF 超链接和书签，适合专用排版服务备选。[WeasyPrint API](https://doc.courtbouillon.org/weasyprint/stable/api_reference.html)
- python-docx 的项目目标是创建和修改 Word 文件；Word/PDF 转换要有另外的排版程序。[python-docx 项目](https://github.com/python-openxml/python-docx)
- 源规范要求 A4，页边距上 2.5cm/下 2.3cm/左 2.5cm/右 2.5cm，黑体/宋体/Times New Roman，表头跨页重复、行不跨页拆分、逐页检查 PDF，工作流程先 Word 审核再正式 PDF。[本地格式规范](</D:/Codes/方案格式规范.txt>)
- 当前本地输出规范仍写“平台首版以 MD 为必要输出，Word/PDF 后续”，应由主文档依据本次新用户明确要求升级为“纪要 PDF 必需”，保留正式方案审核规则。[本地输出规范](</D:/Codes/007AI Sales/docs/02-产品与开发/设计文档/agent-output-standard.md>)

### Inferences

建议规范更新说明：旧文档中“一律 Word 审核后再 PDF”的表述用于正式售前方案；本次用户要求的会议纪要 PDF 可由纪要确认或明确标注讨论稿后直接导出。PDF 下载本身不自动代表甲方批准；未确认内容、录音缺口和重要未知仍在纪要中显示。

| 输出物 | 必需文件 | 可选后续文件 | 审核与一致性 |
|---|---|---|---|
| 会议纪要 | MD + PDF | DOCX | 两者同一 `minutes_revision_id/fact_snapshot_id`；讨论稿保留待确认标识。 |
| 售前解决方案 | MD | DOCX；审核后正式 PDF | 模板映射、能力限制、跨章节一致性检查；PDF 从获批 DOCX 对应修订导出。 |
| 需求清单 | MD | XLSX 填报版 | REQ 编号不变；宽表拆为按编号关联的多表，不丢字段。 |
| 甲方资料/权限/规则确认清单 | MD | XLSX 多工作表填报版 | 主清单、统计、填写模板共用同一行级数据与状态，不复制样板业务或默认已交件。 |

纪要导出管线：

```text
会议音频/转写修订 + 产品资料版本 + 人工确认
              ↓
冻结 FactSnapshot → 校验 MinutesDocument 结构树
              ├→ Markdown Renderer → .md
              └→ 安全 HTML Template + 本地字体/静态图
                           ↓
                    Chromium PDF Worker
                           ↓
                  结构检查 + 逐页渲染检查
                           ↓
                对象存储 → 授权下载 / 任务状态
```

`MinutesDocument` 最少包含基本信息、参会者确认状态、记录完整性、现状痛点、需求约束、决定、待确认、行动项、来源索引；每个 block 有稳定 ID，表格、图形、引用是结构元素而非任意 HTML。MD 与 PDF 都读取此树；不能分别让模型写一次导致数字和结论漂移。

| PDF 实现点 | 具体设计 |
|---|---|
| 异步任务 | `document_revision_id + format + template_version + renderer_version + font_bundle_hash` 形成幂等键；任务 queued/running/ready/failed。重复点击返回同一有效任务或现成对象。修订后新导出，旧文件保留版本号。 |
| 下载权限 | 生成任务和下载时均校验用户/租户/会议权限；对象 key 不作公开授权；短时签名 URL 或后端鉴权代理，记录审计；撤销授权后服务端阻止新下载，URL 有效期要与该策略一致。 |
| 中文字体 | 文件作为经过许可的本地字体包加入 renderer；按规范用黑体/宋体/Times New Roman。服务器没有这些字体时不得静默替换并宣称达标；需合法部署相应字体，或明确提出可授权替代字体待用户接受。字体包必须记录许可、校验和、嵌入许可与渲染版本。 |
| A4 版式 | print CSS `@page` 设 A4 与边距；`preferCSSPageSize`、`printBackground` 显式配置；正文 12pt、1.5 倍行距，表内容 10.5pt；视觉规范可以裁剪为适合纪要的模板，不能声称普通 Web 样式自动符合 Word 规范。 |
| 表格跨页 | `thead` 按 table-header-group 重复；普通行避免页内拆分；按内容拆分超大表与超过一页高的单元格，重复需求 ID 与“续表”；不可仅给整张长表 `break-inside:avoid` 造成大空白。 |
| 标题与图片 | 标题尽量随下段，图前引导语和图题随图；图表、SVG/PNG 本地静态化，中文标签实际渲染后检查；不能把超宽截图直接缩成不可读文字。 |
| 页码页眉 | 页眉/页脚使用固定安全模板；因 Playwright 模板不继承页面 CSS，独立内联字体、字号与样式。显示页码/总页数、版本和项目名，页边距为其留足空间。 |
| 引用 | 页面内使用稳定来源锚点；在线可链接回会议时间，离线 PDF 仍显示“00:12:34、发言片段 ID / 文件名、页码、工作表、单元格、版本”。不将短期对象下载 URL 当永久证据链接，不在 PDF 埋入身份令牌。 |
| 资源完整 | 等待字体 ready 和本地图片 decode 完成后打印；外链图片、CSS/字体默认不允许，生成时禁止任意远程资源请求；用户材料和模型文本转义/净化，避免 renderer 请求内部 URL。 |
| 失败处理 | PDF 失败保留可编辑的 MD 和结构树；前端显示具体可操作错误，例如字体缺失/页面过大/资源异常，允许同版本重试；不得用空白 PDF 标任务成功。 |
| MD/PDF 一致 | 内容哈希、版本、需求 ID、决定数、行动项数和关键数字能从结构树追溯；PDF 提取文本比对关键文本，阅读顺序和截断仍需渲染检查。 |

正式方案的 Word 路径建议单独任务流：`FactSnapshot → ProposalDocument → python-docx → DOCX 预览/审阅 → approved revision → Word 或兼容排版引擎转 PDF → 逐页检查`。Windows Word 自动化和 Linux LibreOffice 转换的字体、目录、分页存在运行环境差异，要在目标部署验证；不把 python-docx 视为 PDF 引擎，也不许诺在线编辑器预览与 Word 完全一致。

中文排版验收建议：

| 样本 | 检查点 |
|---|---|
| 短会纪要 | 1–3 页，基本信息、决定、待确认、来源完整，MD/PDF 内容一致。 |
| 长会纪要 | 多页中文段落、多人发言、数字/金额/否定条件，页码正确，无空白大片、孤立标题、缺字和字块。 |
| 长需求表 | 表头重复、列宽可读，长行/超页高单元格合理拆开，REQ 编号和续表有对应，不横向裁切。 |
| 图表与字体 | 字体实际嵌入/替换情况检查，图表放大后中文清楚，本地字体缺失时任务失败或明确降级，不能假成功。 |
| 源链接 | PDF 内跳转可用，离线仍可读时间/页码索引，不泄露内部成本和授权令牌。 |
| 异常任务 | 网络断开可查询任务，重复导出幂等，PDF 失败 MD 可下载；改稿后旧 PDF 标“旧版”，不会误配新版本。 |
| 权限 | 无权限用户不能创建他人会议的 PDF、查看导出状态或下载对象，包含猜测任务 ID、对象 key、过期链接的场景。 |
| 视觉检查 | 开发验证时渲染每页成图检查，模板改动重复此项；正式方案交付沿用逐页人工检查要求。自动文本存在不等于版式正确。 |

### Gaps

- 本次未安装字体、运行 Chromium PDF 或生成 DOCX/PDF，因此上述是待开发和待验收设计；没有输出任何伪造 PDF 示例或截图。
- 黑体、宋体、Times New Roman 的部署/嵌入许可需由实际字体来源核验；不能从一台 Windows 已安装字体推导可复制到 Linux 容器。
- 本地格式规范已直接核实 SHA-256：`73798EC292B7408B0427D861EA086CDDFA11911FB55475B34EF03FD04543A009`。若后续源文件变化，模板需新版本和审核，历史文件不自动改写。
- 证据快照在 `.firecrawl/20261015-ui-{project}-readme.md`、`*-license.md` 及同名 `.json`（记录 source_url/retrieved_at）；排版原文在 `20261015-ui-playwright-pdf.txt`、`20261015-ui-weasyprint-api.txt`；企业许可在 `20261015-ui-hyprnote-commercial.txt`。这些是在线来源副本，不是应用代码。
