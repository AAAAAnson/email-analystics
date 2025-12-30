-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 邮件表
CREATE TABLE IF NOT EXISTS emails (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(255) UNIQUE NOT NULL,
    subject TEXT,
    sender VARCHAR(255),
    recipients TEXT,
    cc TEXT,
    date TIMESTAMP WITH TIME ZONE,
    body_text TEXT,
    body_html TEXT,
    folder VARCHAR(100) DEFAULT 'INBOX',
    is_read BOOLEAN DEFAULT FALSE,
    has_attachments BOOLEAN DEFAULT FALSE,
    attachments JSONB DEFAULT '[]',
    raw_headers JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 邮件向量表 (用于RAG)
CREATE TABLE IF NOT EXISTS email_vectors (
    id SERIAL PRIMARY KEY,
    email_id INTEGER REFERENCES emails(id) ON DELETE CASCADE,
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT NOT NULL,
    embedding vector(1024),  -- DeepSeek embedding维度
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 对话历史表
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user' or 'assistant'
    content TEXT NOT NULL,
    related_emails JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 同步状态表
CREATE TABLE IF NOT EXISTS sync_status (
    id SERIAL PRIMARY KEY,
    folder VARCHAR(100) NOT NULL,
    last_uid INTEGER DEFAULT 0,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    total_emails INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'idle',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(folder)
);

-- 创建向量索引 (IVFFlat索引加速相似度搜索)
CREATE INDEX IF NOT EXISTS email_vectors_embedding_idx ON email_vectors
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 创建其他常用索引
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date DESC);
CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender);
CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(folder);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id, created_at);

-- 插入默认同步状态
INSERT INTO sync_status (folder, status) VALUES ('INBOX', 'idle') ON CONFLICT DO NOTHING;
