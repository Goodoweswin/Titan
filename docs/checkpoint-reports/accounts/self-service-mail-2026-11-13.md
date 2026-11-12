# 自助注册、邮箱验证与找回密码：邮件接入进度

日期：2026-11-13（北京时间）。基线：`5ce46de`。本轮未修改账户业务代码、ECS 运行配置、数据库或已安装 App。

## 当前结果

用户已要求继续接通邮件验证、注册和找回密码。既有自助账户实现及审批范围继续适用；线上仍保留上一轮验收通过的 managed/disabled 模式，避免在真实投递尚未接通时开放依赖邮件的流程。

- 用户亲自在阿里云页面接受服务协议并开通 DirectMail；实际观察到开通成功及杭州控制台的正常状态。
- 用户选择 `noreply@notify.pilotus.studio`，最初说明 DNS 由其他负责人配置；随后说明持有阿里云登录密码，尚需确认是否可进入持有域名解析的账号。
- 在当前邮件服务账号中创建发信域名 `notify.pilotus.studio`。用户亲自确认切换为 2048 位 DKIM，之后重新读取实际 selector 与公钥。解析 DER 公钥确认是 2048 位。
- 控制台四项要求为 DKIM TXT、SPF TXT、DMARC TXT、MX；四项均待验证。发信地址表单的关联域名下拉框尚不可用，因此尚未创建发信地址或 SMTP 密码。
- 当前登录阿里云账号的云解析域名列表显示 0 条，没有 `pilotus.studio`。这只是该登录账号的可见结果，不代表域名不存在或不能由另一个账号管理。没有添加 DNS 域名、转移域名、授权自动解析或修改 DNS 记录。
- 用户随后选择亲自登录管理域名的阿里云账号；尚未收到“已登录并找到域名”的完成反馈。关于改由自己的 ECS 处理 noreply 验证的追问，已核实并解释：账户验证逻辑本就在 ECS，投递由 SMTP 服务承担；阿里云 TCP 25 出站默认受限，解封条款仅允许第三方中继。未另安装邮件服务器或更改出站限制。
- 另一次公网 MX 查询显示 `pilotus.studio` 根域由 `mx1/2/3.qiye.aliyun.com` 接收邮件。这只能证明根域的邮件路由，不证明 `noreply@pilotus.studio` 邮箱已存在或用户持有其 SMTP 凭据；阿里云控制台登录密码不能据此当作邮箱密码使用。本轮仍按用户此前选择的独立 DirectMail 子域名准备。
- 精确 DNS 值已从控制台读取并写入桌面交接文件 `/Users/janus/Desktop/Titan-邮件服务-DNS配置清单.txt`，含四条记录、相对/完整名称和复制说明，仅含待公开 DNS 值。DKIM TXT 内容 SHA-256：`60057022c474e7668e0e7dd36caaf84da232b4b995cee5b4d3a0de15da565069`。TTL 600 和单一 MX 优先级 10 明确标为操作者建议值，未冒充控制台给定参数。

## 本轮验证

| 检查 | 结果与边界 |
| --- | --- |
| 账户服务完整测试 | 在 `services/accounts` 使用独立 `/tmp/titan-accounts-venv/bin/pytest -q`，`PGHOST=127.0.0.1 PGPORT=55432 PGUSER=janus PGDATABASE=titan_accounts`：**191 passed in 43.42s**。使用专属本地测试集群及 pytest 的可丢弃测试库，不迁移基库或接触生产库。 |
| 测试服务清理 | 为此次检查启动的已知 `/tmp/titan-accounts-pg` 集群在测试后正常停止；没有留下该测试 PostgreSQL 服务。 |
| 官方 SMTP 端点 | 本机 `smtpdm.aliyun.com:80` 提供 STARTTLS；使用 `ssl.create_default_context()` 成功协商 TLS 1.2。未认证、未发送邮件。当前 Django 适配器的强制 STARTTLS 可使用此端口；465 隐式 TLS 需要不同配置。此结果不代表 ECS 出站或真实邮件投递已验收。 |
| DNS 公网查询 | 2026-11-13 03:25:09 北京时间，经 Google DNS HTTPS resolver 查询四个目标记录，均为 NXDOMAIN、预期值不存在；未使用本机可能受代理影响的 A 记录作为权威依据。 |
| 生产公开状态 | 同时从 Mac 使用正常 CA 验证检查：IP `/login` 200、`/register` 403、`/recover` 403，符合尚未切换的管理员模式。 |
| 旧业务保护 | 原站 `/app/`、`/account`、`/healthz` 均 200，前两页 SHA-256 与上一轮切换前基线一致。 |

新增[阿里云 SMTP 与生产模式切换指南](../../../deploy/accounts/ALIBABA_DIRECTMAIL.md)，明确受控秘密输入、移除 managed 覆盖、新 epoch、既有用户真实邮箱验证、worker 资源与投递验收，以及不回退数据库的故障处理。本轮代码未改变，因此没有重复运行无关的原生或科学引擎测试。

## 下一步依赖

1. 进入能管理 `pilotus.studio` 的域名解析账号，或由 DNS 负责人按桌面清单添加四项记录；公网与阿里云控制台验证通过。
2. 创建触发类发信地址，由用户在阿里云页面设置 SMTP 密码，再通过服务器隐藏输入写入私有配置。密码或授权码不进入聊天。
3. 在 ECS 上完成实际 SMTP/TLS/认证和指定邮箱投递验收，测试 worker 资源与邮件故障重试；保留新旧服务健康证据。
4. 使用新 epoch 切换 `self_service/smtp` 并启动受限 worker，完成用户真实邮箱验证、注册、找回/重置及原生重新登录。不能把管理员批准直接写成邮箱已验证。

这些生产步骤尚未执行，尚不宣称邮件验证、注册及找回密码已经公网接通。登录仍使用现有 ECS IP HTTPS；科研数据同步和 Pilotus 账户合并不在本轮接通范围。
