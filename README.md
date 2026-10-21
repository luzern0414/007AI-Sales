# 行序 AI 销售与项目交付助手

手机 Web 优先，入口为 **首页、项目管理、产品库、工作台**。项目资料、会议、问题和人工确认节点存入数据库，AI结合原文与背景持续整理。当前服务为本机版本，持续开发目标 active，尚未完成生产交付。

最新界面采用手机紧凑列表、进度环和统一时间轴。会议与流程节点并入概览，同名格式与同场资料归组，原件可按Markdown预览并维护提供方；内部设计资料和每日代码变化概括为开发进度。规则与接口见[紧凑工作台](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/compact-project-design.md)。

## 当前能力

| 模块 | 已实现 | 验证范围 |
|---|---|---|
| 首页 | 麦克风录音、本机事务保存、云端补传、录音段校验、会议文字自动保存与恢复、MD/PDF纪要 | Chrome隔离测试环境；合成音频断网补传与文字草稿恢复；PDF实际生成、文本与渲染检查 |
| 项目管理 | 可视化概览、八个固定流程节点、实际时间与确认依据、撤回审计、分类风险、会议/文档分离、文件版本/搜索/下载 | 接口/数据库回归；320/390px手机页面操作与刷新 |
| 产品库 | 产品管理、介绍PDF、脱敏演示链接、人工发布/撤下、面客字段白名单 | 接口与页面上传/发布/撤下；无真实客户产品预置 |
| 工作台 | 项目节点、交付日期、风险、已连接文档进度、5秒可见页面刷新 | 数据库计算与页面验证；文档勾选率不代表工程完成率 |
| 文档与AI | 完整原文分片分析、检查点续跑、背景/提示词持久化、证据风险、简短摘要、四类文档与导出 | 科创37329字转写及两份背景资料真实供应商分析成功；四类方案整体质量尚待人工审核 |
| 文档连接 | D:/Codes编号项目发现、docs标准目录、原件保留、哈希版本同步、摘要和会议导航落盘 | 本机目录同步及幂等/越界测试；云文档/Git连接器未实现 |

实时转写已部署本地 FunASR GPU 2pass（10097），CPU服务10096备用；平台认证WebSocket及原文保存已实测。完整录音补识别默认CPU，避免重复占用4GB显存。配置见[本地转写](config/funasr.md)和[GPU验证](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E5%BC%80%E5%8F%91%E8%AE%B0%E5%BD%95/funasr-gpu.md)。未配置服务时明确失败。方案默认完整单版，仅会议有明确分期原文时允许分期。输出规范见[Agent规范](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/agent-output-standard.md)。

## 启动

环境：Windows、Python 3.12、Node.js 22.12+、Chrome。手机录音需要可信 HTTPS；127.0.0.1仅供当前电脑访问。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
npm.cmd ci
npm.cmd --prefix web ci
Copy-Item .env.example .env
npm.cmd --prefix web run build
.\scripts\start.ps1
```

访问 `http://127.0.0.1:8765`。首次在本机创建管理员，无默认账号/密码。密码至少12字符；远程初始化必须配置SETUP_TOKEN。密钥仅放受限 `.env` 或环境变量。配置见[config](config/README.md)。

开发联调另开终端执行 `npm.cmd --prefix web run dev`，Vite代理 `/api` 到8765。正式预览由FastAPI提供构建后的静态文件；不要对外开放Vite开发服务器。

## 数据与目录

| 目录 | 用途 |
|---|---|
| server/ | 身份、项目、文件、录音、转写、方案与清单、文档同步、导出与备份 |
| web/src/ | React手机页面与通用组件；recording/为本机存储、重采样、录音worker |
| migrations/ | Alembic迁移；启动自动升级至head |
| tests/ | 隔离数据库、文件、模型契约与负向测试 |
| scripts/ | 启动、PDF渲染、备份校验与恢复 |
| data/ | 默认本机SQLite及私有文件；已忽略，不预置测试业务 |
| output/ | 隔离浏览器数据库、合成录音、截图与验证产物；不作为正式业务数据 |
| docs/01-商务与需求/ | `客户资料/` 放客户背景与会议资料；`方案文件/` 放需求清单、资料清单与方案；`报价与合同/` 放报价单、合同与变更确认单。 |
| docs/02-产品与开发/ | `设计文档/` 放产品、架构与接口设计；`开发记录/` 放计划、实现与变更记录。 |
| docs/03-测试与交付/ | `测试验收/` 放测试与验收证据；`交付资料/` 放部署、手册与培训资料；`产品宣传/` 放脱敏后的宣传物料。 |
| docs/素材/ | 集中存放配图；不属于八个分组的文件留在相应主目录。各分组写法见 [SOP](../SOP/README.md)。 |

