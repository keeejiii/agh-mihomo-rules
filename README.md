# agh-mihomo-rules

把 mihomo / Clash 风格的 `.list`、`.yaml` 域名规则集转换成 AdGuard Home `upstream_dns_file` 规则。

## 这个项目做什么

支持把多个远程规则集按“规则组 → DNS 服务器”的方式合并输出。

每个规则组都可以：

- 绑定多个规则集 URL
- 绑定多个 DNS server
- 按你声明的组顺序决定优先级

当前只支持两类输入：

- `.list`
- `.yaml` / `.yml`

## 支持的规则

### `.list`

只提取：

- `example.com`
- `+.example.com`
- `DOMAIN,example.com`
- `DOMAIN-SUFFIX,example.com`

其他格式忽略。

### `.yaml`

只提取：

- `DOMAIN,example.com`
- `DOMAIN-SUFFIX,example.com`

无论规则后面有没有策略名，例如：

```yaml
- DOMAIN,example.com,DIRECT
- DOMAIN-SUFFIX,google.com,Proxy
```

都会正确提取域名部分。

## 优先级规则

优先级由 `RULESET_NAMES` 里的顺序决定。

例如：

```text
RULESET_NAMES=meta,google
```

表示：

1. `meta` 优先
2. `google` 次之

### 冲突处理

- 同一个域名的 `DOMAIN` / 精确规则冲突：先出现的规则组优先
- 同一个域名的 `DOMAIN-SUFFIX` / 后缀规则冲突：先出现的规则组优先
- 如果前面的规则组先声明了 `DOMAIN-SUFFIX,example.com`，后面的 `DOMAIN,example.com` 会被忽略
- 如果前面的规则组先声明了 `DOMAIN,example.com`，后面的 `DOMAIN-SUFFIX,example.com` 只会接管 `*.example.com`，不会覆盖根域 `example.com`

这是为了尽量保留 mihomo 里 `DOMAIN` 和 `DOMAIN-SUFFIX` 的语义差异。

## GitHub Actions 变量配置

GitHub Variables 不支持变量名里带冒号，所以这里不用 `domain:meta` / `dns:meta`，改成下面这套：

### 必填变量

#### 1) 规则组顺序

```text
RULESET_NAMES=meta,google
```

- 推荐填写
- 它决定规则组优先级顺序
- 如果不填，workflow 会自动从已配置的 `DOMAIN_*` + `DNS_*` 配对里推断规则组，并按名称字母序作为顺序；**能跑，但不建议长期依赖**

#### 2) 每个规则组的域名规则集 URL

```text
DOMAIN_META=https://example.com/a.yaml
https://example.com/b.list

DOMAIN_GOOGLE=https://example.com/c.yaml
```

- 一行一个 URL
- 可以 `.yaml` 和 `.list` 混合
- 支持 `raw.githubusercontent.com/...` 链接
- 也兼容普通 GitHub blob 链接，workflow 运行时会自动转成 raw 下载地址

#### 3) 每个规则组对应的 DNS

```text
DNS_META=h3://dns.alidns.com/dns-query quic://dns.alidns.com https://doh.pub/dns-query
DNS_GOOGLE=https://dns.google/dns-query https://cloudflare-dns.com/dns-query
```

- 支持多个 DNS server
- 可以写成空格分隔，也可以分多行写，最终都会合并成 AdGuard Home 支持的空格分隔格式

#### 4) 可选默认 DNS

```text
DEFAULT_DNS=https://cloudflare-dns.com/dns-query
https://dns.google/dns-query
```

- 一行一个 upstream
- 可选；不填也能生成
- 填了以后，会写在输出文件最前面，作为未命中域名规则时的默认 upstream

## 输出规则说明

输出是 AdGuard Home 的 `upstream_dns_file` 规则。

示例：

```text
[/example.com/]https://dns.google/dns-query
[/*.only-sub.example/]#
```

说明：

- `[/example.com/]...`：匹配根域和子域
- `[/*.example.com/]...`：只匹配子域，不匹配根域
- `#`：回退到 AdGuard Home 的默认 upstream

所以：

- `DOMAIN-SUFFIX,example.com` 会转成：`[/example.com/]...`
- `DOMAIN,example.com` 会转成两条：
  - `[/example.com/]...`
  - `[/*.example.com/]#`

这样可以尽量保留“只匹配根域”的语义。

## 使用方式

工作流会自动生成：

- `converted/agh-mihomo-rules.txt`
- latest release 附件同名文件

在 `AdGuardHome.yaml` 里引用：

```yaml
dns:
  upstream_dns_file: /path/to/agh-mihomo-rules.txt
```

如果你配置了 `DEFAULT_DNS`，输出文件前几行就会直接带默认 upstream；如果不配，默认 upstream 继续由 AdGuard Home 主配置决定。

## 当前工作流做什么

1. 读取 `RULESET_NAMES`
2. 读取每个 `DOMAIN_<NAME>` / `DNS_<NAME>`
3. 下载所有规则集
4. 提取支持的域名规则
5. 合并并生成 `agh-mihomo-rules.txt`
6. 仅在产物变化时更新 latest release

## 示例规则集

- `https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/refs/heads/master/rule/Clash/ChinaMax/ChinaMax_Classical.yaml`

## 设计边界

当前最初版刻意只做这些：

- 只支持远程 `.list` / `.yaml` / `.yml`
- 只提取 `DOMAIN` 和 `DOMAIN-SUFFIX` 相关规则
- 不做旧项目那种 `.cn` 子域名裁剪
- 不按“中国/国外”内置固定 DNS 模板处理
- 默认 DNS 只通过可选变量 `DEFAULT_DNS` 注入，不做内置预设
- 不引入额外的复杂配置文件格式

如果后面要扩展，再加：

- 本地配置文件模式
- 更多 mihomo 规则类型
- 产物命名可配置
- 更详细的统计和调试输出
