# 邮件智能助手

基于RAG(检索增强生成)的智能邮件管理助手，使用DeepSeek AI提供智能对话能力。

## 功能特性

- 邮件同步：自动同步网易邮箱(163/126)的所有邮件
- 实时接收：定时检查新邮件，自动同步
- AI记忆：基于向量化的RAG系统，让AI"记住"所有邮件内容
- 智能对话：基于邮件内容的智能问答
- 邮件搜索：语义搜索，找到相关邮件
- 邮件摘要：自动总结近期邮件

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│  Frontend (Vue3)  │  Backend (FastAPI)  │  PostgreSQL+pgvector│
│      :9091        │       :9090         │       :5432         │
├─────────────────────────────────────────────────────────────┤
│     Redis         │   Celery Worker     │   Celery Beat       │
│     :6379         │   (异步任务)         │   (定时任务)         │
└─────────────────────────────────────────────────────────────┘
```

## 快速开始

### 1. 环境要求

- Docker Desktop (Windows/Mac)
- 网易邮箱开启IMAP服务
- DeepSeek API Key

### 2. 配置

复制配置文件并填写信息：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 邮箱配置 (必填)
EMAIL_ADDRESS=your_email@163.com
EMAIL_PASSWORD=your_authorization_code  # 授权码，不是登录密码

# DeepSeek API (必填)
DEEPSEEK_API_KEY=your_deepseek_api_key

# 其他配置可保持默认
```

> **获取网易邮箱授权码**: 登录网易邮箱 → 设置 → POP3/SMTP/IMAP → 开启IMAP → 生成授权码

### 3. 启动服务

```bash
docker-compose up -d
```

首次启动会自动：
- 下载所需镜像
- 初始化数据库
- 下载Embedding模型（约500MB）

### 4. 访问

- 前端界面: http://localhost:9091
- API文档: http://localhost:9090/docs

## 使用指南

### 同步邮件

1. 打开首页，点击"同步邮件"按钮
2. 系统会自动获取邮箱中的邮件并向量化
3. 同步完成后可以开始AI对话

### AI对话

在"AI助手"页面，你可以问：

- "最近有什么重要邮件？"
- "帮我找一下张三发的邮件"
- "上周关于项目的邮件有哪些？"
- "总结一下本月的邮件"

### 邮件搜索

AI会自动在邮件中搜索相关内容，基于语义理解而非关键词匹配。

## 端口说明

| 端口 | 服务 |
|------|------|
| 9090 | 后端API |
| 9091 | 前端页面 |
| 9092 | WebSocket(预留) |

## 常见问题

### Q: 邮件同步失败？

1. 确认邮箱IMAP服务已开启
2. 确认使用的是授权码而非登录密码
3. 检查网络连接

### Q: AI回答不准确？

1. 确认邮件已同步并向量化
2. 在设置页面检查向量化状态
3. 尝试重新向量化

### Q: 首次启动很慢？

首次启动需要下载Embedding模型(约500MB)，请耐心等待。

## 开发

```bash
# 后端开发
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9090

# 前端开发
cd frontend
npm install
npm run dev
```

## 技术栈

- **后端**: Python FastAPI, Celery, SQLAlchemy
- **前端**: Vue 3, Element Plus, Vite
- **数据库**: PostgreSQL + pgvector
- **AI**: DeepSeek API, Sentence-Transformers
- **部署**: Docker Compose

## License

MIT
