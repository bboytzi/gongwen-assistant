# 公文辅助系统 — 详细设计文档

> 版本：v1.3  
> 日期：2026-10-27  
> 作者：陶冶  
> 状态：已上线  
> 更新：v1.3 系统更名为「公文辅助系统」；v1.2 补充检索中心页和导出弹窗 UI 设计，更新 UI 章节

---

## 1. 需求确认

### 1.1 核心目标

面向国企日常办公场景，自动生成符合公文格式的请示材料，同时提供历史材料检索和知识库管理能力。系统名称：「公文辅助系统」。

### 1.2 需求约束（已确认）

| 编号 | 需求项 | 确认内容 |
|------|--------|----------|
| R1 | LLM 接入方式 | 采用公有云 API，支持用户自行配置 API Key 和模型 |
| R2 | Word 排版 | 需要精确排版到 Word，用户可上传自己的模板 |
| R3 | 用户规模 | 并发 10 人 |
| R4 | 部署方式 | 公有云 API，不本地部署模型 |
| R5 | 知识库层级 | 公司级（统一上传管理办法）+ 个人级（个人历史材料） |
| R6 | 文件格式 | 支持 Word (.docx) 和 PDF 上传 |
| R7 | 审批流程 | 不需要，系统只负责生成+导出，用户通过 OA 系统提交 |
| R8 | 数据备份 | 不需要考虑 |
| R9 | 域名与 HTTPS | 直接用 IP 访问，后续自行配置 |
| R10 | 公文格式标准 | 已提供：《集团公文标准与格式》实际文件，见附录 A |
| R11 | 请示类型分类 | 已提供：采购请示模板（含 5 种采购场景），见附录 B |

### 1.3 功能清单

```
F1  用户管理
    F1.1  注册/登录/JWT 认证
    F1.2  角色权限：admin（公司知识库管理员）、user（普通用户）
    F1.3  LLM API 配置管理（每个用户配自己的 Key）

F2  知识库管理
    F2.1  公司级知识库：admin 上传管理办法、制度文件
    F2.2  个人知识库：用户上传自己写过的请示材料
    F2.3  文件解析：PDF → 文本、DOCX → 文本
    F2.4  文档分块 + Embedding 入库
    F2.5  文档列表、搜索、删除、重新解析

F3  请示模板管理
    F3.1  用户上传 Word 模板（.docx）
    F3.2  模板占位符识别（{{标题}}、{{事由}} 等标记）
    F3.3  模板预览和占位符映射配置

F4  请示材料生成
    F4.1  表单输入：请示类型、事由、关键要素
    F4.2  RAG 检索：从知识库提取相关条款 + 相似案例
    F4.3  LLM 多轮生成：大纲 → 分段 → 引用标注
    F4.4  公文格式化 + 套用 Word 模板
    F4.5  生成结果预览 + 在线编辑
    F4.6  导出 Word/PDF
    F4.7  版本管理（每次生成/编辑留存）

F5  材料检索
    F5.1  全文检索（关键词）
    F5.2  语义检索（自然语言描述）
    F5.3  混合排序
    F5.4  检索结果高亮 + 引用溯源

F6  系统管理
    F6.1  LLM 配置测试（连通性、可用模型列表）
    F6.2  系统使用统计
```

---

## 2. 系统架构

### 2.1 整体架构

```
                        ┌──────────────────────────┐
                        │      Nginx (反向代理)      │
                        │   HTTP / 静态资源 / WS    │
                        └─────────┬────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │              │
              ┌─────▼─────┐ ┌────▼─────┐ ┌─────▼──────┐
              │  前端 SPA  │ │ FastAPI  │ │  Celery    │
              │  Vue3 +    │ │  后端    │ │  Worker    │
              │  Element+ │ │ (uvicorn)│ │ (异步任务)  │
              └───────────┘ └────┬─────┘ └─────┬──────┘
                                 │              │
                    ┌────────────┴──────────────┘
                    │
          ┌─────────┼──────────┬─────────────┐
          │         │          │             │
    ┌─────▼───┐ ┌──▼───┐ ┌────▼────┐ ┌─────▼─────┐
    │PostgreSQL│ │Redis │ │ 文件存储 │ │ LLM API   │
    │ 16 +     │ │ 7    │ │ (本地FS) │ │ (云端转发) │
    │ pgvector │ │      │ │         │ │           │
    │ + zhparser│ │     │ │         │ │           │
    └──────────┘ └──────┘ └─────────┘ └───────────┘
```

### 2.2 技术选型

| 层级 | 组件 | 选型 | 版本 | 理由 |
|------|------|------|------|------|
| 前端框架 | SPA | Vue 3 | 3.4+ | 生态成熟，Element Plus 适合管理后台 |
| UI 组件库 | 组件 | Element Plus | 2.7+ | 国企风格，表格/表单/对话框完善 |
| 富文本编辑 | 编辑器 | TinyMCE | 6.x | 兼容性好，支持自定义工具栏 |
| 后端框架 | API | FastAPI | 0.110+ | 异步、自动文档、Python LLM 生态 |
| 运行时 | Python | 3.12 | - | 稳定，与 FastAPI / LangChain 兼容 |
| 数据库 | RDBMS | PostgreSQL | 16 | 单库支持关系数据 + 向量 + 全文 |
| 向量扩展 | Embedding | pgvector | 0.7+ | 直接在 PG 内做向量检索，无需额外服务 |
| 中文分词 | FTS | zhparser | 2.2+ | PG 中文全文检索扩展 |
| 缓存/队列 | KV | Redis | 7.x | 会话 + Celery broker + 限流 |
| 异步任务 | Queue | Celery | 5.3+ | 文档解析、生成任务异步化 |
| Word 生成 | 文档 | python-docx | 1.1+ | 操作 .docx 模板占位符替换 |
| PDF 解析 | 文档 | pdfplumber | 0.10+ | 提取 PDF 文本，保留表格 |
| Word 解析 | 文档 | python-docx | - | 复用，读取 .docx 内容 |
| Embedding | 向量化 | 云 API | - | 跟随 LLM 配置，DeepSeek/通义/智谱等 |
| LLM 框架 | 编排 | LangChain | 0.2+ | RAG 流程编排、Prompt 模板管理 |
| Web 服务器 | 反代 | Nginx | 1.24+ | 反代 + 静态 + HTTPS |
| 容器化 | 部署 | Docker Compose | - | 单机编排，运维简单 |

### 2.3 4核8G 资源分配

```
组件                  CPU占用    内存占用    配置说明
─────────────────────────────────────────────────────────
PostgreSQL 16          1.0核     1.5G      shared_buffers=512MB
                                           work_mem=16MB
                                           max_connections=30
                                           维护工作内存 256MB
                                           (Embedding索引构建需要)

Redis 7                0.3核     256M      maxmemory=200mb
                                           淘汰策略: allkeys-lru

FastAPI (uvicorn)      1.0核     800M      2 workers
                                           uvloop + httptools
                                           并发上限: 50 连接

Celery worker           1.0核     1.2G      1 worker
                                           concurrency=2 (IO密集)
                                           (文档解析+生成)
                                           软限制: 内存 1G 时停止接新任务

Nginx                   0.2核     100M      worker_processes auto

系统 + 预留             0.5核     2.9G      OS + 突发缓冲
─────────────────────────────────────────────────────────
合计                    4.0核     ~6.8G      预留 1.2G 余量
```

**关键设计决策：**

1. **不在本地运行 LLM 模型** — 8G 内存无法承载，全部走云 API
2. **PostgreSQL 单库多角色** — 不拆分微服务数据库，30 连接足够 10 并发
3. **Celery concurrency=2** — 文档解析(CPU密集) 和 LLM 生成(IO密集) 共享队列，限制并发防止内存溢出
4. **pgvector 替代独立向量库** — 省掉一个 Milvus/Qdrant 进程，省 1G+ 内存
5. **Embedding 走云 API** — 不用本地 Embedding 模型，省内存

---

## 3. 数据模型设计

### 3.1 ER 关系图

```
users (用户)
  │ 1
  │
  ├───< knowledge_bases (知识库, N)
  │         │ 1
  │         ├───< kb_documents (知识文档, N)
  │         │         │ 1
  │         │         └───< kb_chunks (文档分块, N) ← 向量存储
  │         │
  │         └───< kb_templates (Word模板, N)
  │
  ├───< documents (请示材料, N)
  │         │ 1
  │         └───< document_versions (版本历史, N)
  │
  ├───< generation_tasks (生成任务, N)
  │
  └───< llm_configs (LLM配置, N)
```

### 3.2 核心表结构

#### 3.2.1 users — 用户表

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    username    VARCHAR(64) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    display_name VARCHAR(64),
    role        VARCHAR(16) NOT NULL DEFAULT 'user',  -- admin / user
    department  VARCHAR(128),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
