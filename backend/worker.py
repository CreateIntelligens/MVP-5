"""
獨立 GPU Worker：負責從 Redis 佇列取出任務並執行換臉處理
"""
import asyncio
import json
import logging
import logging.config
import signal
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from core.redis_client import redis_client, TASK_QUEUE_KEY
from core.config import ensure_directories, LOGGING_CONFIG, PENDING_UPLOADS_DIR
from api.face_swap import (
    process_face_swap_task,
    update_task_status,
    decr_queue_size,
)


logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("gpu_worker")


async def fetch_job(timeout: int = 5) -> Optional[Dict[str, Any]]:
    """阻塞等待下一個任務，若逾時返回 None"""
    result = await redis_client.blpop(TASK_QUEUE_KEY, timeout)
    if not result:
        return None
    _, payload = result
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.error(f"解析佇列任務失敗：{exc}，payload={payload!r}")
        return None


async def clean_pending_files(job: Dict[str, Any]) -> None:
    """清理暫存的上傳檔案"""
    for key in ("file_path", "template_path"):
        value = job.get(key)
        if not value:
            continue
        try:
            path = Path(value)
            if path.is_file() and str(path).startswith(str(PENDING_UPLOADS_DIR)):
                path.unlink(missing_ok=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"刪除暫存檔失敗 ({value}): {exc}")


async def process_job(job: Dict[str, Any]) -> None:
    """執行單一佇列任務"""
    task_id = job["task_id"]
    file_path = Path(job["file_path"])
    template_path = job.get("template_path")

    logger.info(f"[GPU Worker] 開始處理任務 {task_id}")

    try:
        file_content = file_path.read_bytes()
    except Exception as exc:  # noqa: BLE001
        logger.error(f"讀取來源檔案失敗 ({file_path}): {exc}")
        await update_task_status(task_id, {
            "status": "failed",
            "progress": 0,
            "message": "來源檔案不存在或讀取失敗",
            "error": str(exc),
            "failed_at": datetime.now().isoformat(),
        })
        await decr_queue_size()
        await clean_pending_files(job)
        return

    template_content: Optional[bytes] = None
    if template_path:
        try:
            template_content = Path(template_path).read_bytes()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"讀取自訂模板失敗 ({template_path}): {exc}")
            await update_task_status(task_id, {
                "status": "failed",
                "progress": 0,
                "message": "自訂模板檔案讀取失敗",
                "error": str(exc),
                "failed_at": datetime.now().isoformat(),
            })
            await decr_queue_size()
            await clean_pending_files(job)
            return

    await process_face_swap_task(
        task_id=task_id,
        file_content=file_content,
        template_id=job["template_id"],
        template_content=template_content,
        source_face_index=job.get("source_face_index", 0),
        target_face_index=job.get("target_face_index", 0),
        initial_queue_size=job.get("initial_queue_position"),
    )

    await clean_pending_files(job)
    logger.info(f"[GPU Worker] 任務 {task_id} 處理完成")


async def worker_loop() -> None:
    """Worker 主循環"""
    ensure_directories()

    # 預熱 GPU 模型
    logger.info("🔥 GPU Worker 啟動，正在預熱 AI 模型...")
    try:
        from core.face_processor import get_face_processor
        processor = get_face_processor()
        logger.info(f"✅ AI 模型預熱完成！GPU 狀態: {'啟用' if processor.gpu_available else '未啟用'}")
    except Exception as exc:
        logger.error(f"⚠️  模型預熱失敗: {exc}")
        logger.info("   首次任務處理時將進行模型初始化")

    logger.info("📡 GPU Worker 就緒，等待任務...")
    while True:
        job = await fetch_job()
        if not job:
            continue
        try:
            await process_job(job)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"處理任務失敗：{exc}")


def setup_signals(loop: asyncio.AbstractEventLoop) -> None:
    """註冊訊號處理，優雅退出"""
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, loop.stop)
        except NotImplementedError:
            # Windows 無法註冊 signal handler
            pass


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    setup_signals(loop)
    try:
        loop.run_until_complete(worker_loop())
    finally:
        loop.close()
        logger.info("GPU Worker 已關閉")


if __name__ == "__main__":
    main()
