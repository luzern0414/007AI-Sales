# 项目交付平台开发执行计划

目标已在 Codex 中设为 active，持续推进至真实链路完成；不以文档或页面完成替代交付。本计划执行在当前目录，无 Git 仓库，不创建工作树。

架构：React/TypeScript/Vite + FastAPI + SQLAlchemy/Alembic，开发使用本机真实 SQLite，生产 PostgreSQL 单独验证。业务事件、版本与权限由数据库决定。确定性业务不依赖大模型。

全局约束：手机优先；四入口“首页、项目管理、产品库、工作台”；不小于14px；简洁用户文案；真实后端读写；不伪造集成或进度；默认不分期；遵守开发和方案规范；保留独立录音存储路径与所有证据来源。

## 实施批次

下表定义按顺序交付的独立链路，各批先写失败测试，再实现、运行验证、检查异常并更新开发记录。

| 顺序 | 目录/文件 | 产物与测试 |
|---|---|---|
| 1 | server/auth.py、db.py、projects.py、tests/test_projects.py；web/src/pages/Projects.tsx | 会话、初始化、项目、任务、时间线及风险真实持久化；鉴权、越权、乐观锁、日期排序、逾期和0任务口径 |
| 2 | server/files.py、products.py；web/src/pages/Products.tsx | 文件原件、版本与下载、产品内部管理和面客发布；类型/大小/权限、越权下载及白名单字段 |
| 3 | web/src/pages/Home.tsx、Workspace.tsx；web/src/components | 手机四页、项目详情、工作台、表单/加载/失败；浏览器真实操作、刷新/重登、断网、320px无溢出 |
| 4 | web/src/recording、server/recordings.py、tests/test_recordings.py | PCM录音块、IndexedDB日志事务、归档/manifest、水位/补传/恢复、缺口；独立转写适配与实机记录 |
| 5 | server/documents、integrations；tests/test_documents.py | 纪要PDF/MD、基于来源的方案/需求/甲方清单、AI配置与失败、增量进展/来源同步、明确确认 |
| 6 | config、scripts、tests、README | 迁移、安装/启动、备份恢复、数据库/安全/页面回归、字体/PDF检查、实际部署边界 |

## 当前待办

- [x] 身份、初始化并发、项目/任务/依赖/问题/节点的本机数据链路与负向测试。
- [x] 文件/产品上传、下载、发布与撤下；接口权限与隔离页面验证。
- [x] 四入口、工作台真实进度与手机320/390px浏览器操作。
- [x] 合成麦克风录音、断网补传、恢复、跨页、中断记录及停止尾音回归。
- [x] 纪要MD/PDF下载与中文视觉检查。
- [x] 方案/清单生成契约、幂等请求、来源快照、Word/Excel讨论稿与不可覆盖修订的接口测试。
- [x] 本地FunASR与DashScope可选接口；FunASR隔离WebSocket传输测试，不自动转收费服务。
- [x] 本机迁移、SQLite原件备份校验与新目录恢复、配置及验证文档。
- [x] 来源同步及修订导出的浏览器操作；同来源数据库占用、超时与提交所属校验的并发测试。
- [x] 录音退出尾音冲刷及退出失败留存；HTTP响应正文超时；工作台文档进度及跳转。
- [ ] 录音启动取消/IndexedDB生命周期、本机缓存保留策略、转写初始缓存/重连与补识别。
- [ ] 实际FunASR模型、方案模型效果与完整格式规范、人工审核发布。
- [ ] 手机HTTPS真机、PostgreSQL、生产部署/监控/恢复验收。

测试命令：`.venv\Scripts\python.exe -m pytest tests -q`；`npm.cmd --prefix web run build`；浏览器通过 Playwright CLI 连接实际本机服务逐项操作。隔离数据库使用 pytest 临时目录，绝不向开发数据库注入演示项目。UI验证产生的记录仅存隔离测试实例。每批详细失败与通过记录写入[开发记录](development-log.md)。
