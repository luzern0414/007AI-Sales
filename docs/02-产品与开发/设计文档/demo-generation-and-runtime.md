# AI 销售助手：Demo 生成、运行隔离与手机交付调研

调研基准：2026-10-12，Asia/Shanghai；面向软件公司售前，为客户生成可演示的业务系统。

本记录只形成方案，不创建应用代码、项目脚手架、镜像或依赖。事实、设计建议、尚待 PoC 的结论分别标示。

方法：先用 Firecrawl 抓取官方 README、LICENSE、产品文档；免费档出现 rate limit 后改用公开官方 HTTP。原始材料保存在 `.firecrawl/demo-*`，其中 HTML 转文本文件用于阅读；404 页面不作为事实证据。

## 1. 生成路线与开源项目：优先模板加受控 Agent

### Takeaway

**建议：MVP 采用三类固定业务模板、经过销售确认的需求快照、单个受控 coding worker 和实际功能验证。** 复用整套 builder 或自由生成可留到后期，不能把“生成了页面”定义为“前后端系统可演示”。

### Cited Findings

| 项目 | 当前官方定位和集成入口 | 许可边界 | 本项目的用途判断 |
|---|---|---|---|
| bolt.diy | Web 开发工作台，WebContainers 中的 Node.js 环境；支持 starter、文件修改、ZIP 导出和部署。[README](https://github.com/stackblitz-labs/bolt.diy/blob/main/README.md) | 仓库 MIT；WebContainer API 商业生产另需授权。[LICENSE](https://github.com/stackblitz-labs/bolt.diy/blob/main/LICENSE)、[商业授权](https://webcontainers.io/enterprise) | 参考交互和 patch/preview 工作流；整站嵌入不是直接得到手机 SaaS 后端。 |
| OpenHands Agent Canvas | 当前主仓 README 标题为 Agent Canvas，定位为自托管 coding agent 控制中心；核心执行是 Agent Server REST API。[README](https://github.com/OpenHands/OpenHands/blob/main/README.md) | 当前主仓 LICENSE 为 MIT。[LICENSE](https://github.com/OpenHands/OpenHands/blob/main/LICENSE) | 参考调度与日志；不需要在售前产品中照搬开发者控制台。 |
| OpenHands Software Agent SDK | Python、TypeScript、REST/WebSocket API；agents 可执行本地任务，也可经 Agent Server 使用 Docker/Kubernetes 临时 workspace。[README](https://github.com/OpenHands/software-agent-sdk/blob/main/README.md) | SDK/Agent Server 仓库 MIT；云服务是另外的服务关系。[LICENSE](https://github.com/OpenHands/software-agent-sdk/blob/main/LICENSE) | 将来需要更完整 coding agent 时，比改造整套 Canvas 更适合作执行适配层。 |
| gpt-engineer | CLI 从 prompt 文件生成或改进代码；README 自称代码生成实验平台，并推荐维护中的 CLI 另看 aider。[README](https://github.com/AntonOsika/gpt-engineer/blob/main/README.md) | MIT。[LICENSE](https://github.com/AntonOsika/gpt-engineer/blob/main/LICENSE) | 历史工作流参考；不作为新 MVP 的维护依赖。 |
| Dyad | 本地 AI app builder，README 强调 Mac/Windows 与用户自带模型 API key。[README](https://github.com/dyad-sh/dyad/blob/main/README.md) | `src/pro` 外 Apache-2.0；`src/pro` 为 FSL-1.1-ALv2。[根许可](https://github.com/dyad-sh/dyad/blob/main/LICENSE)、[Pro 许可](https://github.com/dyad-sh/dyad/blob/main/src/pro/LICENSE) | 适合销售/研发桌面原型工具；移动多租户产品需要重做服务化边界。 |

当前维护状态采用官方声明和仓库元数据，**不按 stars 推断可生产性**。

| 仓库 | 2026-10-12 快照 | 对选型的影响 |
|---|---|---|
| bolt.diy | `archived=false`；`pushed_at=2026-10-11`。[GitHub API](https://api.github.com/repos/stackblitz-labs/bolt.diy) | 最近有活动；仍须检查固定版本的构建、供应链和商业 runtime 条款。 |
| OpenHands/OpenHands | `archived=false`；`pushed_at=2026-10-12`。[GitHub API](https://api.github.com/repos/OpenHands/OpenHands) | 当前仓库边界已经变化，旧教程不能当成当前 API 规范。 |
| OpenHands/software-agent-sdk | `archived=false`；`pushed_at=2026-10-11`。[GitHub API](https://api.github.com/repos/OpenHands/software-agent-sdk) | SDK 与 UI 分仓，集成应锁 SDK/Agent Server 版本。 |
| gpt-engineer | 旧组织 URL 重定向到 `AntonOsika/gpt-engineer`；`archived=true`；`pushed_at=2025-05-14`。[GitHub API](https://api.github.com/repos/gpt-engineer-org/gpt-engineer) | 已归档，必须避免把旧开源 CLI 等同于持续发展的商业 builder。 |
| Dyad | `archived=false`；`pushed_at=2026-10-12`。[GitHub API](https://api.github.com/repos/dyad-sh/dyad) | 有活动但存在混合许可，不能只看 API 自动识别的 SPDX 标签。 |

- OpenHands SDK README 明确划分 SDK/Agent Server、浏览器 TypeScript client、Agent Canvas UI 和 automation 调度仓库的职责。[仓库边界](https://github.com/OpenHands/software-agent-sdk/blob/main/README.md#repository-boundaries)
- bolt.diy README 提供 UI/本地启动/框架 starter 等能力，但本轮没有找到可直接承担多租户售前平台的稳定公开 headless SaaS API 契约。[README](https://github.com/stackblitz-labs/bolt.diy/blob/main/README.md)
- Dyad FSL Pro 条款把“向他人提供替代产品或相同/实质相似功能的商业产品/服务”列为 Competing Use；具体版本第二周年后转 Apache-2.0，不能把所有 Pro 版本提前视作 Apache。[Pro LICENSE](https://github.com/dyad-sh/dyad/blob/main/src/pro/LICENSE)
- gpt-engineer README 将商业 `gptengineer.app` 单独说明；开源 CLI 的 MIT 许可不能证明商业服务有开源代码或可嵌入后端。[README](https://github.com/AntonOsika/gpt-engineer/blob/main/README.md#relation-to-gptengineerapp-gpt-engineer)

### Inferences

三条路线的取舍是设计建议，不是已测性能结论。

| 路线 | 可交付物 | 主要代价 | 手机端与国内部署 | 建议 |
|---|---|---|---|---|
| A. 固定模板 + 受控 Agent patch | 有真实 API、隔离 seed 数据、CRUD 和可复现构建的演示系统 | 预先维护模板；需求超出边界时必须提示缩减或人工处理 | 手机只访问服务器预览；可控制镜像、模型和国内依赖镜像 | MVP 推荐。 |
| B. 复用 bolt.diy/Dyad 等 builder | 更自由的对话开发工作台、代码编辑和预览 | UI 重构、服务化、多租户、runtime 授权、桌面依赖、升级耦合 | WebContainers 的浏览器约束或 Dyad 的桌面定位要重新处理 | 可独立 PoC，不作为售前主链路前提。 |
| C. 自由生成 + 多 Agent 自主协作 | 任意业务栈、复杂方案与更大修改范围 | 依赖漂移、执行权限、上下文膨胀、修复次数和成本难控 | 手机前端简单，服务器生成与隔离更复杂 | 需求与质量基线稳定后再评估。 |

建议首批模板是 CRM 线索/客户管理、进销存、工单/服务管理。模板不是静态截图，而是固定数据结构、API、页面和测试入口的基础项目。

每个模板约定：

1. 可调整：中文名称、实体字段、枚举、列表筛选、详情表单、主题、有限的状态流转和 seed 示例。
2. 不可由 Agent 自由调整：基础镜像、依赖源、锁文件、权限模型、预览网关、部署脚本、平台配置和网络策略。
3. 初期不承诺：真实 ERP/CRM 对接、付款/短信/邮件、复杂审批、任意第三方 SDK 和生产数据库迁移。
4. 输出固定：需求版本、模板版本、patch、项目压缩包、构建证据、功能验证结果、演示地址、已实现/模拟/未实现清单。
5. Agent 输入使用确认后的需求快照，不直接读取销售所有历史录音和企业业务库。

平台与生成器分离：销售平台负责客户、录音、需求确认、任务和分享；coding worker 只拿指定 job 的脱敏输入及独立 workspace。

建议 MVP 先使用一个 coding worker 执行顺序阶段，不把“多 Agent”作为业务价值前提。可用平台数据库记录状态、持久任务队列触发执行；任务重复投递必须通过 job id/阶段幂等防止重复沙箱和重复计费。

OpenHands SDK 是可选 adapter；即使采用 SDK，模板约束、任务配额、patch 校验、质量检查、租户授权仍由平台掌握。

### Gaps

- 没有对这些项目进行本地 build、API 接入或手机真机验证；“可直接复用”不能视为已证实。
- 本轮没有证明 bolt.diy/Dyad 有稳定公开、适合多租户 SaaS 的 headless 生成 API；如选择整站 fork，必须单独评估维护成本。
- `gptengineer.app` 与 Lovable 的品牌演变未在本记录独立核验；不得把商业品牌改名推导成 MIT CLI 已改名或可自托管。
- “有近期 push”不证明 release 质量、漏洞响应速度或完整测试覆盖。实施前固定 commit/tag 后再审查。

## 2. Runtime、许可与移动 Web：代码在服务器执行

### Takeaway

**建议：手机仅负责录音、需求确认、查看生成进度和访问演示系统；服务器运行 React/Vite + FastAPI + 独立 SQLite Demo。** 国内私有试点可采用单独 Linux worker 主机上的加固 Docker；开放多租户任意生成代码之前，需要更强隔离的 gVisor/微 VM 或经过验证的托管 sandbox。

### Cited Findings

| Runtime | 已确认能力 | 许可/服务边界 | 本项目的判断 |
|---|---|---|---|
| WebContainers | 浏览器 tab 内 Node.js/runtime 和操作系统命令，适合 Vite/Node 工具链。[介绍](https://webcontainers.io/guides/introduction) | 商业、盈利场景的生产 API 使用要许可；原型/PoC 例外；企业版可谈自托管/VPC。[商业授权](https://webcontainers.io/enterprise) | 不承担手机核心运行，也不据此承诺原生 FastAPI 后端。 |
| E2B | 通过 JS/Python SDK 控制云端 sandbox；可执行命令、文件操作；当前 README 指向独立 runtime 自托管指南。[README](https://github.com/e2b-dev/E2B/blob/main/README.md) | E2B SDK 仓库 Apache-2.0；runtime 与部署依赖需要另核许可，云服务需账户和 API key。[LICENSE](https://github.com/e2b-dev/E2B/blob/main/LICENSE)、[自托管入口](https://github.com/e2b-dev/E2B/blob/main/README.md#self-hosting) | 托管候选；国内网络、地区、数据驻留与账单须 PoC。 |
| Daytona 托管产品 | 当前文档有 SDK/API、不同 sandbox classes、HTTP preview 与网络防火墙。[sandboxes](https://www.daytona.io/docs/en/sandboxes/)、[preview](https://www.daytona.io/docs/en/preview/) | 商业服务与旧公开 core 不是同一许可/维护边界。[旧仓声明](https://github.com/daytonaio/daytona/blob/main/README.md) | 可以做托管服务 PoC；不作为“持续维护的开源自建 core”推荐。 |
| Daytona 旧公开 core | README 明确 2026 年 6 月核心开发迁至私有 codebase，旧仓不再更新/修复/release。[README](https://github.com/daytonaio/daytona/blob/main/README.md) | README 指向 v0.190.0；其 LICENSE 为 AGPLv3；GitHub API `archived=true`。[固定版许可](https://github.com/daytonaio/daytona/blob/v0.190.0/LICENSE)、[API](https://api.github.com/repos/daytonaio/daytona) | 仅历史参考，采用旧 fork 要自行承担维护与 AGPL 义务。 |
| Docker/Linux container | namespace、cgroup、capabilities 隔离/资源控制；官方明确 default capabilities/mounts 与内核漏洞可能造成不完整隔离。[安全文档](https://docs.docker.com/engine/security/) | 服务端 Docker Engine 与 Docker Desktop 是不同产品，不能把桌面订阅规则混成 Linux Engine 运行要求。[官方产品安全文档](https://docs.docker.com/engine/security/) | 有限模板、内部试点的基础设施；不宣称是任意代码的可信安全边界。 |
| gVisor/runsc | 用户态 application kernel，OCI runtime 可接 Docker/Kubernetes，减少应用直接接触主机内核的接口。[官方介绍](https://gvisor.dev/docs/) | 仓库 Apache-2.0，当前未归档。[GitHub API](https://api.github.com/repos/google/gvisor) | 国内自托管加强隔离的候选；模板与构建工具兼容性需要实测。 |

- WebContainers 官方浏览器支持页主推 desktop Chromium；Safari 16.4 TP 起为 beta；依赖 SharedArrayBuffer 与跨域隔离，而且页面说明非 Chromium 的预览和第三方资源存在限制。[browser support](https://webcontainers.io/guides/browser-support)
- 因为文档保证的是浏览器 Node.js runtime，本轮没有找到原生 CPython/FastAPI 服务器和常规数据库进程可在 WebContainers 中等价运行的证据。[runtime 介绍](https://webcontainers.io/guides/introduction)
- gVisor 官方承认其方式带来应用兼容性下降和较高的每 syscall 开销；system-call-heavy workloads 可能有明显性能影响。[架构说明](https://gvisor.dev/docs/)
- Docker 官方要求只有可信用户能控制 daemon；挂载宿主目录和暴露 daemon API 都具有重要权限后果。[Docker daemon attack surface](https://docs.docker.com/engine/security/#docker-daemon-attack-surface)
- E2B 默认启用互联网访问；可关闭全部出网，或指定 IP/CIDR/domain allow list。域名 deny list 的能力不能等同于 domain allow list。[internet access](https://docs.e2b.dev/sandbox/internet-access)
- E2B persistence 保存文件系统和内存；当前文档称 paused sandbox 没有自动 TTL，需要显式 kill；timeout 默认行为是 kill，auto-pause 需显式配置。[persistence](https://docs.e2b.dev/sandbox/persistence)
- E2B 服务在 pause 时无法从外界访问，已有连接断开；resume 后要重连。文件系统-only 模式 resume 需要 reboot，不应假设服务进程一直在。[persistence](https://docs.e2b.dev/sandbox/persistence)
- Daytona 当前普通 preview token 是 sandbox-wide credential，可访问 toolbox/terminal 等端口，不能分发给客户；signed preview URL 限单端口、可到期/撤销。[preview 文档](https://www.daytona.io/docs/en/preview/)
- Daytona 防火墙参数能力与账户 tier 有关；部分 tier 的组织策略不能被 sandbox 设置覆盖。[network limits](https://www.daytona.io/docs/en/network-limits/)

### Inferences

手机销售平台和生成物应分别选型。下表是推荐，不是已经实现。

| 层次 | 推荐方案 | 原因与代价 |
|---|---|---|
| 销售平台移动前端 | React + TypeScript + Vite，响应式移动 Web/PWA | 四个底部入口不需要 SSR；静态前端部署简单。录音 API/前后台行为必须另做手机真机 PoC。 |
| 销售平台后端 | FastAPI + PostgreSQL + 持久任务队列 + 对象存储 | 录音/需求/租户资料存平台数据库；音频、source bundle 和检查结果存对象存储；耗时任务独立执行。 |
| 可选平台栈 | Vue + FastAPI；或 React/Next + NestJS | 若团队 Vue/Node 经验明显更强，可替换平台栈；Next SSR、BFF 和双语言维护不能无理由增加。 |
| 生成物前端 | 固定 React + TypeScript + Vite + 已审核 UI 组件 | 模板和构建路径统一；手机看列表、卡片和表单，复杂表格提供横滑/简化视图。 |
| 生成物后端 | 固定 FastAPI + SQLite | 真实 HTTP CRUD，独立数据库文件便于 seed/reset/export；不适合直接承诺多实例生产写入。 |
| 预览入口 | 一个反向代理把前端 `/` 与后端 `/api` 提供到同一演示 origin | 避免手机前端处理沙箱端口、内部地址或跨域 API key；网关仅暴露业务服务。 |

平台数据库和 Demo 数据库必须分离。Demo 的 SQLite 只含合成客户/商品/工单数据，不复制平台的客户原始对话库。

生成物的真后端边界：创建、查询、编辑、删除、列表筛选和简单状态转换必须经过 FastAPI，并在 SQLite 中体现实际写入及重新读取。

模拟边界：短信、付款、外部 ERP、签章、AI 诊断等初期提供明确标注的模拟结果。不能把 LocalStorage 数据变化或截图作为“有后端”的证据。

国内可访问性分成四条独立链路：模型 API、sandbox 控制 API、preview 域名、npm/PyPI/镜像拉取。某条在公司办公网可用，不证明手机 4G/5G 可用。

建议预先构建、固定 digest 的基础镜像和本地依赖缓存，生成时不让 Agent 任意从互联网拉取包；托管 sandbox 只拿需要的脱敏输入。

“微 VM”与 gVisor 是不同隔离机制，不能把 gVisor 描述成 VM，也不能因产品声称 secure 就忽略实际选择的 sandbox class 与网络权限。

### Gaps

- 未验证 iPhone Safari、安卓 Chrome、微信内置浏览器在国内 4G/5G 下的 preview 连通性、cookie、iframe 和 WebSocket 行为。
- 未实测 E2B/Daytona 的大陆访问、控制 API 延迟、preview 首开时延、数据驻留、暂停成本和套餐限制。方案中不能填写虚构 SLA、单 Demo 价格或成功率。
- E2B runtime 仓库、当前 Daytona clients SDK 仓库和其传递依赖许可需在真正接入的固定版本上继续核查；旧 core 的许可不能外推到新托管服务或 SDK。
- 未做 gVisor 下 Python wheels、SQLite 文件操作、浏览器 smoke 工具、Node 构建兼容性验证。
- SQLite 在 Demo 里方便隔离与快照，但需要验证备份一致性、reset、多标签并发写入和休眠恢复；生产交付升级到 PostgreSQL 是新的工程阶段。

## 3. 预览、供应链、生命周期与质量门槛

### Takeaway

**建议：生成 job 只有在 build、真实 API CRUD 和浏览器 smoke 都通过后才能进入“可演示”。** 预览使用独立域名和可撤销分享授权，运行环境、数据库与源码快照有明确生命周期；演示过期不能自动等同于销毁源码。

### Cited Findings

- Docker cgroups 防止资源被某个容器耗尽；namespace/capabilities 需要正确配置且不构成绝对隔离。[Docker security](https://docs.docker.com/engine/security/)
- gVisor 的安全机制降低内核攻击面，但引入兼容和 syscall 开销，因此隔离方案必须与实际模板验证一起选择。[gVisor](https://gvisor.dev/docs/)
- WebContainers 商业授权覆盖为客户、潜在客户及员工提供的商业生产用途，不限于公开售卖 IDE。[商业使用](https://webcontainers.io/enterprise)
- E2B 支持 pause/resume，但 paused 不可访问、kill 不可恢复、默认 timeout 并非自动持久化，平台必须维护自己的生命周期逻辑。[persistence](https://docs.e2b.dev/sandbox/persistence)
- Daytona signed preview URL 与普通 preview token 权限不同；共享给客户应使用有期限、可撤销的单端口授权。[preview](https://www.daytona.io/docs/en/preview/)

### Inferences

以下条目全部是本项目建议，尚未执行或通过安全验证。

#### 生成流水线

1. 销售确认需求版本：记录业务实体、角色、核心流程、必需页面、优先级、排除范围与接受条件。
2. 选择模板并复制固定版本到独立 workspace；记录模型版本、模板版本、镜像 digest、依赖锁版本和 job id。
3. 编码前先生成可校验的实现计划：哪些字段/API/页面要修改，哪些外部功能只模拟。
4. Agent 只能写入允许的源码路径；平台校验 patch 大小、文件类型、越界路径和是否改动禁改文件。
5. 构建层检查：依赖锁一致性、类型检查、前端 production build、后端 import/startup、路由/schema 完整性。
6. 业务 API 检查：seed → list → create → get → update → delete → confirm deleted；非法输入和不存在 id 有合理错误。
7. 持久化检查：同一数据再次读取一致；重启后仍可读取；reset 恢复 seed；每个 demo 数据隔离。
8. 浏览器 smoke：手机 viewport 打开列表，创建/编辑一项，再刷新验证；检查关键 console/network 错误。
9. 汇总失败给 Agent，在同一个隔离任务中进行有界修复；建议最多两轮、总 token/时间上限，数值须由后续实验调整。
10. 到达上限停止并保留错误、patch、最后成功版本；销售能看懂“哪些步骤失败”和建议缩小的范围。
11. 全部质量门槛通过后发布预览；保存校验摘要、源码 bundle 和匹配的数据库快照。

不允许自动“修复”校验规则、跳过失败测试、关闭授权、替换依赖镜像源或删除验收步骤。任务取消需要停止模型调用和沙箱执行；平台仍保存已经收集的阶段证据。

#### 依赖与网络白名单

- 前后端固定锁文件，构建使用锁定版本；新增依赖提交到人工审核队列，Agent 不自行升级基础栈。
- 基础镜像按 digest 锁定；禁止在生成任务中修改 Dockerfile、服务编排、反向代理或平台环境文件。
- 只安装审核名单中的包；禁用不必要的安装脚本，若模板确需脚本，固定具体包/版本及执行权限。
- 构建阶段只允许内部镜像/制品源；预览阶段默认不出网；外部模拟功能不需要真实 API key。
- 阻断宿主内网、云 metadata、loopback 越权、其他 tenant sandbox；DNS 和 IPv6 也需要对应规则。
- Agent 使用受限文件编辑/命令工具；命令执行始终在沙箱内，不向 Agent 暴露 Docker socket、宿主路径、云 API 凭证或平台数据库口令。
- 检查输入与输出里的 secret、真实客户姓名/电话/邮件、原始合同等；原始销售对话不写入源码、seed、日志或公开截图。
- 客户原话视为数据：其中“安装这个包”“上传客户库”等内容不能提升成 Agent 系统指令或网络授权。

#### 预览与分享

- 平台域名与生成物使用不同可注册主域，减少域 cookie 与生成物脚本之间的信任关联。
- 每个 demo/revision 单独路由，网关映射到固定业务端口；禁止用户通过 URL 指定任意端口、宿主 IP 或目标路径。
- 推荐“查看 Demo”打开独立浏览器页；平台内 iframe 是辅助预览，必须按手机浏览器表现做降级。
- iframe 限制能力，配置 CSP/frame-ancestors；明确授权 postMessage 的 origin 和消息 schema。沙箱属性组合须真机检验。
- 平台 session cookie 不向 demo 域名共享；演示权限与平台用户权限分开，由预览网关执行访问控制。
- 分享链接使用随机、有限期、可撤销授权，绑定 demo/revision 和查看范围；短期 token 换取仅预览域 cookie，避免把长期管理 token 放在 URL。
- 客户分享默认私密，Demo 广场只展示销售明确选择发布的合成示例；禁止原始客户会话或真实业务数据自动进入广场。
- 外部分享显示“业务演示/样例数据/模拟功能”的范围；真实购买、发信、第三方业务提交初期关闭。

#### 隔离与资源约束

- 生成 worker 与销售平台分主机/网络，按 tenant + job 创建隔离 workspace，运行时不访问平台业务库。
- 非 root、只读根文件系统、独立可写目录、drop capabilities、no-new-privileges、seccomp/AppArmor；禁止 privileged、host network 和宿主目录任意挂载。
- 明确 CPU、内存、PID、磁盘、输出大小、执行时长、总 token、每用户并发和租户预算；具体数值从 PoC 数据决定。
- 构建容器、运行容器和预览网关职责分开；用户访问 Demo 不应能直接调用 agent-server、terminal 或文件管理 API。
- 任意源码上传、未知模板与广场 fork 会扩大风险面；未具备强隔离之前只开放受控模板修改。

#### 生命周期

| 状态/对象 | 建议策略 | 恢复/删除语义 |
|---|---|---|
| 生成 workspace | job 结束后清理执行环境，持久化脱敏输出和检查结果 | 重试从确认需求 + 固定模板 + 已保存 patch 重建。 |
| 已就绪 Demo runtime | 无访问达到阈值后停止/休眠；展示唤醒中状态 | 重新启动后跑健康检查，确认后开放入口。 |
| Demo 数据 | 独立 SQLite；快照须保证一致性 | 定义恢复保留修改还是 reset seed，默认展示数据可重置。 |
| 分享链接 | 有效期和撤销独立于 runtime 生命周期 | runtime 唤醒不得延长已过期授权；撤销立即生效。 |
| 源码/构建产物 | 对象存储按 revision 持久化，明确保留期 | runtime 删除不等于源码丢失；支持脱敏导出。 |
| 到期 Demo | 先关闭分享/休眠，按保留策略再删除运行资源 | 对客户和销售明确说明还能恢复什么。 |
| 厂商 snapshot | 只作运行加速，不作为唯一备份 | 厂商状态、套餐或账号变化不能让唯一源码与 DB 消失。 |

停止 Docker 容器不会保存运行进程内存；重新创建空容器也不会自动恢复 SQLite。应将 DB snapshot、source bundle、模板/依赖版本及运行 manifest 作为独立可恢复资产管理。

导出只包含生成物代码、锁文件、数据库结构/合成 seed、启动说明、测试摘要和许可清单，不包含客户原音频、销售平台 token、模型 API key 或 sandbox 管理凭证。

#### PoC 验收清单

- 选择三类真实售前需求的脱敏版本，各验证从确认需求到 CRUD 可演示的完整链路。
- 记录首次构建通过率、修复后通过率、无法实现的需求种类、token/执行/存储成本；报告样本数与范围，不先承诺成功率。
- 对比普通 Docker 与 gVisor/托管 sandbox 的模板兼容、隔离能力、冷启动和国内网络表现。
- iPhone Safari、安卓 Chrome、微信内置浏览器，分别在办公 Wi-Fi 与手机网络检查独立页/iframe/唤醒/私密分享。
- 验证 create/update 后服务重启、休眠唤醒、DB reset、revision 回退、bundle 导出与重建。
- 验证错误需求/安装未知依赖/读取宿主环境/内网请求不会绕过校验和网络控制。
- 验证其他销售、其他 tenant、过期链接和撤销链接无法访问私密 Demo。
- 验证任务中断、重复投递、模型 API 失败和 sandbox 容量不足都可恢复且不重复发布。

### Gaps

- 上述工程边界和验收规则尚未实现；本轮结论是方案级建议，不能声称系统已经安全隔离或自动生成成功。
- 尚未根据实际业务样本定出资源配额、保留期、生成时长目标和模板覆盖率；建议先用小样本 PoC 校准。
- 源码许可、SDK 许可、托管服务条款、模型条款、生成物依赖许可分别需要在选定版本上记录，不用一个“开源”标签覆盖全部。

### 主要来源与本地材料索引

| 来源 | 在线入口 | 本地材料（`.firecrawl/`） |
|---|---|---|
| bolt.diy README/LICENSE | [官方仓库](https://github.com/stackblitz-labs/bolt.diy) | `demo-bolt-readme.md`、`demo-bolt-license.md`、`demo-meta-bolt.json` |
| OpenHands Canvas | [官方仓库](https://github.com/OpenHands/OpenHands) | `demo-openhands-readme.md`、`demo-openhands-license.md`、`demo-meta-openhands.json` |
| OpenHands SDK | [官方仓库](https://github.com/OpenHands/software-agent-sdk) | `demo-openhands-sdk.txt`、`demo-openhands-sdk-license.txt`、`demo-meta-openhands-sdk.json` |
| gpt-engineer | [当前归档仓库](https://github.com/AntonOsika/gpt-engineer) | `demo-gpt-engineer-readme.md`、`demo-gpt-engineer-license.md`、`demo-meta-gpt-engineer.json` |
| Dyad | [官方仓库](https://github.com/dyad-sh/dyad) | `demo-dyad-readme.md`、`demo-dyad-license.md`、`demo-dyad-pro-license.txt`、`demo-meta-dyad.json` |
| E2B | [SDK 仓库](https://github.com/e2b-dev/E2B)、[persistence](https://docs.e2b.dev/sandbox/persistence)、[network](https://docs.e2b.dev/sandbox/internet-access) | `demo-e2b-readme.md`、`demo-e2b-license.md`、`demo-e2b-persistence.html/.txt`、`demo-e2b-network.html/.txt` |
| Daytona | [旧 core](https://github.com/daytonaio/daytona)、[当前 preview](https://www.daytona.io/docs/en/preview/)、[当前网络](https://www.daytona.io/docs/en/network-limits/) | `demo-daytona-readme.md`、`demo-daytona-license-v0190.txt`、`demo-meta-daytona.json`、`demo-daytona-preview.html/.txt`、`demo-daytona-network-limits.html/.txt` |
| WebContainers | [浏览器支持](https://webcontainers.io/guides/browser-support)、[介绍](https://webcontainers.io/guides/introduction)、[商业授权](https://webcontainers.io/enterprise) | `demo-webcontainers-browser.md`、`demo-webcontainers-introduction.html/.txt`、`demo-webcontainers-enterprise.html/.txt` |
| Docker/gVisor | [Docker 安全](https://docs.docker.com/engine/security/)、[gVisor](https://gvisor.dev/docs/) | `demo-docker-security.html/.txt`、`demo-gvisor-overview.html/.txt`、`demo-meta-gvisor.json` |

未作为证据的 404 材料：旧 WebContainers commercial-usage 路径、E2B auto-pause 路径、Daytona sandbox-lifecycle/network-access 路径以及 Daytona 当前 main/LICENSE 路径。使用表中的成功入口与固定版 LICENSE。
