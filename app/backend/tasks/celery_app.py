from celery import Celery

from core.config import settings

celery_app = Celery(
    "gongwen",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    # worker 启动时自动 import 任务模块。
    # 不写这一项的话，`celery -A tasks.celery_app worker` 只加载本模块，
    # tasks/tasks.py 里的 @celery_app.task 从未执行，worker 的 [tasks]
    # 列表为空，收到任务会报 unregistered，生成和解析全部静默失败。
    include=["tasks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    worker_max_memory_per_child=512000,
    # Celery 6.0 起 broker_connection_retry 不再决定启动阶段的重试行为
    broker_connection_retry_on_startup=True,
)
