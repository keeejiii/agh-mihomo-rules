# 第三方声明

## 代码来源

本项目最初从 `agh-cn-rules` 项目骨架演化而来，并重写为面向 mihomo `.list` / `.yaml` 规则集的通用转换器。

- 原项目代码许可证：MIT

## 规则来源

本项目不内置固定规则数据。

用户通过 GitHub Actions Variables 提供外部规则集 URL，工作流运行时再临时下载并转换。

因此：

- 规则内容的版权与许可证，取决于你配置的上游规则集
- 在公开分发生成产物前，请自行确认上游规则集是否允许再分发和派生使用

## AdGuard Home 语法参考

项目输出格式基于 AdGuard Home 官方文档中的 domain-specific upstream 语法：

- <https://github.com/AdguardTeam/AdGuardHome/wiki/Configuration>

## 附注

第三方内容可公开访问，不代表自动获得再分发、修改或再许可授权。
