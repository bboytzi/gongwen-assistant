# 公文辅助系统

面向国企日常办公的公文起草、检索与知识库管理系统。

系统名称与标识可由管理员在「设置 → 系统外观」中自定义。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + Celery
- **前端**: Vue 3 + Element Plus + TinyMCE
- **数据库**: PostgreSQL 16 (pgvector + zhparser)
- **缓存/队列**: Redis 7
- **部署**: Docker Compose (单机 4核8G)

## 快速开始

### 1. 环境准备

- Docker + Docker Compose
- PostgreSQL 16 with pgvector + zhparser (Docker 镜像已包含)
- LLM API Key (DeepSeek/通义/智谱)

### 2. 部署

```bash
git clone https://github.com/bboytzi/gongwen-assistant.git
cd gongwen-assistant
docker-compose up -d
```

访问 `http://<服务器IP>` 即可使用。

### 3. 首次使用

1. 注册账号
2. 在「设置」页面配置 LLM API Key
3. 在「知识库」上传管理办法和个人案例
4. 在「新建公文」创建公文

## 项目结构

```
gongwen-assistant/
├── app/
│   ├── backend/          # FastAPI 后端
│   │   ├── api/          # API 路由
│   │   ├── core/         # 配置、数据库、安全、加密
│   │   ├── models/       # SQLAlchemy 数据模型
│   │   ├── schemas/      # Pydantic 验证模型
│   │   ├── services/     # LLM客户端、文件解析、检索、Word排版、生成流水线
│   │   ├── tasks/        # Celery 异步任务
│   │   ├── sql/          # 数据库初始化 SQL
│   │   ├── main.py       # FastAPI 入口
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   ├── frontend/         # Vue 3 前端
│   │   ├── src/
│   │   │   ├── api/      # Axios 请求层
│   │   │   ├── components/ # 公共组件
│   │   │   ├── router/   # Vue Router
│   │   │   ├── store/    # Pinia 状态管理
│   │   │   ├── views/    # 页面组件
│   │   │   └── assets/   # 样式
│   │   └── Dockerfile
│   └── nginx/            # Nginx 配置
├── data/                 # 数据存储（不提交）
├── docs/                 # 设计文档
├── docker-compose.yml
└── README.md
```

## 文档

- [详细设计文档](docs/design.md)
