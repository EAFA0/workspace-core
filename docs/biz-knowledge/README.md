# Biz Knowledge Contract

本目录是业务规则、领域概念和跨仓业务约定的 owner。

## 内容边界

- 描述业务上必须满足什么，不复制需求原文。
- 不记录代码实现、字段布局或工具参数。
- 规则必须可验证，并标明来源。
- 同一规则只在一篇业务知识文档维护，其他位置使用链接。

## 命名与结构

- 文件名：`<feature-slug>.md`
- 每篇文档至少包含：
  - 业务领域概述
  - 核心规则
  - 规则来源
  - 涉及的实现链路
  - 对应业务测试

## 索引

当前 workspace 的条目索引位于 [INDEX.md](./INDEX.md)。索引只负责发现，不承载规则正文。

知识分类和召回顺序见 [`03-knowledge-model.md`](../architecture/03-knowledge-model.md)。
