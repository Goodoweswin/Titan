# 阿里云邮件推送接入与自助账户切换

本指南接续现有管理员账户部署。注册、邮箱验证、重发验证邮件、找回与重置密码的实现已在服务中；生产环境需先完成真实事务邮件接入，再从 `managed` 切换到 `self_service`。登录 issuer 继续使用已安装 App 的 `https://121.40.43.188`，发信域名与登录入口分开配置。

账户数据库、一次性验证链接的生成和校验、密码重置及会话撤销均在用户自己的 ECS 上处理。DirectMail 负责把事务邮件投递到用户邮箱；`noreply` 是发件地址前缀，无需另建收信邮箱。阿里云默认限制 ECS 的 TCP 25 出站，其解封条款也只允许经第三方 SMTP 服务器外发，因此本方案不在共用业务 ECS 上另部署直接向收件 MX 投递的邮件服务器。自建投递也无法替代发信域名的 DNS 授权。

## 邮件服务准备

使用阿里云 DirectMail 华东 1（杭州）、独立发信子域名 `notify.pilotus.studio`，计划发件地址为 `noreply@notify.pilotus.studio`，发信类型选择“触发邮件”。域名的 DKIM、SPF、DMARC、MX 记录必须以该账号控制台实际生成的值为准；新域名需四项全部验证通过。现有根域邮箱、`sop.pilotus.studio` 网站及其他业务记录保留。

2026-11-13 的现场域名已创建并切换为 2048 位 DKIM，仍待 DNS 验证。准确的四条记录已另交 DNS 负责人；重新创建域名或再次更换 DKIM 后，必须重新读取控制台值，旧交接清单不再作为依据。同一名称的 SPF 应保持为一条，由 DNS 负责人合并已有发送源。

域名验证通过后才创建关联发信地址。SMTP 密码由用户在阿里云页面设置，并在受控终端的隐藏输入提示中写入服务器私有配置。密码、授权码、邮件链接与私钥不进入聊天、源码、命令参数或日志。阿里云控制台提示新发信地址及 SMTP 密码可能需要等待生效；随后以实际认证及投递结果为准。

## SMTP 连接合同

现有 Django 适配器固定 `EMAIL_USE_TLS=True`，使用必需的 STARTTLS 和默认 CA/主机名验证。因此杭州接入配置为：

```dotenv
ACCOUNTS_ACCOUNT_MODE=self_service
ACCOUNTS_MAIL_DELIVERY=smtp
ACCOUNTS_FROM_EMAIL=noreply@notify.pilotus.studio
ACCOUNTS_SMTP_HOST=smtpdm.aliyun.com
ACCOUNTS_SMTP_PORT=80
ACCOUNTS_SMTP_USER=noreply@notify.pilotus.studio
```

以上仅是非秘密参数，不能单独作为完整生产 env。`ACCOUNTS_SMTP_PASSWORD` 必须私下注入；原 Django secret、RSA key、数据库凭据、issuer、允许 host 和精确网关地址保持原配置。端口 80 在此承载 SMTP，通过 STARTTLS 升级加密；适配器会在升级失败时终止连接，不进行明文认证。465 是隐式 TLS，不能只把当前端口改成 465 来使用。不要使用 ECS 默认封禁的 25 端口。

截至本次准备工作，本机对官方端点的 STARTTLS 握手通过，协商 TLS 1.2；没有认证或发信。该证据不替代 ECS 网络连通性、SMTP 密码认证、邮件到达和用户点击链接的验收。

## 生产切换顺序

1. 重新核对 ECS 当前运行版本、私有 Compose 覆盖、网关与新旧服务健康。保存仅包含非秘密字段的时间点记录；备份私有配置时保留 0600 和独立目录。不要打印完整 env、Docker inspect 或展开的 Compose 配置。
2. DNS 四项验证通过并创建触发类发信地址后，由用户完成 SMTP 密码设置及隐藏输入。先准备单独的 0600 自助模式 env，暂不替换正在使用的 managed env。保留签名密钥与数据库，只为模式转换生成新的外部 `ACCOUNTS_SESSION_EPOCH`。
3. 用账户镜像和暂存 env 进行一次性生产配置检查、运行数据库角色检查、ECS 上的受信任 STARTTLS 握手及 SMTP 认证。需要发信时，只向用户指定的验收邮箱发送本任务的事务邮件。输出仅保留稳定错误类型、状态和数量；不输出认证值、收件人、正文或链接。`check_accounts_deployment` 明确只检查配置与权限，本身不证明 SMTP 可用。
4. 核对 base Compose 加现场本地镜像覆盖的实际合并结果：账户 API 和 worker 使用同一暂存 env；不再叠加 `compose.managed.yaml`，否则它会强制覆盖回 managed/disabled。API 服务继续使用唯一名称 `accounts-api`；网关上游与网关网络不变。镜像仍按现场本地内容 ID 固定并保留 `pull_policy: never`，不能把它误写为 registry manifest digest。
5. 先测量资源和失败重试场景：API 144 MiB、数据库 160 MiB、新增 worker 80 MiB，共 384 MiB；不减少密码哈希强度或借用旧业务预算。邮件 worker 只连接专属 mail/database 网络，不连接网关；数据库和 API 不新增公网端口。
6. 说明此次模式转换会使现有登录失效后，原子切换私有 env，并仅冷重建 Titan 的 API、启动 worker。数据库卷、用户及密码保留；无需重启现有 Caddy 或旧业务。worker 必须通过生产检查且变为 healthy。
7. 先为原有管理员开通的账户完成真实邮箱验证。`admin_provisioned` 不代替 `verified_at`，禁止批量标为已验证。现有用户可通过“重新发送验证邮件”完成验证，随后重新登录。
8. 验收新用户注册、真实验证投递、链接 GET 不消费/POST 确认、重复及过期链接、找回投递、用户私下重置密码、旧密码及旧会话失效、原生重新登录和重启保持。真实用户的注册及新密码输入由用户完成；本地测试使用合成账号。检查成功或过期邮件正文被擦除，投递故障有有界重试，新旧服务持续健康。

## 回退与范围

切换失败时保留数据库和新增账号，停止新 worker，以保存的 managed 配置配合另一个全新 epoch 冷重建 Titan API；再核验旧站和原先批准的管理员账户。不要使用全栈 `down`、删除卷、恢复旧数据库或复用已失效 epoch。回到 managed 后，新注册但未被管理员批准的账号不自动获得 managed 资格；不通过批量批准掩盖这个模式差异。

本任务不把注册接通等同于科研数据云同步、Pilotus 账号合并或 Windows 原生验收。当前线上状态与真实验收进展以本轮 checkpoint 为准。

## 官方依据

- [发信域名与新域名四项验证](https://help.aliyun.com/zh/direct-mail/user-guide/how-to-configure-sending-domain-names)
- [发信地址、触发邮件及 SMTP 密码](https://help.aliyun.com/zh/direct-mail/user-guide/setup-sender-addresses)
- [官方 SMTP 端点、80/25 STARTTLS 与 465 隐式 TLS](https://help.aliyun.com/zh/direct-mail/smtp-endpoints)
- [按量计费与免费额度](https://help.aliyun.com/zh/direct-mail/billing-methods/)
- [ECS TCP 25 默认限制及解封用途](https://help.aliyun.com/zh/document_detail/56130.html)