默认SQLite是开发持久化实现。PostgreSQL连接驱动与迁移兼容定义已配置，但尚未实际运行验证；pgvector、对象存储、LangGraph检查点和生产部署仍是设计目标，不属于已完成功能。当前项目访问按创建人隔离，尚无团队共享与客户独立访问账号。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
npm.cmd --prefix web test
npm.cmd --prefix web run build
npm.cmd --prefix web audit --registry=https://registry.npmjs.org
```

浏览器验证用Playwright CLI和隔离实例，不向 `data/platform.db` 写入演示数据。结果与尚未验证事项见[开发记录](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E5%BC%80%E5%8F%91%E8%AE%B0%E5%BD%95/development-log.md)。新机器需要本地Chrome及可用中文字体；Word目录更新、图表完整规范、逐页渲染与正式方案PDF审核尚未完成。

## 备份与恢复

```powershell
.\scripts\backup.ps1 -Destination D:\Backups\sales-20261015
.\.venv\Scripts\python.exe scripts/storage-maintenance.py verify D:\Backups\sales-20261015
.\.venv\Scripts\python.exe scripts/storage-maintenance.py restore D:\Backups\sales-20261015 --database D:\Restore\sales.db --storage D:\Restore\files
```

备份从SQLite快照提取原件引用，校验文件SHA256；生成清单后才算有效备份。恢复只写全新目标，不覆盖已有数据；停服务后更改 `.env` 指向恢复位置，再启动并检查会议/文件下载。衍生PDF/WAV缓存无需备份，可由原件重建。此工具不支持PostgreSQL；生产数据库需原生备份和独立恢复演练。浏览器尚未上传的录音/草稿不在服务端备份中。

## 当前边界与后续工作

1. 本机真实ASR与模型已验证；物理手机iOS/Android、HTTPS、锁屏/来电及生产并发尚未验证，未录制区间无法还原。
2. 录音块本机保存/补传、连接前缓存、停止尾音与无正文时会后补识别已实现；部分实时转写缺口的精确补全和缓存清理策略仍待完善。
3. 文档修订保留旧版及依据；人工审核发布、格式规范完整自动校验、架构配图及Word/PDF逐页检查待补齐；现在均是讨论稿。
4. 分析具备持久任务和分片检查点，当前单进程后台队列；大量导入资料仍在回填。供应商可能超时，失败保留并可重试。方案生成仍受单次上下文容量限制，超限明确失败。
5. 团队权限、账号维护、远程文档连接器、生产可观测性与部署验收未完成。

当前节点、目录和AI上下文见[项目流程配置](config/project-workflow.md)，本轮设计见[开发计划](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E5%BC%80%E5%8F%91%E8%AE%B0%E5%BD%95/2026-10-15-project-workflow.md)，验证见[验收记录](docs/03-%E6%B5%8B%E8%AF%95%E4%B8%8E%E4%BA%A4%E4%BB%98/%E6%B5%8B%E8%AF%95%E9%AA%8C%E6%94%B6/2026-10-15-workflow-acceptance.md)。以下保留历史研究，历史“未编码”与旧导航仅描述当时状态。

---

## 2026-10-12 历史设计：把客户访谈变成可演示业务系统

状态：**方案草案，仅文档阶段**。调研日期：2026-10-12，Asia/Shanghai。

产品定位已由用户明确：面向软件公司、数字化服务团队的售前人员，用手机 Web 记录客户谈话，整理需求，经销售确认后生成简单、可运行的前后端业务系统 Demo。
本目录已整理功能方案、技术架构、数据/API 契约、开源选型、阶段验收及配置目录。尚未开发应用、安装依赖、调用付费模型、运行 ASR 或沙箱 PoC。

## 业务闭环

录音、上传文件或粘贴谈话 → 异步转写 → 与 AI 聊天澄清 → 有证据的需求草稿 → 销售确认冻结版本 → 选择模板和演示子集 → 有界 Agent 生成与验证 → 独立预览 → 私密分享 → 反馈形成新版本。

“聊天”指销售与 AI 讨论访谈笔记、补充信息及修订需求；首期没有客户在线即时通讯系统。
“可运行”要求实际后端 API、独立数据库、CRUD 和持久化验证；仅生成页面、图片或 LocalStorage 演示不满足目标。

## 手机端四个入口

| 底部入口 | 核心任务 |
|---|---|
| 首页 | 汇总真实业务数据，突出录音入口，继续最近会话、待确认需求、生成任务和跟进事项。 |
| Demo 广场 | 查看平台模板及本组织私有案例，使用脱敏模板，不自动公开客户资料。 |
| 生成 Demo | 从已确认需求挑选范围，创建生成任务，查看验证结果、预览和修订。 |
| 我的 | 管理个人项目/Demo、组织权限、存储保留和用量。 |

## 建议阅读顺序

1. [功能方案](docs/01-%E5%95%86%E5%8A%A1%E4%B8%8E%E9%9C%80%E6%B1%82/%E5%AE%A2%E6%88%B7%E8%B5%84%E6%96%99/functional-spec.md)：业务、页面、交互、失败处理与虚构案例。
2. [技术调研报告](<docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/AI%20%E9%94%80%E5%94%AE%E5%8A%A9%E6%89%8B%20%E6%8A%80%E6%9C%AF%20%E8%B0%83%E7%A0%94.md>)：证据、开源项目和取舍。
3. [技术架构](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/technical-design.md)及[数据与 API](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/data-and-api.md)：系统边界与契约。
4. [架构决策草案](docs/02-%E4%BA%A7%E5%93%81%E4%B8%8E%E5%BC%80%E5%8F%91/%E8%AE%BE%E8%AE%A1%E6%96%87%E6%A1%A3/0001-template-first-and-isolated-runtime.md)及[阶段与验收](docs/03-%E6%B5%8B%E8%AF%95%E4%B8%8E%E4%BA%A4%E4%BB%98/%E6%B5%8B%E8%AF%95%E9%AA%8C%E6%94%B6/phase-plan-and-acceptance.md)：选择理由、验证门槛。
5. [配置说明](config/README.md)、[配置目录](config/settings-catalog.md)及[模板目录](templates/README.md)：拟议政策和模板约束。

## 当前目录

| 路径 | 当前内容 |
|---|---|
| docs/01-商务与需求/ | `客户资料/` 放客户背景与会议资料；`方案文件/` 放需求清单、资料清单与方案；`报价与合同/` 放报价单、合同与变更确认单。 |
| docs/02-产品与开发/ | `设计文档/` 放产品、架构与接口设计；`开发记录/` 放计划、实现与变更记录。 |
| docs/03-测试与交付/ | `测试验收/` 放测试与验收证据；`交付资料/` 放部署、手册与培训资料；`产品宣传/` 放脱敏后的宣传物料。 |
| docs/素材/ | 集中存放配图；不属于八个分组的文件留在相应主目录。各分组写法见 [SOP](../SOP/README.md)。 |
| config/ | 配置说明和参数目录；没有可执行配置或真实密钥。 |
| templates/ | 三类业务模板的设计约束；没有模板源码。 |
| assets/ | 素材管理约定；没有图片或 UI 原型。 |
| .firecrawl/ | 官方资料原始抓取缓存，已被 .gitignore 忽略，不作为交付产品。 |

未来若进入开发，可另设平台前端、平台 API、worker、sandbox supervisor、模板源码和测试目录；这些代码目录本轮未创建。未来结构须在设计评审及 PoC 结论后确定。

## 主要建议

平台拟用 React + TypeScript + Vite + Ant Design Mobile，FastAPI + Pydantic + PostgreSQL，私有 S3 兼容对象存储；Celery 配 Redis 协议 broker，Valkey 是待兼容性验证的自托管候选。
Agent 首轮 PoC 拟用 OpenAI Agents SDK，显式接入百炼或 DeepSeek Chat Completions；SDK 名称不代表使用 OpenAI 模型服务，默认 OpenAI tracing 出口需关闭。
Demo 拟用 React + FastAPI + 每个预览独立 SQLite，采用 CRM-lite、工单、简单审批三个受控模板。手机访问服务端预览，不在手机浏览器运行 Python 后端。
平台与 Demo 的数据、凭证、网络和可注册主域分离；内部受限试点可评估加固 Docker，客户外部分享前须完成独立 runner 主机及 gVisor、微 VM 或适当托管沙箱的隔离 PoC。

## 结论的适用范围

公开资料已核查，项目推荐尚未获得用户设计批准。没有浏览器实测、模型准确率、生成成功率、价格或时延保证。录音仅计划支持前台麦克风，不承诺后台、锁屏或系统通话录音。
后续需确定部署地域、提供方账号与合同、预算、保留政策及第一优先模板；对应负责人和验证活动见[文档索引](docs/README.md)。

