# TiDB 与 Demo 数据底座说明

TiDB 是兼容 MySQL 通信协议的分布式 SQL 数据库。本 Demo 使用 TiDB Cloud Starter 保存订单、知识文档、文本分块、向量、会话和长期偏好。Python 应用通过 SQLAlchemy 和 PyMySQL 连接 Starter，并使用 TLS 保护连接。

TiDB 的 HTAP 能力由 TiKV 行存与 TiFlash 列存共同支撑。业务数据首先写入 TiKV，目标表配置 TiFlash 副本后，数据实时复制到列存，以支持分析查询。TiFlash 副本需要针对表配置，不应把 Starter 与独立的 TiDB Cloud Lake 理解为自动同步的一体资源。

本 Demo 的向量列固定为 1024 维，与百炼 text-embedding-v4 请求的显式维度一致。知识检索使用 VEC_COSINE_DISTANCE 计算距离，距离越小通常表示语义越接近。所有查询必须带 tenant_id 条件，避免跨租户返回文档。
