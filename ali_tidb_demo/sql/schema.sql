-- All tables are tenant-scoped. This script does not insert business data.
CREATE TABLE IF NOT EXISTS sales_orders (
  order_id       VARCHAR(64) PRIMARY KEY,
  tenant_id      VARCHAR(64) NOT NULL,
  region         VARCHAR(32) NOT NULL,
  amount         DECIMAL(18,2) NOT NULL,
  status         VARCHAR(32) NOT NULL,
  ordered_at     DATETIME NOT NULL,
  KEY idx_tenant_region_time (tenant_id, region, ordered_at)
);

CREATE TABLE IF NOT EXISTS documents (
  document_id    VARCHAR(64) PRIMARY KEY,
  tenant_id      VARCHAR(64) NOT NULL,
  title          VARCHAR(512) NOT NULL,
  source_uri     VARCHAR(1024),
  content_hash   CHAR(64) NOT NULL,
  status         VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at     TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_tenant_hash (tenant_id, content_hash),
  KEY idx_tenant_document_status (tenant_id, status, document_id)
);

CREATE TABLE IF NOT EXISTS document_chunks (
  chunk_id        VARCHAR(64) PRIMARY KEY,
  document_id     VARCHAR(64) NOT NULL,
  tenant_id       VARCHAR(64) NOT NULL,
  chunk_no        INT NOT NULL,
  content         TEXT NOT NULL,
  embedding       VECTOR(1024) NOT NULL,
  embedding_model VARCHAR(64) NOT NULL,
  VECTOR INDEX idx_chunk_embedding ((VEC_COSINE_DISTANCE(embedding))),
  UNIQUE KEY uk_document_chunk (document_id, chunk_no),
  KEY idx_tenant_document (tenant_id, document_id)
);

CREATE TABLE IF NOT EXISTS conversations (
  conversation_id    VARCHAR(64) PRIMARY KEY,
  tenant_id          VARCHAR(64) NOT NULL,
  user_id            VARCHAR(64) NOT NULL,
  bailian_session_id VARCHAR(128),
  session_updated_at DATETIME(6),
  summary            TEXT,
  created_at         TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
  updated_at         TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6)
                      ON UPDATE CURRENT_TIMESTAMP(6),
  KEY idx_tenant_user (tenant_id, user_id, updated_at)
);

CREATE TABLE IF NOT EXISTS messages (
  message_id      VARCHAR(64) PRIMARY KEY,
  conversation_id VARCHAR(64) NOT NULL,
  tenant_id       VARCHAR(64) NOT NULL,
  role            VARCHAR(16) NOT NULL,
  content         MEDIUMTEXT NOT NULL,
  created_at      TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_conversation_time (conversation_id, message_id)
);

CREATE TABLE IF NOT EXISTS agent_memories (
  memory_id   VARCHAR(64) PRIMARY KEY,
  tenant_id   VARCHAR(64) NOT NULL,
  user_id     VARCHAR(64) NOT NULL,
  memory_type VARCHAR(32) NOT NULL,
  content     TEXT NOT NULL,
  confidence  DECIMAL(4,3) NOT NULL DEFAULT 1.000,
  status      VARCHAR(16) NOT NULL DEFAULT 'active',
  updated_at  TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6)
               ON UPDATE CURRENT_TIMESTAMP(6),
  KEY idx_user_memory (tenant_id, user_id, status, memory_type)
);

CREATE TABLE IF NOT EXISTS agent_tasks (
  task_id         VARCHAR(64) PRIMARY KEY,
  tenant_id       VARCHAR(64) NOT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  task_type       VARCHAR(64) NOT NULL,
  status          VARCHAR(32) NOT NULL,
  input_json      JSON,
  output_uri      VARCHAR(1024),
  error_message   TEXT,
  created_at      TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
  updated_at      TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6)
                   ON UPDATE CURRENT_TIMESTAMP(6),
  UNIQUE KEY uk_tenant_idempotency (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS agent_events (
  event_id        VARCHAR(64) PRIMARY KEY,
  tenant_id       VARCHAR(64) NOT NULL,
  conversation_id VARCHAR(64),
  event_type      VARCHAR(64) NOT NULL,
  payload         JSON NOT NULL,
  delivery_status VARCHAR(16) NOT NULL DEFAULT 'pending',
  retry_count     INT NOT NULL DEFAULT 0,
  available_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_at      TIMESTAMP(6) DEFAULT CURRENT_TIMESTAMP(6),
  KEY idx_delivery (delivery_status, available_at, event_id)
);
