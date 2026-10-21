import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from core.database import SessionLocal
from models.models import GenerationTask

router = APIRouter()


@router.websocket("/ws/generation/{task_id}")
async def ws_generation(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for real-time generation progress updates."""
    await websocket.accept()
    try:
        last_progress = -1
        last_step = ""
        while True:
            db = SessionLocal()
            try:
                task = db.query(GenerationTask).filter(GenerationTask.id == task_id).first()
                if not task:
                    await websocket.send_json({"error": "Task not found"})
                    break

                if task.progress != last_progress or task.current_step != last_step:
                    await websocket.send_json({
                        "task_id": str(task.id),
                        "status": task.status,
                        "progress": task.progress,
                        "current_step": task.current_step,
                        "error": task.error_message,
                    })
                    last_progress = task.progress
                    last_step = task.current_step or ""

                # If task completed or failed, send content and close
                if task.status in ("completed", "failed", "cancelled"):
                    if task.result_content:
                        await websocket.send_json({
                            "task_id": str(task.id),
                            "status": task.status,
                            "progress": task.progress,
                            "content": task.result_content,
                            "references": task.references[:10] if task.references else [],
                        })
                    break

            finally:
                db.close()

            await asyncio.sleep(1)  # Poll every second

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except Exception:
            pass
