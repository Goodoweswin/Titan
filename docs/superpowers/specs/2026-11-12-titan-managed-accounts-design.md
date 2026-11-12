# Titan 管理员开通账号与 ECS 接入准备

用户于 2026-11-12 要求开始 ECS 登录开发，并明确：新域名、邮件服务、新电脑 SSH/Workbench 均未配置；先完成管理员创建账号、账号密码登录、会话和退出，邮件验证与邮件找回暂未接通。既有科研 taobao 的域名、数据库和网关用途保留。

## 目标与当前事实

在已完成的 Titan 账户服务上新增明确的管理员开通模式，并贯通原生客户端；本地以真实 PostgreSQL/OAuth 协议验证，为之后 ECS 部署提供准确配置和操作说明。已有自助邮件注册模式保持默认及原有验证规则。

本次只读核验：旧站 `/app/`、`/account`、`/healthz` 有效 HTTPS 均200；通过交接中的 ED25519 主机公钥严格固定身份后，现有本机密钥登录 taobao-ops 被拒绝。未发现已登录的阿里云浏览器标签，也没有可用 Workbench/阿里云 CLI profile。服务器内部当前资源与权限未核验，未更改 ECS。公网入口和真实原生在线登录不是本地开发完成的同义词。

## 两种模式

`ACCOUNTS_ACCOUNT_MODE=self_service|managed`，默认 `self_service`；未知值拒绝启动。

- self_service：维持现有邮箱注册、验证、邮件找回。生产仍必须 SMTP 且邮箱验证后才能取得桌面授权。
- managed：仅管理员开通的有效账号可取得授权和使用会话；允许明确的 `ACCOUNTS_MAIL_DELIVERY=disabled`。不需要 SMTP 变量，绝不能填虚假的发件人或凭据才能启动。自助注册、发送验证、邮件找回和消费既有邮件链接均不可用；GET/POST直接访问也不能创建账号、令牌、邮件或变更密码。页面给出管理员开通/联系管理员重置的真实说明。

两种模式生产环境都继续要求 HTTPS issuer、强密钥、独立数据库角色、精确可信网关与安全 Cookie/CSRF。不得把公网 IP 或旧域名作为未经确认的新 issuer；调试仅允许既有 loopback 模式。模式是部署政策，变更模式时必须轮换外部 SESSION_EPOCH 并重新登录，不在本任务实现运行时切换。

## 账号信任与管理员操作

User 增加布尔 `admin_provisioned`，默认 false，迁移不自动批准既有用户；`verified_at` 仅代表真实邮件验证，管理员创建不设置它。统一服务端资格判断：有效账号且在 managed 下 admin_provisioned=true，在 self_service 下 verified_at 非空。

OAuth 授权码兑换、refresh、access/API、浏览器授权均使用同一资格政策；会话600秒access、30天固定refresh家族、PKCE S256、RS256、撤销/重放/epoch/密码/停用失效规则保持。

新增管理命令 `provision_account --email ... --name ...`，只在 managed 模式创建普通非staff、非superuser账号，不覆盖既有同邮箱账号；大小写规范、昵称与Django强密码校验保持。密码通过受控终端隐藏输入并确认，或显式 `--password-stdin` 从私有输入读取，禁止密码参数、日志/命令输出、默认密码或不可用的邮件重置。管理员可用同样私密输入方式的 `set_account_password --email ...` 重置；重置使用现有用户优先事务锁并使全部浏览器/授权码/桌面会话失效。密码哈希算法和工作因子不降低。

admin_provisioned 不由注册表单、客户端或普通资料API编辑；Web管理界面只读显示它。其任何通过正常model save的变更都要永久更新auth_version，防止撤销后再批准使旧凭据复活；保留既有并发admin表单只写changed字段的修复。停用/重新启用规则保持。

## 桌面契约与界面

受固定issuer、HTTPS和Bearer保护的 `/api/v1/me` 增加 `administratorApproved` 布尔：仅 managed 且有效管理员开通账号为true。`emailVerified` 继续如实返回 verified_at 状态。此资格字段与现有emailVerified一样来自原生读取的受认证API，不接受React提供的profile或资格标记。

Rust Profile增加 `administrator_approved: bool`（serde camelCase，缺失默认false）；profile资格判断统一为 email_verified || administrator_approved，且原有subject/session绑定、ID token签名/issuer/audience/azp/nonce/时间和credential隔离均保持。至少测试未验证且未批准拒绝、未验证但管理员批准接受、批准flag类型错误拒绝、subject/session不匹配拒绝。检查login、restore/refresh、status和update-profile的相关路径，不只改单处commit。

登录按钮使用中性“登录账户”，浏览器在managed显示“账号由管理员开通；密码问题请联系管理员”。不虚假显示邮箱已验证，不提供不可用自助注册/找回入口；self_service浏览器保留可用注册/找回。账户仍在中栏；WB/IF/统计游客、草稿、正方形活动视图与现有OS凭据保护不变。

## ECS 准备与范围

提供 managed 专用env示例和Compose override/启动说明，明确只启动api/db、无mail worker；不改变self_service原有worker默认行为。生产配置自检允许managed+disabled且拒绝self_service+disabled，保护原有数据库角色、网关、HTTPS、日志和资源边界；managed api+db限额仍是既有144+160MiB，尚未经ECS实测。

本地启动器支持 `--account-mode managed`（默认self_service），使用其独立目录、PG端口和epoch。验证真实服务创建/密码登录/OAuth授权/会话列表/本机与全部退出/管理员重置/停用后失效；真实邮寄和公网不宣称完成。账户服务、数据库测试环境独立于科学环境与已安装Titan数据。

不生成未加口令的SSH私钥，不修改authorized_keys、安全组、Docker/sudo组、现有Caddy、旧产品库或公网路由。后续由负责人提供受控管理通道、确定新域名；只有届时核验资源和完整候选配置后才能部署。邮件服务对managed模式不是前置条件。

## 验收证据

新模式的真实PG端点/生命周期/管理员并发回归，生产配置组合失败/成功矩阵、disabled endpoints无副作用；原self_service全套回归。原生通过真实本地managed服务但测试用内存store完成完整协议循环，不依赖当前失败的OS Keychain；继续保留其失败门槛。前端测试与相关浏览器流程覆盖中性入口、未验证但受管理员批准资料和原中栏/草稿功能。ECS访问、域名/TLS、Docker容量和当前Keychain各有独立状态，不用mock或本地通过替代。

## 交给构建者的选择

沿用Django/PostgreSQL/Tauri/React及既有依赖，不新增身份框架。新管理代码可拆为policy.py和management helper以减少重复；选择最小可维护实现。命令错误和字段名称以上述契约为准。用独立临时本地环境保留可复现证据，结束时停止自己启动的进程。无需重新确认用户已经明确的功能范围或执行方式。