```

#### 3.2.2 knowledge_bases — 知识库表

```sql
CREATE TABLE knowledge_bases (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    name        VARCHAR(128) NOT NULL,
    level       VARCHAR(16) NOT NULL DEFAULT 'personal', -- company / personal
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 公司级知识库：user_id 关联 admin，level='company'，全员可读
-- 个人级知识库：user_id 关联本人，level='personal'，仅本人可读

CREATE INDEX idx_kb_user ON knowledge_bases(user_id);
CREATE INDEX idx_kb_level ON knowledge_bases(level);
```

#### 3.2.3 kb_documents — 知识文档表

```sql
CREATE TABLE kb_documents (
    id          BIGSERIAL PRIMARY KEY,
    kb_id       BIGINT NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    title       VARCHAR(256) NOT NULL,
    doc_type    VARCHAR(32) NOT NULL,    -- regulation(管理办法) / case(案例) / template(模板) / historical(历史请示)
    file_path   VARCHAR(512),           -- 原始文件路径
    file_format VARCHAR(16),           -- pdf / docx
    content     TEXT,                   -- 解析后的全文文本
    meta        JSONB DEFAULT '{}',     -- 结构化属性：文号、发文部门、生效日期等
    status      VARCHAR(16) DEFAULT 'pending', -- pending/parsing/indexed/failed
    parse_error TEXT,
    chunk_count INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kbdoc_kb ON kb_documents(kb_id);
CREATE INDEX idx_kbdoc_type ON kb_documents(doc_type);
CREATE INDEX idx_kbdoc_status ON kb_documents(status);
```

#### 3.2.4 kb_chunks — 文档分块表（向量存储）

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE kb_chunks (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    kb_id       BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,         -- 冗余，加速权限过滤
    chunk_index INT NOT NULL,            -- 块在文档中的序号
    content     TEXT NOT NULL,            -- 分块文本
    embedding   vector(1024),            -- 向量（维度跟随 Embedding 模型）
    search_tsv  tsvector,                -- 全文检索向量
    meta        JSONB DEFAULT '{}',      -- 块属性：章节、页码等
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 向量索引（IVFFlat，适合中小规模）
CREATE INDEX idx_chunk_vec ON kb_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 全文检索索引
CREATE INDEX idx_chunk_fts ON kb_chunks USING gin(search_tsv);

-- 权限过滤索引
CREATE INDEX idx_chunk_user ON kb_chunks(user_id);
CREATE INDEX idx_chunk_kb ON kb_chunks(kb_id);

-- 分块时自动生成 tsvector
-- 触发器：插入/更新时自动从 content 生成 search_tsv
```

#### 3.2.5 kb_templates — Word 模板表

```sql
CREATE TABLE kb_templates (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    kb_id           BIGINT REFERENCES knowledge_bases(id),
    name            VARCHAR(128) NOT NULL,
    file_path       VARCHAR(512) NOT NULL,     -- .docx 文件路径
    placeholders    JSONB DEFAULT '[]',        -- 占位符列表：[{key, desc, type}]
    -- 占位符识别规则：{{key}} 格式，如 {{标题}}、{{事由}}、{{请示事项}}
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tpl_user ON kb_templates(user_id);
```

#### 3.2.6 documents — 请示材料表

```sql
CREATE TABLE documents (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    title           VARCHAR(256) NOT NULL,
    content         TEXT,                    -- 当前内容（富文本HTML）
    status          VARCHAR(16) DEFAULT 'draft', -- draft / final
    doc_type        VARCHAR(32),             -- 请示类型：人事/采购/资金/项目...
    source_kb_ids   BIGINT[],                -- 生成时引用的知识库
    generation_config JSONB DEFAULT '{}',     -- 生成参数记录
    template_id     BIGINT REFERENCES kb_templates(id), -- 使用的Word模板
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_doc_user ON documents(user_id);
CREATE INDEX idx_doc_type ON documents(doc_type);
```

#### 3.2.7 document_versions — 版本历史

```sql
CREATE TABLE document_versions (
    id          BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version     INT NOT NULL,
    content     TEXT NOT NULL,
    change_note VARCHAR(256),
    created_by  BIGINT REFERENCES users(id),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, version)
);
```

#### 3.2.8 generation_tasks — 生成任务

```sql
CREATE TABLE generation_tasks (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES users(id),
    document_id BIGINT REFERENCES documents(id),
    status      VARCHAR(16) DEFAULT 'pending', -- pending/retrieving/generating/formatting/done/failed
    params      JSONB NOT NULL,               -- 输入参数
    result      JSONB,                        -- 生成结果摘要
    retrieval_log JSONB,                      -- RAG检索记录（引用了哪些块）
    error       TEXT,
    started_at  TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_task_user ON generation_tasks(user_id);
CREATE INDEX idx_task_status ON generation_tasks(status);
```

#### 3.2.9 llm_configs — LLM 配置表

```sql
CREATE TABLE llm_configs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id),
    name            VARCHAR(64) NOT NULL,         -- 配置名称
    provider        VARCHAR(32) NOT NULL,         -- deepseek / qwen / zhipu / openai / custom
    api_base        VARCHAR(256) NOT NULL,         -- API 基础地址
    api_key_encrypted BYTEA,                      -- AES加密存储的 Key
    model           VARCHAR(64) NOT NULL,         -- 模型名：deepseek-chat / qwen-plus...
    embedding_model VARCHAR(64),                  -- Embedding 模型名
    max_tokens      INT DEFAULT 4096,
    temperature     REAL DEFAULT 0.7,
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- API Key 加密存储：AES-256-GCM，密钥从环境变量读取
-- 每个用户可配置多个 LLM，但同一时间只有一个 is_active
```

---

## 4. 核心流程设计

### 4.1 文档生成全流程

```
用户在前端填写请示表单
    │
    │  POST /api/v1/documents/generate
    │  { doc_type, title, key_elements, kb_ids, template_id }
    │
    ▼
┌─────────────────────────────────────────────┐
│ Step 1: 创建生成任务 (FastAPI)                │
│  - 写入 generation_tasks (status=pending)     │
│  - 推送到 Celery 队列                         │
│  - 返回 task_id，前端轮询 / WebSocket 推送    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 2: 意图解析 (LLM #1, Celery)            │
│  输入：用户填写的表单内容                      │
│  输出：{                                       │
│    doc_category: "人事请示",                   │
│    key_entities: {                            │
│      事由: "...",                              │
│      涉及对象: "...",                           │
│      金额: "..."                               │
│    },                                          │
│    required_sections: [                        │
│      "事由", "依据", "请示事项",                 │
│      "附件清单"                                  │
│    ]                                            │
│  }                                             │
│  Prompt: 请示意图分析专用模板                   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 3: RAG 检索 (Celery)                     │
│  3a. 从公司级知识库检索相关管理办法条款          │
│      - 语义检索：top_k=10 chunks              │
│      - 全文检索：关键词精确匹配 top_k=10        │
│      - 混合排序去重 → top_k=15                 │
│                                               │
│  3b. 从个人知识库检索相似历史请示                │
│      - 语义检索：top_k=5 chunks               │
│      - 混合排序 → top_k=5                      │
│                                               │
│  3c. 检索日志写入 retrieval_log                 │
│      [{chunk_id, source, score, content}]      │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 4: 大纲生成 (LLM #2, Celery)             │
│  输入：意图解析结果 + 检索到的参考片段          │
│  输出：结构化大纲                               │
│  {                                             │
│    sections: [                                 │
│      { title: "关于...的请示", type: "title" },│
│      { title: "一、请示事由", type: "body" },   │
│      { title: "二、政策依据", type: "body" },  │
│        refs: [chunk_id_3, chunk_id_7],         │
│      { title: "三、请示事项", type: "body" },  │
│      { title: "附件：...", type: "attachment"} │
│    ]                                            │
│  }                                              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 5: 分段生成 (LLM #3, 逐段调用, Celery)  │
│  对每个 section：                               │
│  - 组装 Prompt（该段标题 + 参考片段 +          │
│    公文写作要求）                               │
│  - 调用 LLM 生成段落内容                        │
│  - 每段标注引用来源                             │
│  - 通过 WebSocket 推送进度                     │
│    { section_idx, content, progress: 60% }    │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 6: 引用校验 (Celery, 规则校验)            │
│  - 检查生成内容中引用的条款号/文件名             │
│    是否真实存在于检索结果中                      │
│  - 标记可疑引用（LLM编造的引用）                 │
│  - 可选：再调一次 LLM 做事实核查                │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 7: Word 排版 (Celery)                   │
│  7a. 如果用户选择了模板：                       │
│      - 加载用户上传的 .docx 模板              │
│      - 替换 {{占位符}} 为生成内容               │
│      - 保留模板的样式/字体/页眉页脚             │
│      - 用 python-docx 操作                     │
│                                               │
│  7b. 如果没有模板：使用内置默认公文模板          │
│      - 页面：A4，上37mm 下35mm 左28mm 右26mm    │
│      - 发文机关标志：方正小标宋_GBK 2号(22pt)   │
│      - 标题：方正小标宋_GBK 2号(22pt) 居中      │
│      - 主送机关：方正仿宋_GBK 3号(16pt) 顶格    │
│      - 正文：方正仿宋_GBK 3号(16pt) 首行缩进   │
│      - 一级标题(一、)：方正黑体_GBK 3号         │
│      - 二级标题(（一）)：方正楷体_GBK 3号       │
│      - 三/四级标题(1./(1))：方正仿宋_GBK 3号   │
│      - 行距：固定值 30 磅                      │
│      - 段前段后：0 行                         │
│      - 附件说明：方正仿宋_GBK 3号 左空二字      │
│      - 署名/日期：方正仿宋_GBK 3号              │
│      - 附注(联系人/电话)：方正仿宋_GBK 3号      │
│        居左空2字加圆括号                       │
│      - 抄送机关：方正仿宋_GBK 4号(14pt)         │
│      - 页码：4号半角宋体阿拉伯数字              │
│      - 签发人(上行文)：签发人3字方正仿宋_GBK    │
│        姓名方正楷体_GBK 3号                    │
│                                               │
│  7c. 生成 .docx 文件，存到文件存储              │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ Step 8: 完成                                   │
│  - 更新 generation_tasks status=done          │
│  - 创建 documents 记录                         │
│  - 创建 document_versions v1                  │
│  - WebSocket 推送完成通知                       │
│  - 返回 document_id + 预览链接                 │
└─────────────────────────────────────────────┘
```

### 4.2 文件上传与解析流程

```
用户上传文件 (PDF / DOCX)
    │
    │  POST /api/v1/knowledge-bases/{kb_id}/documents
    │  multipart/form-data
    │
    ▼
┌────────────────────────────────────────┐
│ 1. 保存文件到 /data/uploads/{user_id}/ │
│    {kb_id}/{uuid}.{ext}               │
│                                       │
│ 2. 创建 kb_documents 记录              │
│    status=pending                      │
│                                       │
│ 3. 推送解析任务到 Celery               │
│    返回 document_id                   │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌────────────────────────────────────────┐
│ Celery: 文档解析                        │
│                                        │
│ 4a. PDF → 文本                          │
│     - pdfplumber 逐页提取               │
│     - 保留表格结构（转 markdown 表格）   │
│     - 保留页码信息                      │
│                                        │
│ 4b. DOCX → 文本                        │
│     - python-docx 读取段落+表格        │
│     - 保留标题层级                     │
│                                        │
│ 5. 文本清洗                             │
│     - 去除多余空白                      │
│     - 修复换行                         │
│     - 存入 kb_documents.content         │
│                                        │
│ 6. 文档分块 (Chunking)                  │
│     - 策略：按章节/段落语义分块         │
│     - 块大小：300-500字                │
│     - 重叠：50字                        │
│     - 保留章节标题作为块 meta           │
│                                        │
│ 7. Embedding 生成                       │
│     - 调用用户配置的 Embedding API     │
│     - 批量请求（每批20个块）            │
│     - 写入 kb_chunks.embedding          │
│                                        │
│ 8. 全文索引                              │
│     - 生成 tsvector (中文分词)          │
│     - 写入 kb_chunks.search_tsv        │
│                                        │
│ 9. 更新状态 status=indexed              │
│    chunk_count = N                     │
└────────────────────────────────────────┘
```

### 4.3 混合检索流程

```sql
-- 语义检索
SELECT 
    c.id, c.content, c.document_id, d.title,
    c.embedding <=> $1 AS distance       -- 余弦距离
FROM kb_chunks c
JOIN kb_documents d ON c.document_id = d.id
WHERE c.user_id = $2                       -- 权限隔离
  AND (
    c.kb_id = ANY($3::bigint[])           -- 指定知识库
    OR EXISTS(                            -- 或公司级知识库
      SELECT 1 FROM knowledge_bases kb 
      WHERE kb.id = c.kb_id 
      AND kb.level = 'company'
    )
  )
ORDER BY c.embedding <=> $1
LIMIT 10;

-- 全文检索
SELECT 
    c.id, c.content, c.document_id, d.title,
    ts_rank(c.search_tsv, plainto_tsquery('chinese_zh', $1)) AS rank
FROM kb_chunks c
JOIN kb_documents d ON c.document_id = d.id
WHERE c.user_id = $2
  AND c.search_tsv @@ plainto_tsquery('chinese_zh', $1)
  AND (c.kb_id = ANY($3) OR ...)
ORDER BY rank DESC
LIMIT 10;

-- 混合排序（应用层合并）
-- score = 0.4 * normalize(fts_rank) + 0.6 * (1 - distance)
-- 去重（同一文档多个块取最高分）后取 top_k
```

### 4.4 Word 模板占位符方案

基于实际公文格式标准（见附录 A），默认模板和用户自定义模板统一使用以下占位符体系：

#### 4.4.1 占位符定义

```
公文模板结构（对应实际格式标准）：

┌──────────────────────────────────────────────────────┐
│  {{发文机关}}                              ← 方正小标宋_GBK 2号(55pt)   │  红头
│  〔 {{发文字号年}} 〕{{发文字号序}} 号      ← 方正仿宋_GBK 3号           │  发文字号
│                          签发人：{{签发人}}  ← 方正仿宋_GBK 3号(签发人)  │  签发人(上行文)
│                                                        │
│  {{标题}}                                  ← 方正小标宋_GBK 2号 居中    │  标题(梯形/菱形)
│                                                        │
│  {{主送机关}}：                            ← 方正仿宋_GBK 3号 顶格      │  主送机关
│                                                        │
│  {{引言段落}}                              ← 方正仿宋_GBK 3号 首行缩进  │  引言
│  按照...现将...有关事项请示如下。                        │
│                                                        │
│  一、{{章节1标题}}                         ← 方正黑体_GBK 3号           │  一级标题
│  {{章节1内容}}                             ← 方正仿宋_GBK 3号           │  正文
│  （一）{{章节1_1标题}}                      ← 方正楷体_GBK 3号           │  二级标题
│  {{章节1_1内容}}                           ← 方正仿宋_GBK 3号           │
│  1.{{章节1_1_1标题}}                       ← 方正仿宋_GBK 3号           │  三级标题
│  {{章节1_1_1内容}}                         ← 方正仿宋_GBK 3号           │
│                                                        │
│  ... (更多章节按需生成)                                 │
│                                                        │
│  妥否，请示。                              ← 方正仿宋_GBK 3号           │  结尾语
│                                                        │
│  附件：{{附件列表}}                        ← 方正仿宋_GBK 3号 左空二字  │  附件说明
│                                                        │
│                              {{发文机关署名}}           │  署名
│                              {{成文日期}}               │  成文日期
│  （联系人：{{联系人}}；联系电话：{{联系电话}}）         │  附注(左空2字圆括号)
│                                                        │
│  ──────────────────────────────────────────────       │
│  抄送：{{抄送机关}}                        ← 方正仿宋_GBK 4号           │  抄送
│  {{印发机关}}                          年 月 日印发   ← 方正仿宋_GBK 4号           │  印发
│  ──────────────────────────────────────────────       │
│                              {{页码}}       ← 4号半角宋体              │  页码
└──────────────────────────────────────────────────────┘
```

#### 4.4.2 占位符分类

| 分类 | 占位符 | 类型 | 说明 |
|------|--------|------|------|
| 元数据 | `{{发文机关}}` `{{发文字号年}}` `{{发文字号序}}` `{{签发人}}` | 单值 | 用户在表单中填写 |
| 标题 | `{{标题}}` `{{主送机关}}` | 单值 | 用户填写或LLM生成 |
| 正文-引言 | `{{引言段落}}` | 多段落 | LLM 生成，可能含多个段落 |
| 正文-章节 | `{{章节N标题}}` `{{章节N内容}}` | 多段落 | N=1,2,3...，LLM 大纲决定章节数 |
| 正文-子章节 | `{{章节N_M标题}}` `{{章节N_M内容}}` | 多段落 | 二级/三级标题，按需 |
| 结尾 | `{{附件列表}}` `{{发文机关署名}}` `{{成文日期}}` | 单值/多行 | 附件为多行列表 |
| 附注 | `{{联系人}}` `{{联系电话}}` | 单值 | 请示必须包含 |
| 抄送 | `{{抄送机关}}` `{{印发机关}}` | 单值 | 可选 |

#### 4.4.3 python-docx 实现方案

```python
# services/word/template_renderer.py

import re
from copy import deepcopy
from docx import Document
from docx.shared import Pt, Cm, Emu
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

class TemplateRenderer:
    """Word 模板渲染器"""
    
    # 占位符正则
    PLACEHOLDER_RE = re.compile(r'\{\{(\w+)\}\}')
    
    # 公文字体常量（来自实际标准文件）
    FONT_TITLE = '方正小标宋_GBK'          # 标题用
    FONT_BODY = '方正仿宋_GBK'              # 正文用
    FONT_H1 = '方正黑体_GBK'               # 一级标题
    FONT_H2 = '方正楷体_GBK'               # 二级标题
    FONT_COPY = '方正仿宋_GBK'             # 抄送用(4号)
    
    SIZE_TITLE = Pt(22)     # 2号 = 22pt
    SIZE_BODY = Pt(16)      # 3号 = 16pt
    SIZE_COPY = Pt(14)      # 4号 = 14pt
    LINE_SPACING = Pt(30)   # 固定值30磅
    
    def __init__(self, template_path: str):
        self.doc = Document(template_path)
    
    def render(self, data: dict, output_path: str):
        """渲染模板，替换占位符"""
        for paragraph in self.doc.paragraphs:
            self._render_paragraph(paragraph, data)
        
        for table in self.doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for paragraph in cell.paragraphs:
                        self._render_paragraph(paragraph, data)
        
        self.doc.save(output_path)
    
    def _render_paragraph(self, paragraph, data: dict):
        """渲染单个段落"""
        text = paragraph.text
        matches = self.PLACEHOLDER_RE.findall(text)
        if not matches:
            return
        
        for key in matches:
            value = data.get(key, '')
            if isinstance(value, list):
                # 多段落内容：在当前段落位置插入新段落
                self._insert_multi_paragraph(paragraph, value, key)
            else:
                # 单值替换：保留原有 run 样式
                self._replace_in_runs(paragraph, key, str(value))
    
    def _replace_in_runs(self, paragraph, key: str, value: str):
        """在 run 层级做替换，保留字体/字号/加粗等样式"""
        full_text = paragraph.text
        new_text = full_text.replace(f'{{{{{key}}}}}', value)
        
        # 保存第一个 run 的样式
        if paragraph.runs:
            ref_run = paragraph.runs[0]
            ref_font_name = ref_run.font.name
            ref_font_size = ref_run.font.size
            ref_bold = ref_run.font.bold
            # eastAsia 字体
            ref_ea = self._get_east_asian_font(ref_run)
        
        # 清空所有 run
        for run in paragraph.runs:
            run.text = ''
        
        # 在第一个 run 写入新文本
        if paragraph.runs:
            run = paragraph.runs[0]
        else:
            run = paragraph.add_run()
        
        run.text = new_text
        if ref_font_name:
            run.font.name = ref_font_name
        if ref_font_size:
            run.font.size = ref_font_size
        run.font.bold = ref_bold
        if ref_ea:
            self._set_east_asian_font(run, ref_ea)
    
    def _insert_multi_paragraph(self, ref_paragraph, lines: list, key: str):
        """多段落占位符：在引用段落后插入新段落，继承样式"""
        parent = ref_paragraph._element.getparent()
        idx = list(parent).index(ref_paragraph._element)
        
        # 替换占位符为第一段
        if lines:
            self._replace_in_runs(ref_paragraph, key, lines[0])
        
        # 后续段落插入
        for i, line in enumerate(lines[1:], 1):
            new_p = deepcopy(ref_paragraph._element)
            parent.insert(idx + i, new_p)
            # 设置新段落文本
            from docx.text.paragraph import Paragraph
            new_para = Paragraph(new_p, ref_paragraph._parent)
            new_para.text = line  # 会创建新 run
    
    def _get_east_asian_font(self, run):
        """获取 run 的东亚字体名"""
        rpr = run._element.find(qn('w:rPr'))
        if rpr is not None:
            rfonts = rpr.find(qn('w:rFonts'))
            if rfonts is not None:
                return rfonts.get(qn('w:eastAsia'))
        return None
    
    def _set_east_asian_font(self, run, font_name: str):
        """设置 run 的东亚字体"""
        rpr = run._element.find(qn('w:rPr'))
        if rpr is None:
            rpr = run._element.makeelement(qn('w:rPr'), {})
            run._element.insert(0, rpr)
        rfonts = rpr.find(qn('w:rFonts'))
        if rfonts is None:
            rfonts = rpr.makeelement(qn('w:rFonts'), {})
            rpr.append(rfonts)
        rfonts.set(qn('w:eastAsia'), font_name)
```

#### 4.4.4 默认公文模板生成方案

当用户未上传模板时，系统用 python-docx 从零生成符合标准的公文：

```python
def create_default_template(output_path: str):
    """生成符合集团公文标准的默认模板"""
    doc = Document()
    
    # 页面设置：A4，上37mm 下35mm 左28mm 右26mm
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(3.7)
    section.bottom_margin = Cm(3.5)
    section.left_margin = Cm(2.8)
    section.right_margin = Cm(2.6)
    
    # 发文机关标志（红头）— 方正小标宋_GBK 2号(22pt) 居中
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('{{发文机关}}')
    run.font.size = Pt(22)
    _set_font(run, '方正小标宋_GBK')
    
    # 发文字号 — 方正仿宋_GBK 3号
    p = doc.add_paragraph()
    run = p.add_run('〔 {{发文字号年}} 〕{{发文字号序}} 号        签发人：{{签发人}}')
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    
    # 标题 — 方正小标宋_GBK 2号 居中
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('{{标题}}')
    run.font.size = Pt(22)
    _set_font(run, '方正小标宋_GBK')
    
    # 主送机关 — 方正仿宋_GBK 3号 顶格
    p = doc.add_paragraph()
    run = p.add_run('{{主送机关}}：')
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    
    # 引言
    p = _add_body_paragraph(doc, '{{引言段落}}')
    
    # 一级标题 — 方正黑体_GBK 3号
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.85)  # 首行缩进2字符(3号字≈0.85cm)
    p.paragraph_format.line_spacing = Pt(30)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    run = p.add_run('一、{{章节1标题}}')
    run.font.size = Pt(16)
    _set_font(run, '方正黑体_GBK')
    
    # 正文 — 方正仿宋_GBK 3号
    _add_body_paragraph(doc, '{{章节1内容}}')
    
    # 结尾语
    _add_body_paragraph(doc, '妥否，请示。')
    
    # 附件说明
    _add_body_paragraph(doc, '附件：{{附件列表}}')
    
    # 署名 + 日期（右对齐）
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run('{{发文机关署名}}')
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = p.add_run('{{成文日期}}')
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    
    # 附注（联系人/电话）— 左空2字 圆括号
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.85)
    p.paragraph_format.line_spacing = Pt(30)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    run = p.add_run('（联系人：{{联系人}}；联系电话：{{联系电话}}）')
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    
    doc.save(output_path)


def _add_body_paragraph(doc, text):
    """添加正文段落：方正仿宋_GBK 3号 首行缩进 行距30磅"""
    from docx.enum.text import WD_LINE_SPACING
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0.85)
    p.paragraph_format.line_spacing = Pt(30)
    p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(text)
    run.font.size = Pt(16)
    _set_font(run, '方正仿宋_GBK')
    return p


def _set_font(run, font_name: str):
    """设置 run 的西文+东亚字体"""
    run.font.name = font_name  # 西文
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        rpr = run._element.makeelement(qn('w:rPr'), {})
        run._element.insert(0, rpr)
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = rpr.makeelement(qn('w:rFonts'), {})
        rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), font_name)
    rfonts.set(qn('w:ascii'), font_name)
    rfonts.set(qn('w:hAnsi'), font_name)
```

#### 4.4.5 采购请示专项模板

基于实际采购请示模板（附录 B），系统内置一个采购请示专用模板，支持场景化生成：

```
采购请示模板结构（来自实际文件）：

{{发文机关}}
〔 {{发文字号年}} 〕{{发文字号序}} 号        签发人：{{签发人}}

{{标题}}（如：XXX部门报请审议采购XXX的请示）

{{主送机关}}：

{{引言段落}}（简要说明采购事项动因，包括任务来源、采购原因、建议）

具体内容如下：

一、{{采购背景标题}}                        ← 方正黑体_GBK 3号
{{采购背景内容}}                            ← 含场景1-5之一对应的内容

二、{{采购流程及制度依据标题}}                ← 方正黑体_GBK 3号
{{采购流程及制度依据内容}}                    ← 含制度引用 + 预算档位判断

三、{{市场摸底调查标题}}                     ← 方正黑体_GBK 3号
{{市场摸底调查内容}}                         ← 直接委托/其他采购流程

四、{{请示事项标题}}                         ← 方正黑体_GBK 3号
（一）{{供应商采购方式标题}}
{{供应商采购方式内容}}
（二）{{采购金额及结算方式标题}}
{{采购金额及结算方式内容}}

妥否，请示！

附件：
{{附件列表}}

                    {{发文机关署名}}
                    {{成文日期}}

（联系人：{{联系人}}；联系电话：{{联系电话}}）
```

**采购场景识别**：LLM 在意图分析阶段，根据用户输入自动判断属于以下哪种采购场景，并选择对应的写作模板片段：

| 场景 | 判断特征 | 正文片段来源 |
|------|----------|-------------|
| 场景1 | 特定项目执行所需 | "我部于XX年承接XXX项目..." |
| 场景2 | 完成某一类型项目所需的服务/货物 | "XX类项目为我部主要业务板块之一..." |
| 场景3 | 多部门联合采购 | "XX是我司重要的业务产品..." |
| 场景4 | 行政后勤、管理所需 | "因XX原因，导致XX结果..." |
| 场景5 | 甲方/上级指定供应商 | "我部承接XX单位的XX项目..." |

**采购流程自动判断**：根据预算金额自动匹配制度条款：

| 预算范围 | 采购方式 | 制度依据 |
|----------|---------|---------|
| < 30万元 | 直接委托 | 《生产经营项目招标采购管理实施细则》第五条第四点第一项 |
| 30万-50万元 | 询价 | 第五条第三点 |
| 50万-200万元 | 公开采购 | 第五条第二点 |
| ≥ 200万元 | 公开招标 | 第五条第一点 |

---

## 5. API 接口设计

### 5.1 接口清单

```
基础路径：/api/v1

认证
  POST   /auth/register                 注册
  POST   /auth/login                     登录 → JWT
  POST   /auth/refresh                   刷新 Token
  GET    /auth/me                        当前用户信息

LLM 配置
  GET    /llm-configs                    列出配置
  POST   /llm-configs                    创建配置
  PUT    /llm-configs/{id}               更新配置
  DELETE /llm-configs/{id}              删除配置
  POST   /llm-configs/{id}/activate      激活配置
  POST   /llm-configs/{id}/test          测试连通性
  GET    /llm-configs/{id}/models        获取可用模型列表

知识库
  GET    /knowledge-bases                列出（含公司级）
  POST   /knowledge-bases                创建
  PUT    /knowledge-bases/{id}           更新
  DELETE /knowledge-bases/{id}           删除

知识文档
  POST   /knowledge-bases/{kb_id}/documents    上传文档
  GET    /knowledge-bases/{kb_id}/documents    列出文档
  DELETE /knowledge-documents/{id}              删除文档
  POST   /knowledge-documents/{id}/reparse      重新解析
  GET    /knowledge-documents/{id}/status       解析状态

Word 模板
  POST   /templates                       上传模板
  GET    /templates                        列出模板
  GET    /templates/{id}/placeholders      获取占位符列表
  DELETE /templates/{id}                   删除模板
  GET    /templates/{id}/preview           预览模板

请示材料
  POST   /documents/generate              触发生成（异步）
  GET    /documents                        列出
  GET    /documents/{id}                  获取详情
  PUT    /documents/{id}                  更新内容
  GET    /documents/{id}/versions         版本列表
  POST   /documents/{id}/export           导出 Word/PDF
  GET    /documents/{id}/export/{fmt}     下载文件

生成任务
  GET    /tasks/{id}                      任务状态
  GET    /tasks/{id}/retrieval-log         检索日志
  WebSocket /ws/tasks/{id}                实时进度推送

检索
  POST   /search                           混合检索
  GET    /search/suggest                   搜索建议
```

### 5.2 关键接口示例

**生成交示材料：**

```json
POST /api/v1/documents/generate
Authorization: Bearer {jwt}

{
  "title": "关于申请采购办公设备的请示",
  "doc_type": "采购类",
  "key_elements": {
    "事由": "因业务扩展需要采购办公电脑20台",
    "预算金额": "150000元",
    "资金来源": "办公经费",
    "涉及对象": "信息部",
    "依据": "公司固定资产管理办法"
  },
  "kb_ids": [1, 3],              // 引用的知识库
  "template_id": 5,              // 使用的 Word 模板
  "llm_config_id": 2             // 使用的 LLM 配置
}

Response: 202 Accepted
{
  "task_id": 42,
  "status": "pending",
  "estimated_time": "30-60s",
  "ws_url": "/ws/tasks/42"
}
```

**WebSocket 进度推送：**

```json
// 服务端推送
{ "type": "progress", "step": "intent_parsing", "progress": 10, "message": "正在分析请示意图..." }
{ "type": "progress", "step": "rag_retrieval", "progress": 25, "message": "正在检索相关管理办法..." }
{ "type": "progress", "step": "rag_retrieval", "progress": 35, "message": "正在检索相似历史案例..." }
{ "type": "progress", "step": "outline", "progress": 45, "message": "正在生成大纲..." }
{ "type": "progress", "step": "generating", "progress": 60, "section": "事由", "content": "..." }
{ "type": "progress", "step": "generating", "progress": 75, "section": "依据", "content": "..." }
{ "type": "progress", "step": "formatting", "progress": 90, "message": "正在排版..." }
{ "type": "done", "progress": 100, "document_id": 88, "preview_url": "/api/v1/documents/88" }
```

---

## 6. 安全设计

### 6.1 认证与授权

```
认证流程：
  用户登录 → JWT (access_token 30min + refresh_token 7d)
  access_token 存 httpOnly cookie 或 Authorization header
  refresh_token 存 httpOnly cookie

权限矩阵：
  ┌──────────┬─────────────┬──────────────┬──────────────┐
  │          │ 公司级知识库 │ 个人级知识库  │ 请示材料      │
  ├──────────┼─────────────┼──────────────┼──────────────┤
  │ admin    │ 读写删       │ 读写删(自己的)│ 读写删(自己的)│
  │ user     │ 只读         │ 读写删(自己的)│ 读写删(自己的)│
  └──────────┴─────────────┴──────────────┴──────────────┘
```

### 6.2 API Key 安全

```
LLM API Key 存储与使用：
  1. 用户通过前端配置 API Key
  2. 后端用 AES-256-GCM 加密后存入 llm_configs.api_key_encrypted
  3. 加密密钥从环境变量 LLM_KEY_ENCRYPTION_SECRET 读取（不入库）
  4. 仅在调用 LLM 时临时解密，解密后的值不落日志、不进缓存
  5. API 响应中永远不返回 Key 明文
```

### 6.3 文件安全

```
上传限制：
  - 格式白名单：.pdf, .docx
  - 单文件大小限制：50MB
  - 单用户存储上限：可配置，默认 500MB
  - 文件名清洗：去除路径穿越字符
  - 存储路径：/data/uploads/{user_id}/{uuid}.{ext}（不暴露原文件名）

访问控制：
  - 文件下载接口校验 user_id 所有权
  - 公司级知识库文档：所有登录用户可下载
  - 静态文件目录禁止直接访问，全部走 API
```

---

## 7. 部署方案

### 7.1 目录结构

```
/opt/claw/                          # 应用根目录
├── docker-compose.yml
├── .env                            # 环境变量（密钥等）
├── app/
│   ├── backend/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── api/                    # 路由层
│   │   ├── core/                   # 核心逻辑（认证、配置）
│   │   ├── services/               # 业务服务层
│   │   │   ├── generation/         # 文档生成引擎
│   │   │   ├── retrieval/          # RAG 检索
│   │   │   ├── parsing/            # 文件解析
│   │   │   └── word/               # Word 排版
│   │   ├── models/                 # 数据模型 (SQLAlchemy)
│   │   ├── tasks/                   # Celery 任务定义
│   │   ├── prompts/                 # LLM Prompt 模板
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── views/
│   │   │   ├── components/
│   │   │   ├── stores/             # Pinia
│   │   │   └── api/                # Axios 封装
│   │   ├── package.json
│   │   └── vite.config.ts
│   └── nginx/
│       └── claw.conf               # Nginx 配置
├── data/                           # 持久化数据
│   ├── pgdata/                     # PostgreSQL 数据
│   ├── redis/                      # Redis 持久化
│   ├── uploads/                    # 用户上传文件
│   │   └── {user_id}/
│   └── exports/                    # 生成的 Word/PDF
└── logs/                           # 日志
    ├── backend/
    ├── celery/
    └── nginx/
```

### 7.2 docker-compose.yml

```yaml
version: "3.9"

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: claw-pg
    restart: always
    environment:
      POSTGRES_DB: claw
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - ./data/pgdata:/var/lib/postgresql/data
    # 不映射端口到宿主机，仅容器间访问
    networks:
      - claw-net
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1.5G

  redis:
    image: redis:7-alpine
    container_name: claw-redis
    restart: always
    command: redis-server --maxmemory 200mb --maxmemory-policy allkeys-lru
    volumes:
      - ./data/redis:/data
    networks:
      - claw-net
    deploy:
      resources:
        limits:
          cpus: "0.3"
          memory: 256M

  backend:
    build: ./app/backend
    container_name: claw-api
    restart: always
    command: >
      uvicorn main:app
      --host 0.0.0.0
      --port 8000
      --workers 2
      --loop uvloop
      --limit-concurrency 50
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/claw
      - REDIS_URL=redis://redis:6379/0
      - LLM_KEY_ENCRYPTION_SECRET=${LLM_KEY_ENCRYPTION_SECRET}
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ./data/uploads:/app/uploads
      - ./data/exports:/app/exports
      - ./logs/backend:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - claw-net
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 800M

  celery-worker:
    build: ./app/backend
    container_name: claw-worker
    restart: always
    command: celery -A tasks.celery_app worker --loglevel=info --concurrency=2 --max-memory-per-child=1000000
    environment:
      - DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@postgres:5432/claw
      - REDIS_URL=redis://redis:6379/0
      - LLM_KEY_ENCRYPTION_SECRET=${LLM_KEY_ENCRYPTION_SECRET}
      - JWT_SECRET=${JWT_SECRET}
    volumes:
      - ./data/uploads:/app/uploads
      - ./data/exports:/app/exports
      - ./logs/celery:/app/logs
    depends_on:
      - postgres
      - redis
    networks:
      - claw-net
    deploy:
      resources:
        limits:
          cpus: "1.0"
          memory: 1.2G

  nginx:
    image: nginx:1.24-alpine
    container_name: claw-nginx
    restart: always
    ports:
      - "80:80"
      # 后续用户自行配置 HTTPS 时开放 443
    volumes:
      - ./app/nginx/claw.conf:/etc/nginx/conf.d/default.conf
      - ./app/frontend/dist:/usr/share/nginx/html      # 前端构建产物
      - ./data/uploads:/usr/share/nginx/uploads:ro     # 静态文件（受限访问）
    depends_on:
      - backend
    networks:
      - claw-net
    deploy:
      resources:
        limits:
          cpus: "0.2"
          memory: 100M

networks:
  claw-net:
    driver: bridge
```

### 7.3 Nginx 配置

```nginx
server {
    listen 80;
    server_name _;
    # 后续用户自行配置 HTTPS

    # 前端 SPA
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API 反代
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;       # LLM 调用可能较慢
    }

    # WebSocket
    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600s;
    }

    # 上传文件大小限制
    client_max_body_size 50M;
}
```

### 7.4 PostgreSQL 关键配置

```ini
# postgresql.conf (4核8G 优化)
shared_buffers = 512MB
work_mem = 16MB
maintenance_work_mem = 256MB        # 向量索引构建需要
effective_cache_size = 2GB
max_connections = 30
random_page_cost = 1.1              # SSD
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# zhparser 扩展
shared_preload_libraries = 'zhparser'
```

---

## 8. LLM 配置与调用设计

### 8.1 多 Provider 抽象

```python
# services/llm/provider.py

from abc import ABC, abstractmethod
from typing import AsyncGenerator

class LLMProvider(ABC):
    """LLM 提供商抽象接口"""
    
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """同步对话"""
        pass
    
    @abstractmethod
    async def chat_stream(self, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        """流式对话"""
        pass
    
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """生成 Embedding"""
        pass

# 各 Provider 实现
class DeepSeekProvider(LLMProvider): ...   # DeepSeek API
class QwenProvider(LLMProvider): ...       # 通义千问 API
class ZhipuProvider(LLMProvider): ...      # 智谱 API
class OpenAICompatibleProvider(LLMProvider): ...  # 通用 OpenAI 兼容接口

# 工厂
def get_provider(config: LLMConfig) -> LLMProvider:
    providers = {
        "deepseek": DeepSeekProvider,
        "qwen": QwenProvider,
        "zhipu": ZhipuProvider,
        "custom": OpenAICompatibleProvider,
    }
    cls = providers.get(config.provider, OpenAICompatibleProvider)
    return cls(api_base=config.api_base, api_key=decrypt(config.api_key), model=config.model)
```

### 8.2 Prompt 模板管理

```
prompts/
├── intent_analysis.txt         # 意图分析
├── outline_generation.txt     # 大纲生成
├── section_generation/        # 分段生成
│   ├── _base.txt              # 基础模板
│   ├── 事由.txt
│   ├── 依据.txt
│   ├── 请示事项.txt
│   └── 附件.txt
├── citation_check.txt         # 引用校验
└── system_prompt.txt          # 系统提示词
```

**意图分析 Prompt 示例（含采购场景识别）：**

```
你是一个国企公文写作专家。请分析以下请示请求，提取关键信息。

用户输入：
{user_input}

请示类型：{doc_type}
关键要素：{key_elements}

请输出 JSON：
{
  "doc_category": "请示的具体类别",
  "key_entities": {
    "事由": "...",
    "涉及对象": "...",
    "金额": "...",
    "资金来源": "...",
    "预算金额": "..."          // 采购类必填
  },
  "required_sections": ["事由", "依据", "请示事项", "附件清单"],
  "priority_refs": ["需要引用的关键制度/办法名称"],

  // 采购类请示专用字段
  "procurement_scenario": 1,   // 1-5 对应采购场景（见下文）
  "budget_tier": "direct",     // direct(<30万)/inquiry(30-50万)/public(50-200万)/tender(≥200万)
  "procurement_method": "直接委托"  // 采购方式
}

采购场景说明（仅采购类请示填写）：
  场景1：完成生产经营目标，即特定项目执行所需
  场景2：生产经营要素组织，即完成某一类型项目所需的服务或货物
  场景3：多部门联合采购服务或货物（金额最大的部门牵头）
  场景4：采购行政后勤、管理所需的服务或货物
  场景5：项目甲方或上级单位指定供应商

注意：
1. 只输出 JSON，不要其他内容
2. required_sections 根据请示类型确定，通常包含：事由、依据、请示事项
3. priority_refs 是用户明确提到或根据类型应当引用的制度名称
4. 采购类请示必须判断 procurement_scenario 和 budget_tier
5. budget_tier 根据"预算金额"字段数值自动判断
```

---

## 9. 前端设计

### 9.1 页面结构

```
┌──────────────────────────────────────────────────────┐
│  顶部导航栏  [Logo] 请示材料生成系统    [用户] [设置]  │
├──────────┬───────────────────────────────────────────┤
│          │                                             │
│  侧边栏   │              主内容区                       │
│          │                                             │
│ 📝 生成   │  ┌─────────────────────────────────────┐  │
│   新建   │  │                                     │  │
│   草稿箱 │  │         根据路由切换的页面             │  │
│   历史   │  │                                     │  │
│          │  │  - 生成表单页                         │  │
│ 📚 知识库 │  │  - 生成进度页                         │  │
│   公司级 │  │  - 编辑预览页                         │  │
│   我的   │  │  - 知识库管理页                        │  │
│          │  │  - 检索页                             │  │
│ 🔍 检索   │  │  - 设置页                             │  │
│          │  │                                     │  │
│ ⚙ 设置   │  └─────────────────────────────────────┘  │
│   LLM配置│                                             │
│   模板   │                                             │
└──────────┴───────────────────────────────────────────┘
```

### 9.2 核心页面交互

**生成表单页：**

```
┌─────────────────────────────────────────────────────┐
│  新建请示材料                                         │
├─────────────────────────────────────────────────────┤
│                                                       │
│  请示类型*  [采购类 ▼]                                 │
│              （采购类 / 人事类 / 资金类 / 项目类 / ...） │
│                                                       │
│  标题*      [XXX部门报请审议采购XXX的请示       ]      │
│                                                       │
│  ── 采购场景（仅采购类显示）──                        │
│  采购场景   [场景1: 特定项目执行所需 ▼]                 │
│              （场景1-5，可自动识别或手动指定）           │
│                                                       │
│  关键要素（结构化输入）                                │
│  ┌──────────────────────────────────────────────┐    │
│  │ 事由*     [因业务扩展需要采购办公电脑20台...   ]│    │
│ │ 预算金额  [150000] 元  → 自动判定: 直接委托      ││    │
│ │ 资金来源  [办公经费                    ]        ││    │
│ │ 涉及对象  [信息部                      ]        ││    │
│ │ 依据制度  [生产经营项目招标采购管理实施细则  ]   ││    │
│ │ 起草部门  [信息部                      ]        ││    │
│ │ 起草人    [张三                        ]        ││    │
│ │ [+ 添加自定义要素]                             ││    │
│  └──────────────────────────────────────────────┘    │
│                                                       │
│  引用知识库  ☑ 公司管理办法库  ☑ 采购制度库            │
│              ☐ 我的请示案例库                          │
│                                                       │
│  Word 模板  [采购请示专用模板 ▼]  [上传新模板]         │
│              （采购请示模板 / 标准公文模板 / 自定义）   │
│                                                       │
│  LLM 配置   [DeepSeek-Chat ▼]                         │
│                                                       │
│  [预览 Prompt]                    [生成请示材料 →]     │
│                                                       │
└─────────────────────────────────────────────────────┘
```

**生成进度页（实时展示）：**

```
┌─────────────────────────────────────────────────────┐
│  生成中... 关于申请采购办公设备的请示                   │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ✅ 意图分析          已识别：采购类请示                │
│  ✅ 知识库检索        找到 15 条相关条款                 │
│  ✅ 大纲生成          5 个段落                         │
│  ⏳ 内容生成          3/5 段完成                       │
│  ⬜ 引用校验                                           │
│  ⬜ Word 排版                                          │
│                                                       │
│  ┌─── 实时内容预览 ───────────────────────────────┐   │
│  │                                                 │  │
│  │  关于申请采购办公设备的请示                      │  │
│  │                                                 │  │
│  │  公司领导：                                      │  │
│  │                                                 │  │
│  │  一、请示事由                                    │  │
│  │  因公司业务规模持续扩展，信息部现有办公           │  │
│  │  设备已无法满足日常工作需求...                   │  │
│  │  📎 引用：《公司固定资产管理办法》第三章第十二条   │  │
│  │                                                 │  │
│  │  二、政策依据 ▌                                  │  │
│  │  (正在生成...)                                   │  │
│  │                                                 │  │
│  └─────────────────────────────────────────────────┘  │
│                                                       │
│  [取消生成]                                           │
└─────────────────────────────────────────────────────┘
```

---

## 10. 实施路线

### Phase 1：基础框架（2-3 周）

- 项目脚手架（FastAPI + Vue3 + Docker Compose）
- 用户认证 + JWT
- 数据库初始化（DDL + 迁移脚本）
- LLM 配置管理 + 多 Provider 抽象
- 基础前端框架

### Phase 2：知识库（2-3 周）

- 文件上传（PDF/DOCX）
- 文档解析（pdfplumber + python-docx）
- 文档分块 + Embedding 入库
- pgvector + zhparser 配置
- 知识库管理界面
- 混合检索功能

### Phase 3：文档生成核心（3-4 周）

- Prompt 模板体系
- 意图分析 → 大纲 → 分段生成流程
- RAG 检索 + 引用标注
- WebSocket 实时进度推送
- 引用校验
- 生成进度页面

### Phase 4：Word 排版（2-3 周）

- python-docx 模板占位符替换
- 模板上传 + 占位符识别
- 默认公文模板
- 导出功能
- 在线编辑器（TinyMCE 集成）

### Phase 5：完善与优化（2 周）

- 版本管理
- 全文检索优化
- 使用统计
- 日志与监控
- 安全加固

---

## 10.5 UI 设计（7 个核心页面）

> 系统名称：公文辅助系统  
> 技术栈：Vue 3 + Element Plus  
> 设计风格：新中式，宣纸底 #FAF8F3 + 朱红印 #A63A2E + 衬线标题，克制圆角

### 页面清单

| 编号 | 页面 | 路由 | 核心功能 |
|------|------|------|---------|
| P1 | 新建请示 | /documents/new | 表单输入 → 配置 → 触发生成 |
| P2 | 生成进度 | /documents/:id/generate | 实时步骤追踪 + 内容预览（WebSocket） |
| P3 | 编辑器 | /documents/:id/edit | 富文本编辑 + 引用溯源 + 导出 |
| P4 | 检索中心 | /search | 双模式搜索 + 筛选器 + 结果溯源 |
| P5 | 知识库 | /knowledge | 公司级/个人级文档管理 |
| P6 | 设置 | /settings | LLM 配置管理 + 连通性测试 |
| P7 | 导出弹窗 | (Modal) | 模板选择 + 占位符映射 + 格式选项 |

### P1 新建请示

**布局**：顶栏 + 左侧表单区 + 右侧预览/配置区

- 顶栏：系统名称 + 面包屑「我的请示 > 新建」
- 表单核心字段：
  - 请示类型（下拉：采购类/人事类/资金类/项目类/制度类）
  - 采购场景（仅采购类显示：项目执行/要素组织/联合采购/行政后勤/甲方指定）
  - 标题（文本输入）
  - 关键要素（结构化：事由、金额、资金来源、涉及对象、依据，+ 自定义要素）
  - 预算金额（输入后自动判定采购方式：直接委托/询价/公开采购/招标，显示制度档位提示）
- 配置区：
  - 引用知识库（checkbox：公司管理办法库默认勾选、个人案例库可选）
  - Word 模板（下拉选择已有模板 / 上传新模板）
  - LLM 配置（下拉选择已激活的配置）
- 底部：「预览 Prompt」「生成请示材料 →」两个按钮

### P2 生成进度

**布局**：顶栏 + 左侧步骤追踪 + 右侧内容预览

- 左侧步骤追踪（6 步垂直流程）：
  1. 意图解析 → 2. RAG 检索 → 3. 大纲生成 → 4. 分段生成 → 5. 引用校验 → 6. Word 排版
  - 完成步骤：绿色勾选
  - 进行中步骤：紫色脉冲动画
  - 未开始步骤：灰色虚线
- 顶部进度条：实时百分比（WebSocket 推送）
- 右侧内容预览区：
  - 每段生成完立即渲染预览
  - 引用来源以蓝色标签内联标注，点击可展开原文
  - 正在生成的段落末尾有闪烁光标
- 底部：「取消生成」按钮（可中断，已生成内容保留）

### P3 编辑器

**布局**：顶栏 + 左侧编辑区 + 右侧引用溯源面板 + 底部状态栏

- 左侧编辑区（TinyMCE）：
  - 工具栏含公文字体快捷选择（方正仿宋 3 号、方正小标宋 2 号等）
  - 「引用」按钮：在光标处插入引用标注
  - 自动保存（每 30s）
- 右侧引用溯源面板：
  - 列出所有引用的制度条款和历史案例
  - 每条可展开查看原文片段
  - 底部引用统计 + 校验结果（绿色「校验通过」或红色「可疑引用」警告）
- 底部状态栏：自动保存时间 · 版本号 · 字数 · 预计页数
- 右上角操作：「导出 Word」「保存版本」

### P4 检索中心

**布局**：顶栏 + 左侧筛选面板 + 右侧搜索结果

- 搜索模式切换：「语义检索」「关键词检索」Tab 切换
  - 语义检索：输入自然语言描述，混合排序（0.6 × 语义 + 0.4 × 全文）返回 Top 10
  - 关键词检索：精确匹配，高亮关键词
- 左侧筛选面板：
  - 检索范围（checkbox）：公司管理办法库 / 公司制度文件 / 我的请示案例 / 全部用户请示
  - 文档类型（checkbox）：管理办法 / 请示材料 / 制度文件
  - 请示类型（checkbox）：采购类 / 人事类 / 资金类 / 项目类
  - 时间范围（下拉）：近 3 个月 / 近半年 / 近 1 年 / 全部
- 右侧结果列表：
  - 每条结果：类型标签（管理办法=蓝色/历史请示=绿色） + 标题 + 摘要（关键词高亮） + 元信息（来源、文号、日期）
  - 相关度百分比显示
  - 「查看原文」链接跳转或弹窗
  - 底部「加载更多」
- 顶栏也保留快捷搜索框（输入后回车直接跳转到检索中心页）

### P5 知识库管理

**布局**：顶栏 + Tab 切换（公司级/个人级）+ 文档列表 + 底部上传区

- Tab 切换：公司级（admin 可上传/管理，普通用户只读）/ 个人级（用户自己管理）
- 文档列表：
  - 每行：格式图标（PDF/DOCX） + 名称 + 类型标签 + 分块数 + 状态（已索引/解析中/失败）
  - 失败项有「重试」按钮
  - 支持删除（个人级可删自己的，公司级仅 admin 可删）
- 底部上传区：虚线边框拖拽区，支持点击或拖拽上传 Word/PDF
- 上传后自动触发解析 → 分块 → Embedding 入库，状态实时更新

### P6 设置 — LLM 配置

**布局**：顶栏 + LLM 配置列表 + 配置表单 + 测试面板

- LLM 配置列表：
  - 每条：名称 + Provider + 模型 + 激活状态
  - 同时只能激活一个，激活的紫色高亮边框
  - 支持编辑、删除、切换激活
- 配置表单：
  - 配置名称（文本）
  - Provider（下拉：deepseek / qwen / zhipu / custom）
  - 选 custom 时：API 地址可自定义
  - API Key（加密存储，默认掩码显示，有「显示」按钮临时查看）
  - 对话模型（文本，如 deepseek-chat）
  - Embedding 模型（文本，如 text-embedding-3-small）
- 测试面板：
  - 「测试连通性」按钮：发送测试请求到对话 API 和 Embedding API
  - 结果面板：绿色=成功（显示延迟、模型名称），红色=失败（错误信息）

### P7 导出 Word 弹窗（Modal）

**布局**：半透明遮罩 + 居中弹窗（680px 宽）

- 标题栏：「导出 Word 文档」 + 请示名称 + 关闭按钮
- 内容区（三部分）：

  **① 模板选择**（卡片式选择）：
  - 标准公文模板（系统内置：红头、仿宋_GB2312 3号、固定行距30磅）
  - 采购请示模板（含采购明细表格、签发人栏、附件清单）
  - 上传新模板（虚线卡片入口）
  - 选中模板蓝色高亮边框

  **② 占位符映射确认**（表格）：
  - 三列：模板占位符 / 映射内容 / 字数
  - 系统自动匹配生成内容到模板占位符
  - 未匹配项标注「手动填」（如文号、签发人）
  - 顶部绿色提示：所有占位符已自动匹配

  **③ 格式选项**（checkbox）：
  - ☑ 包含引用标注
  - ☑ 包含附件清单页
  - ☐ 同时导出 PDF 版本

- 底部统计面板：总字数 / 引用数 / 预计页数 / 引用校验结果
- 操作按钮：「取消」「预览全文」「导出 Word ↓」

### 顶栏快捷搜索

- 所有页面顶栏右侧保留一个搜索框（占位文字：搜索材料、办法、案例…）
- 输入关键词回车 → 跳转到 /search?q=关键词
- 支持快捷键 Ctrl+K 调出搜索框

---

## 11. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| LLM 生成内容有幻觉（编造制度条款） | 引用不真实，误导决策 | 引用校验环节：检查引用的条款号/文件名是否存在于原始文档；标注可疑引用 |
| Embedding API 不稳定或不可用 | 新文档无法入库 | 重试机制 + 降级（暂时只做全文索引） |
| pgvector 检索性能随数据量下降 | 检索变慢 | 数据量 < 10万块时 IVFFlat 够用；超过后迁移到 HNSW 索引 |
| 用户 API Key 额度耗尽 | 生成中途失败 | 调用前检测余额（如 API 支持）；失败后保留已生成内容，支持续生成 |
| 并发文档解析耗尽内存 | OOM | Celery max-memory-per-child 限制 + 并发数=2 |
| DOCX 模板格式复杂（嵌套表格、图片） | 占位符替换失败 | 限制模板格式规范；提供模板制作指南；降级为默认模板 |

---

## 12. 待确认事项（已全部确认）

| 编号 | 事项 | 结论 |
|------|------|------|
| 1 | 公文格式标准 | ✅ 已提供《集团公文标准与格式》实际文件，格式参数已落地到 Step 7 和 4.4 节 |
| 2 | 请示类型分类 | ✅ 已提供采购请示模板（含 5 种采购场景），分类体系见附录 B。其他类型（人事/资金/项目等）后续按需扩展 |
| 3 | 审批流程 | ✅ 不需要，系统只负责生成+导出，用户通过 OA 系统提交 |
| 4 | 数据备份 | ✅ 不需要考虑 |
| 5 | 域名与 HTTPS | ✅ 直接用 IP 访问，后续自行配置 |

---

## 附录 A：公文格式标准（提取自实际文件）

> 来源：《集团公文标准与格式.docx》

### A.1 页面参数

| 参数 | 值 |
|------|-----|
| 纸张 | A4 (210mm × 297mm) |
| 版心 | 156mm × 225mm |
| 上白边 | 37mm |
| 下白边 | 35mm |
| 左白边 | 28mm |
| 右白边 | 26mm |
| 装订 | 左侧装订 |

### A.2 字体字号

| 元素 | 字体 | 字号 | 对齐 |
|------|------|------|------|
| 发文机关标志（红头） | 方正小标宋_GBK | 2号 (22pt) | 居中 |
| 发文字号 | 方正仿宋_GBK | 3号 (16pt) | 左 |
| 签发人（"签发人"三字） | 方正仿宋_GBK | 3号 (16pt) | 右 |
| 签发人姓名 | 方正楷体_GBK | 3号 (16pt) | 右 |
| 标题 | 方正小标宋_GBK | 2号 (22pt) | 居中 |
| 主送机关 | 方正仿宋_GBK | 3号 (16pt) | 顶格 |
| 正文 | 方正仿宋_GBK | 3号 (16pt) | 首行缩进2字 |
| 一级标题（一、） | 方正黑体_GBK | 3号 (16pt) | 首行缩进2字 |
| 二级标题（（一）） | 方正楷体_GBK | 3号 (16pt) | 首行缩进2字 |
| 三级标题（1.） | 方正仿宋_GBK | 3号 (16pt) | 首行缩进2字 |
| 四级标题（（1）） | 方正仿宋_GBK | 3号 (16pt) | 首行缩进2字 |
| 附件说明 | 方正仿宋_GBK | 3号 (16pt) | 左空二字 |
| 发文机关署名 | 方正仿宋_GBK | 3号 (16pt) | 右 |
| 成文日期 | 方正仿宋_GBK | 3号 (16pt) | 右(距右边4字符) |
| 附注（联系人/电话） | 方正仿宋_GBK | 3号 (16pt) | 左空2字圆括号 |
| 抄送机关 | 方正仿宋_GBK | 4号 (14pt) | 左 |
| 印发机关和日期 | 方正仿宋_GBK | 4号 (14pt) | - |
| 页码 | 半角宋体 | 4号 (14pt) | - |

### A.3 段落格式

| 参数 | 值 |
|------|-----|
| 行距 | 固定值 30 磅 |
| 段前 | 0 行 |
| 段后 | 0 行 |
| 首行缩进 | 2 字符 |

### A.4 公文格式要素清单

1. 发文机关标志
2. 发文字号（机关代字 + 年份 + 顺序号）
3. 签发人（上行文必须）
4. 标题（发文机关 + 事由 + 文种，梯形或菱形排列）
5. 主送机关
6. 正文
7. 附件说明
8. 发文机关署名
9. 成文日期（阿拉伯数字，年月日标全，月日不编虚位）
10. 印章
11. 附注（请示件必须注明联系人和联系电话）
12. 附件
13. 抄送机关
14. 印发机关和印发日期
15. 页码

### A.5 标题排列规则

- 标题排列分行使用**梯形或菱形**，不使用长方形或沙漏型
- 回行要做到词意完整

---

## 附录 B：请示类型分类与采购请示模板（提取自实际文件）

> 来源：《采购请示模板2022.11.14.docx》

### B.1 当前已覆盖的请示类型

| 请示类型 | 来源 | 说明 |
|----------|------|------|
| 采购类请示 | 实际模板文件 | 含 5 种采购场景，预算档位自动匹配，制度引用自动选择 |

### B.2 后续可扩展的请示类型

| 请示类型 | 扩展方式 | 说明 |
|----------|----------|------|
| 人事类请示 | 上传模板 | 人员招聘、岗位调整、薪酬调整等 |
| 资金类请示 | 上传模板 | 资金申请、费用报销、预算调整等 |
| 项目类请示 | 上传模板 | 项目立项、项目变更、项目结项等 |
| 制度类请示 | 上传模板 | 制度制定、修订、废止等 |

扩展方式：管理员上传对应类型的 Word 模板到公司级知识库，系统自动识别占位符并纳入请示类型选项。

### B.3 采购请示完整结构

```
标题：XXX部门报请审议采购XXX的请示

主送机关：公司：

一、采购背景及预算
   场景1-5（根据采购动因选择）：
   - 场景1：完成生产经营目标，即特定项目执行所需
   - 场景2：生产经营要素组织，即完成某一类型项目所需的服务或货物
   - 场景3：多部门联合采购（金额最大的部门牵头）
   - 场景4：采购行政后勤、管理所需的服务或货物
   - 场景5：项目甲方或上级单位指定供应商

二、采购流程及制度依据
   情况1：单项预算 < 30万元 → 直接委托
   情况2：30万-50万元 → 询价
   情况3：50万-200万元 → 公开采购
   情况4：≥ 200万元 → 公开招标
   
   制度引用：
   - 《生产经营项目招标采购管理实施细则（试行）》（成天府人资发〔2022〕4号）
   - 《直接委托采购实施细则（试行）》（成天府人资发〔2022〕4号）

三、市场摸底调查情况/服务或货物采购方案
   直接委托流程要求：采购需求相同、报价内容一致、评判标准一致等
   其他采购流程要求：细化采购内容、明确评比维度等

四、请示事项/审议事项
   （一）明确供应商的采购方式
   （二）明确采购金额及结算方式

结尾：妥否，请示！

附件清单：
   必需要件：采购需求及要求、采购预算依据资料
   直接委托还需：供应商报价资料、唯一性证明、有权单位指定资料等
   询价/公开比选/公开招标还需：需求支撑资料

署名：成都天府新区人力资源开发服务有限公司 / 成都天府新区人才发展职业培训学校
      XXX部门
      XX年XX月XX日

附注：（联系人：XXX；联系电话：XXXXXXXXXX）

特别说明（5条）：
   1. 供应商为上级指定时须提供盖章指定资料
   2. 除公开采购/招标外不使用续签作为采购理由
   3. 预算依据应为历史采购记录、第三方平台、政府指导价
   4. 不具竞争性的垄断行业需说明垄断性质
   5. 供应商名称必须与合同签订方一致
```

### B.4 采购场景写作片段库

系统内置以下场景写作片段，LLM 生成时根据场景编号注入到 Prompt 的 few-shot 部分：

```
场景1（特定项目执行所需）：
  我部于XX年XX月XX日承接XXX项目（以下简称"本项目"），为XX提供XXX服务，
  服务内容包括XXX，总营收（暂定）XXX万元，利润率为X%。由于我司缺乏XX条件，
  由第三方机构提供XXX服务，辅助完成项目执行，能够更好的保证服务质量，实现降本增效。
  根据本项目的要求，我部草拟了采购需求，主要涉及XX、XX、XXX（详见附件X采购需求），
  同时，依据历史采购价格，测算出本次采购事项预算为XXX万元。

场景2（生产经营要素组织）：
  XX类项目为我部主要经营业务板块之一，根据我部本年度任务目标计划，预计执行项目XX个，
  全年营收约为XX万元，平均利润率控制在XX%以上。在该业务开展过程中，需要为客户提供
  包括XX、XX在内的高重复性、低技术要求服务。结合以往经验，将上述服务交由第三方机构
  完成，能够更明显降低项目成本、提高执行效率、保证服务品质。
  本次申请采购的XX辅助服务主要包含XX、XX等服务内容，根据以往采购成交金额，
  结合本年度经营计划测算出本次采购事项预算为XX万元。

场景3（多部门联合采购）：
  XX是我司重要的业务产品，根据XX部门签订的本年度生产经营目标责任书，预计上述业务
  产品将实现营收XX万元。在该业务开展过程中，需要为客户提供包括XX、XX在内的重复性、
  低技术要求服务。同时，XX部、XX部在工作开展过程中，也需要上述服务予以支撑。
  我部联合XX部、XX部共同草拟完成XX辅助性服务的采购需求内容并结合历史采购数据，
  测算采购费用共计XX万元。其中，XX部XX万元、XX部XX万元。

场景4（行政后勤/管理所需）：
  因XX（原因），导致XX（结果），为避免XX，提升公司XX或为改善XX，给予员工更好的
  工作条件，提高工作便捷性，建议采购XX服务（或货物）。
  我部门根据草拟的XX服务（货物）内容，向各部门发起需求征集，完善采购内容、明确采购预算。

场景5（甲方/上级指定供应商）：
  我部于XX年XX月XX日承接XX（单位名称）的XX项目，由我司为业主单位提供XX服务。
  项目总营收XX万元，预计利润率为X%，收益情况良好。
  根据项目合同约定的服务内容以及甲方的采购要求文件，本次采购费用不超过XX万元。
```

### B.5 采购流程制度引用片段库

```
情况1（< 30万元 → 直接委托）：
  依据前述采购预算为XX万元，我部按照《生产经营项目招标采购管理实施细则（试行）》
  （成天府人资发〔2022〕4号）第五条第四点第一项"单项合同估算价小于询价采购限额的
  项目（或该制度规定的其他可以直接委托的情况）"可以采用直接委托方式确定供应商。
  并按照《直接委托采购实施细则（试行）》（成天府人资发〔2022〕4号）第三章第四条
  直接委托一般执行流程，实施直接委托采购工作。

情况2（30万-50万元 → 询价）：
  依据前述采购预算为XX万元，我部按照《生产经营项目招标采购管理实施细则》
  （成天府人资发〔2022〕4号）第五条第三点"单项合同估算价30万元（含）以上，
  50万元以下生产经营（日常经营）类项目，应当采用询价"的规定。
  本项目采购应当采用询价方式，择优选定供应商。

情况3（50万-200万元 → 公开采购）：
  依据前述采购预算为XX万元，我部按照《生产经营项目招标采购管理实施细则》
  （成天府人资发〔2022〕4号）第五条第二点"单项合同估算价50万元（含）以上，
  200万元以下生产经营（日常经营）类项目，应当采用公开采购"的规定。
  本项目采购应当采用公开采购方式，择优选定供应商。

情况4（≥ 200万元 → 公开招标）：
  依据前述采购预算为XX万元，我部按照《生产经营项目招标采购管理实施细则》
  （成天府人资发〔2022〕4号）第五条第一点"单项合同估算价200万（含）以上
  生产经营（日常经营）类项目，应当采用招标"的规定。
  本项目采购应当采用公开招标方式，择优选定供应商。
```
