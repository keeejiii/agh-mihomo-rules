# AdGuard Home mihomo DNS Rules

[![Generate AdGuard Home Rules](https://github.com/keeejiii/agh-mihomo-rules/actions/workflows/update-rules.yml/badge.svg)](https://github.com/keeejiii/agh-mihomo-rules/actions/workflows/update-rules.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE)

把 mihomo / Clash 的域名规则集转换成 AdGuard Home `upstream_dns_file` 规则文件。

## 这个项目适合谁

- **想直接拿现成规则用**：下载 latest release，丢给 AdGuard Home
- **想自己生成规则**：fork 后配 GitHub Actions Variables，按自己的规则组和 DNS upstream 生成

## 5 秒看懂

- 输入：mihomo / Clash 的 `.list`、`.yaml` 域名规则
- 输出：AdGuard Home `upstream_dns_file`
- 多组规则支持：`RULESET_NAMES` 控制优先级
- 变量约定：统一使用 **全大写** `RULESET_NAMES`、`DOMAIN_<NAME>`、`DNS_<NAME>`、`DEFAULT_DNS`
- 更新方式：每天北京时间 **06:15** 左右自动运行；只有产物变化时才更新 latest release

### 最短配置示例

```text
RULESET_NAMES=GOOGLE,MICROSOFT

DOMAIN_GOOGLE=https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/refs/heads/master/rule/Clash/Google/Google.list
DNS_GOOGLE=https://dns.google/dns-query https://cloudflare-dns.com/dns-query

DOMAIN_MICROSOFT=https://github.com/blackmatrix7/ios_rule_script/blob/master/rule/Clash/Microsoft/Microsoft.yaml
DNS_MICROSOFT=h3://dns.alidns.com/dns-query quic://dns.alidns.com

DEFAULT_DNS=https://cloudflare-dns.com/dns-query
https://dns.google/dns-query
```

## 直接使用

### 1) 下载 latest release

```bash
mkdir -p /opt/AdGuardHome
curl -L https://github.com/keeejiii/agh-mihomo-rules/releases/latest/download/agh-mihomo-rules.txt -o /opt/AdGuardHome/agh-mihomo-rules.txt
```

直链：<https://github.com/keeejiii/agh-mihomo-rules/releases/latest/download/agh-mihomo-rules.txt>

### 2) 在 AdGuard Home 里引用

```yaml
dns:
  upstream_dns_file: /opt/AdGuardHome/agh-mihomo-rules.txt
```

> 如果你只是想直接使用仓库当前发布的规则文件，到这里就够了。

## 自定义生成

如果你想把自己的 mihomo / Clash 域名规则集转换成 AdGuard Home 规则，建议 fork 本仓库后配置 GitHub Actions Variables。

仓库页面路径：

**Settings → Secrets and variables → Actions → Variables**

### 配置原则

- 统一使用 **全大写变量名**：`RULESET_NAMES`、`DOMAIN_<NAME>`、`DNS_<NAME>`、`DEFAULT_DNS`
- 顶部那段“最短配置示例”就是推荐写法
- `RULESET_NAMES` 决定规则组优先级顺序

### 每个变量怎么写

#### `RULESET_NAMES`

```text
RULESET_NAMES=GOOGLE,MICROSOFT
```

- 决定规则组优先级顺序
- 前面的组优先，后面的组补充
- 建议始终显式填写
- 如果不填，workflow 会尝试从已成对的 `DOMAIN_*` + `DNS_*` 自动推断

#### `DOMAIN_<NAME>`

```text
DOMAIN_GOOGLE=https://example.com/a.yaml
https://example.com/b.list
```

- 一行一个规则集 URL
- 支持 `.list` / `.yaml` 混合
- 支持 `raw.githubusercontent.com/...`
- 也兼容普通 GitHub `blob` 链接，workflow 会自动转成 raw 下载地址

#### `DNS_<NAME>`

```text
DNS_GOOGLE=https://dns.google/dns-query https://cloudflare-dns.com/dns-query
```

- 对应规则组命中后使用的 DNS upstream
- 支持多个 DNS server
- 可以写成空格分隔，也可以分多行写
- 最终输出时会合并成 AdGuard Home 支持的同一行空格分隔格式

#### `DEFAULT_DNS`

```text
DEFAULT_DNS=https://cloudflare-dns.com/dns-query
https://dns.google/dns-query
```

- 可选
- 会写在输出文件最前面，作为默认 upstream
- `DEFAULT_DNS` 会按空白拆分，**最终一行一个 upstream**
- 这个拆分规则只对 `DEFAULT_DNS` 生效；域名匹配规则里的多个 DNS 仍保留在同一行

## 支持的输入规则

### `.list`

当前会提取这些形式：

- `example.com`
- `+.example.com`
- `DOMAIN,example.com`
- `DOMAIN-SUFFIX,example.com`

其他格式忽略。

### `.yaml`

当前会提取：

- `DOMAIN,example.com`
- `DOMAIN-SUFFIX,example.com`

例如：

```yaml
- DOMAIN,example.com,DIRECT
- DOMAIN-SUFFIX,google.com,Proxy
```

会只提取域名部分。

## 输出规则说明

输出是 AdGuard Home 的 `upstream_dns_file` 格式。

示例：

```text
https://cloudflare-dns.com/dns-query
https://dns.google/dns-query
[/google.com/]https://dns.google/dns-query https://cloudflare-dns.com/dns-query
[/microsoft.com/]h3://dns.alidns.com/dns-query quic://dns.alidns.com
```

含义：

- 前两行是 `DEFAULT_DNS`
- 后面每一行是“域名匹配 → 对应 DNS upstream”
- `[/example.com/]...` 会匹配根域和子域

当前版本里：

- `DOMAIN-SUFFIX,example.com` → `[/example.com/]...`
- `DOMAIN,example.com` → `[/example.com/]...`

也就是说，当前**不再生成** `[/*.example.com/]#` 这种回退规则。

## 冲突与优先级

优先级由 `RULESET_NAMES` 的顺序决定。

例如：

```text
RULESET_NAMES=GOOGLE,MICROSOFT
```

表示 `GOOGLE` 优先，`MICROSOFT` 次之。

如果多个规则组里出现同一个域名：

- 前面的规则组优先
- 后面的同域名规则会被忽略

## 工作流会做什么

1. 读取 `RULESET_NAMES`
2. 读取每组 `DOMAIN_<NAME>` / `DNS_<NAME>`
3. 下载所有规则集
4. 提取支持的域名规则
5. 合并生成 `converted/agh-mihomo-rules.txt`
6. 仅在输出变化时更新 latest release

## 设计边界

当前版本刻意只做这些：

- 只处理域名类规则
- 只支持 `.list` 和 `.yaml` 输入
- 只提取 `DOMAIN` 和 `DOMAIN-SUFFIX`
- `DOMAIN` 当前按 `DOMAIN-SUFFIX` 处理
- 不做 TLD 特判、裁剪或额外压缩
- 不预设任何固定 DNS 分类模板
- 默认 DNS 只通过 `DEFAULT_DNS` 注入
- 规则组、规则源和 DNS 映射全部由 Variables 决定
- 不引入额外复杂配置文件格式

## 第三方声明

本项目代码采用 MIT License。

规则生成涉及第三方规则数据以及不同许可证来源。重新分发前，请自行审查上游许可证与使用条件。

详见 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md)。
