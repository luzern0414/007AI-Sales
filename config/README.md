# 运行配置

当前程序从根目录 `.env` 及进程环境变量读取配置，环境变量优先。模板为[.env.example](../.env.example)。不在源码、浏览器或日志中保存真实密钥。

| 配置项 | 当前作用 |
|---|---|
| DATABASE_URL | 默认 `sqlite:///data/platform.db`。本机真实SQLite持久化；PostgreSQL连接使用 `postgresql+psycopg://`，尚未运行验证 |
| STORAGE_DIR | 默认 `data/files`，私有附件、录音块及可重建缓存；禁止配置为公开静态目录 |
| ALLOWED_HOSTS | 允许访问的主机名，逗号分隔；默认127.0.0.1、localhost |
| ALLOWED_ORIGINS | HTTP写请求与转写WebSocket的允许来源，包含协议和端口 |
| COOKIE_SECURE | 本机HTTP为0，HTTPS部署必须为1 |
| SETUP_TOKEN | 远程初始化凭证；首次创建管理员后初始化入口关闭；至少12字符密码 |
| LLM_BASE_URL / LLM_API_KEY / LLM_MODEL | OpenAI兼容Chat Completions企业服务；三项齐全才允许生成，服务商端点及模型需按账户核验 |
| REALTIME_ASR_PROVIDER | `funasr` 或 `dashscope`；模板选本地funasr。旧配置未填写时兼容dashscope，不自动回退或切换供应商 |
| FUNASR_WS_URL | 运维指定的本地/私有FunASR服务，例如 `ws://127.0.0.1:10096`；不需要云API密钥。模型服务需单独部署，见[本地转写](funasr.md) |
| DASHSCOPE_API_KEY / DASHSCOPE_WS_URL / DASHSCOPE_ASR_MODEL | 仅选择dashscope时使用；三项齐全才连接。未配置时录音保存继续，文字转写明确不可用 |
| FUNASR_BATCH_PYTHON / FUNASR_BATCH_DEVICE | 完整录音补转写使用独立Python环境与设备；本机默认CPU，实时GPU占用4GB显存时不再并行装载GPU模型 |
| PROJECTS_ROOT | 自动发现数字+名称目录的根路径，本机D:/Codes，仅读取各项目docs业务资料 |
| DOCUMENT_SOURCES_JSON | 运维允许同步的本机目录映射，例如 `{"delivery":"D:/ApprovedDocs"}`；默认 `{}`，不允许用户任意浏览服务器目录 |
| PROPOSAL_FORMAT_PATH | 方案格式规范文件，模板指向 `D:/Codes/方案格式规范.txt`；缺失则停止生成 |
| PDF_BROWSER_CHANNEL | 默认chrome；需安装对应Playwright支持的浏览器与授权可用中文字体 |
| NODE_EXECUTABLE | PDF子进程Node路径，默认node；Node需22.12+ |

dev使用默认数据目录；隔离UI测试另设 `output/ui-test.db` 和 `output/ui-files`，地址8766。生产环境尚未部署，无已验证生产URL、数据库或对外账号。不得将隔离测试账户、合成录音或模板客户资料作为正式业务数据。

## 启停与迁移

根目录执行 `scripts/start.ps1`，地址 `http://127.0.0.1:8765`，只绑定当前电脑。Ctrl+C停止；重新执行为重启。修改后端或环境变量后需重启，修改前端后需 `npm.cmd --prefix web run build`。

启动自动执行Alembic到head。可手动运行 `.venv/Scripts/python.exe -m alembic upgrade head`、`alembic current`、`alembic check`。迁移前备份；升级失败时不要删除数据库。`baseline-local-database.py`仅用于已有无版本库的一次性迁移，不用于新部署或重复初始化。

手机访问需在目标服务器配置可信HTTPS、对应HOST/ORIGIN、Secure Cookie、反向代理WebSocket升级及请求大小/超时，并实际验证iOS/Android；当前未提供已验证的公网部署。

## 集成检查

登录后 `/api/integrations/status` 返回配置是否齐全。本机FunASR GPU10097已通过平台WebSocket、原文入库和停止确认测试，CPU10096备用；云ASR未实际验收。AI项目分析使用完整分片、持久检查点和限次退避，手动分析与会议优先执行；方案生成单独使用90秒请求超时、24000输出token上限及容量检查。同会议仅一个方案生成请求运行，幂等结果持久化；中断需人工重试。

文档连接支持MD/TXT/PDF/DOCX/XLSX/PPTX/HTML/drawio、图片及音频；音频归入会议，文件页只显示文档。每次最多1000份、总计1GB、扫描最多10000项，单文件仍受上传限制。后台每60秒同步，编号项目每300秒发现一次。同来源有占用标记、超时恢复与最终校验，符号链接及越界拒绝。缺失来源保留归档并提示，机器生成文档和未填写模板不回灌AI。详见[项目流程配置](project-workflow.md)。

浏览器普通请求最多30秒；生成/上传/下载最多120秒；来源同步最多150秒以容纳服务端超时清理。超时不会自动重试写操作，需要检查结果。退出前停止录音并保存尾音；离线内容仍需原浏览器恢复，退出失败不卸载录音状态。

## 备份恢复

见[README](../README.md)与 `scripts/storage-maintenance.py --help`。工具读取实际DATABASE_URL/STORAGE_DIR；SQLite在线快照后校验其引用的原件。只有成功写出manifest且verify通过才是有效备份；失败目录保留供排查，不覆盖重用。恢复到全新路径，先停止服务，再调整配置，验证后启动；不覆盖当前业务库。

备份包含敏感客户数据，应存放在受控目录并独立加密/访问管理。浏览器未补传数据需在原设备恢复；不要在恢复前清空浏览器站点数据。当前没有自动保留/删除策略或PostgreSQL备份工具。

## 日志与故障

运行终端可见请求状态及服务异常日志；页面仅显示简短中文错误，不包含密钥/堆栈。检查失败时依次确认端口、配置、数据库迁移、存储权限及供应商账户。PDF失败可保留MD；扫描PDF标待识别，不虚构文字。401需重登，409需刷新或处理业务前提。

当前只有管理员创建用户API，没有账号维护/重置密码页面或重置工具；团队共享、集中日志、告警及生产运维验收待完成。历史配置研究保存在[settings-catalog.md](settings-catalog.md)，其中未实现参数不被当前程序读取。
