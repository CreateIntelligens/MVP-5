"""
換臉 API 路由
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
import os
import uuid
import json
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime
import asyncio
import cv2
import time
from concurrent.futures import ThreadPoolExecutor

from core.face_processor import get_face_processor, cleanup_old_results, get_system_info
from core.config import UPLOAD_CONFIG, TEMPLATE_CONFIG, get_template_path, RESULTS_DIR, UPLOADS_DIR
from core.file_cleanup import cleanup_upload_file
from core.redis_client import redis_client, TASK_KEY_PREFIX, QUEUE_SIZE_KEY, GPU_LOCK_KEY
from core.distributed_lock import RedisLock

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()

# 線程池 - GPU操作 (單線程串行)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu_worker")

# ==================== Redis 工具函數 ====================

def get_task_status(task_id: str) -> dict:
    """從 Redis 獲取任務狀態"""
    data = redis_client.get(f"{TASK_KEY_PREFIX}{task_id}")
    if data:
        return json.loads(data)
    return None

def set_task_status(task_id: str, status: dict):
    """設置任務狀態到 Redis (TTL 48 小時)"""
    redis_client.setex(
        f"{TASK_KEY_PREFIX}{task_id}",
        172800,  # 48 小時過期
        json.dumps(status, ensure_ascii=False)
    )

def update_task_status(task_id: str, updates: dict):
    """更新任務狀態"""
    task = get_task_status(task_id)
    if task:
        task.update(updates)
        set_task_status(task_id, task)

def get_queue_size() -> int:
    """獲取當前佇列大小"""
    size = redis_client.get(QUEUE_SIZE_KEY)
    return int(size) if size else 0

def incr_queue_size() -> int:
    """佇列大小 +1"""
    return redis_client.incr(QUEUE_SIZE_KEY)

def decr_queue_size() -> int:
    """佇列大小 -1"""
    size = redis_client.decr(QUEUE_SIZE_KEY)
    # 防止負數
    if size < 0:
        redis_client.set(QUEUE_SIZE_KEY, 0)
        return 0
    return size

def validate_file(file: UploadFile) -> None:
    """驗證上傳的檔案"""
    # 檢查檔案大小
    if file.size and file.size > UPLOAD_CONFIG["MAX_FILE_SIZE"]:
        raise HTTPException(
            status_code=413,
            detail=f"檔案過大，最大允許 {UPLOAD_CONFIG['MAX_FILE_SIZE'] // (1024*1024)}MB"
        )
    
    # 檢查檔案類型
    if file.content_type not in UPLOAD_CONFIG["ALLOWED_MIME_TYPES"]:
        raise HTTPException(
            status_code=415,
            detail=f"不支援的檔案格式，請上傳 {', '.join(UPLOAD_CONFIG['ALLOWED_MIME_TYPES'])} 格式的圖片"
        )
    
    # 檢查檔案副檔名
    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in UPLOAD_CONFIG["ALLOWED_EXTENSIONS"]:
        raise HTTPException(
            status_code=415,
            detail=f"不支援的檔案副檔名，請上傳 {', '.join(UPLOAD_CONFIG['ALLOWED_EXTENSIONS'])} 格式的圖片"
        )

async def process_face_swap_task(
    task_id: str,
    file_content: bytes,
    template_id: str,
    template_content: Optional[bytes] = None,
    source_face_index: int = 0,
    target_face_index: int = 0,
    initial_queue_size: Optional[int] = None
):
    """背景任務：執行換臉處理 (使用 Redis 分散式鎖)"""

    async with RedisLock():
        logger.info(
            f"開始處理背景換臉任務 {task_id}，提交時佇列大小: "
            f"{initial_queue_size if initial_queue_size is not None else 'unknown'}"
        )

        try:
            # 更新任務狀態：開始處理
            update_task_status(task_id, {
                "status": "processing",
                "progress": 10,
                "message": "正在初始化 AI 模型...",
                "queue_position": 1,
                "queue_ahead": 0
            })

            # 獲取臉部處理器
            processor = get_face_processor()
            logger.info(f"任務 {task_id} 使用 GPU 處理")

            # 更新進度：模型載入完成
            update_task_status(task_id, {
                "progress": 30,
                "message": "正在偵測臉部特徵...",
                "queue_position": 1,
                "queue_ahead": 0
            })

            # 處理模板
            if template_id == "custom" and template_content:
                template_info = {"description": "使用者自訂模板"}
                template_name = "自訂模板"

                loop = asyncio.get_event_loop()
                process_result = await loop.run_in_executor(
                    executor,
                    processor.process_image_data,
                    file_content,
                    template_content,
                    source_face_index,
                    target_face_index,
                    task_id
                )
            else:
                template_info = TEMPLATE_CONFIG["TEMPLATES"][template_id]
                template_path = get_template_path(template_id)
                template_name = template_info["name"]

                update_task_status(task_id, {
                    "progress": 50,
                    "message": "AI 正在進行換臉處理...",
                    "queue_position": 1,
                    "queue_ahead": 0
                })

                loop = asyncio.get_event_loop()
                process_result = await loop.run_in_executor(
                    executor,
                    processor.process_image_file,
                    file_content,
                    template_path,
                    source_face_index,
                    target_face_index,
                    task_id
                )

            update_task_status(task_id, {
                "progress": 90,
                "message": "正在生成最終結果...",
                "queue_position": 1,
                "queue_ahead": 0
            })

            result_path = process_result["result_path"]
            original_path = process_result["original_path"]

            result_filename = Path(result_path).name
            result_url = f"/results/{result_filename}"

            original_filename = Path(original_path).name
            original_url = f"/uploads/{original_filename}"

            update_task_status(task_id, {
                "status": "completed",
                "progress": 100,
                "message": "換臉處理完成",
                "result_url": result_url,
                "original_url": original_url,
                "template_id": template_id,
                "template_name": template_name,
                "template_description": template_info["description"],
                "completed_at": datetime.now().isoformat(),
                "queue_position": 0,
                "queue_ahead": 0
            })

            logger.info(f"任務 {task_id} 換臉處理完成：{result_url}")

        except Exception as e:
            update_task_status(task_id, {
                "status": "failed",
                "progress": 0,
                "message": f"換臉處理失敗：{str(e)}",
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
                "queue_position": 0,
                "queue_ahead": 0
            })

            logger.error(f"任務 {task_id} 換臉處理失敗：{e}")

        finally:
            try:
                remaining_queue_size = decr_queue_size()
            except Exception as redis_error:
                logger.warning(f"任務 {task_id} 更新佇列大小失敗：{redis_error}")
                remaining_queue_size = "unknown"
            logger.info(f"背景換臉任務 {task_id} 完成，佇列大小: {remaining_queue_size}")
            update_task_status(task_id, {
                "queue_remaining": remaining_queue_size
            })

@router.post("/face-swap")
async def swap_face(
    file: UploadFile = File(..., description="使用者上傳的照片"),
    template_id: Optional[str] = Form(None, description="模板 ID"),
    template_file: Optional[UploadFile] = File(None, description="自訂模板檔案"),
    source_face_index: int = Form(0, description="來源臉部索引"),
    target_face_index: int = Form(0, description="目標臉部索引")
):
    """
    非同步換臉任務提交
    
    提交換臉任務至後台處理佇列，返回任務 ID 供狀態查詢
    
    - **file**: 使用者上傳的照片檔案
    - **template_id**: 模板 ID (1-6)，可選參數
    - **template_file**: 自訂模板檔案，可選參數
    - **source_face_index**: 來源圖片中的臉部索引 (預設: 0)
    - **target_face_index**: 模板圖片中的臉部索引 (預設: 0)
    """
    try:
        # 生成 task_id

        task_id = str(uuid.uuid4())

        # 自動判斷使用自訂模板還是預設模板
        if template_file and template_file.filename:
            template_id = "custom"
        elif not template_id:
            # 如果都沒有提供，拋出錯誤
            raise HTTPException(
                status_code=400, 
                detail="請提供 template_id 或上傳 template_file"
            )
            
        # 驗證檔案
        validate_file(file)
        
        # 讀取檔案內容
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="檔案內容為空")
        
        # 處理模板檔案
        template_content = None
        if template_id == "custom" and template_file:
            validate_file(template_file)
            template_content = await template_file.read()
            if not template_content:
                raise HTTPException(status_code=400, detail="模板檔案內容為空")
        elif template_id != "custom" and template_id not in TEMPLATE_CONFIG["TEMPLATES"]:
            raise HTTPException(
                status_code=400,
                detail=f"無效的模板 ID: {template_id}，可用的模板 ID: {list(TEMPLATE_CONFIG['TEMPLATES'].keys())}"
            )
        
        # 初始化任務狀態 (task_id已在前面生成)
        set_task_status(task_id, {
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "message": "任務已提交，等待處理...",
            "template_id": template_id,
            "created_at": datetime.now().isoformat(),
            "result_url": None,
            "template_name": None,
            "template_description": None,
            "error": None
        })
        
        # 增加佇列計數
        queue_size = incr_queue_size()
        queue_ahead = queue_size - 1 if queue_size > 0 else 0

        update_task_status(task_id, {
            "queue_position": queue_size,
            "queue_ahead": queue_ahead,
            "initial_queue_position": queue_size
        })

        # 啟動背景任務（使用 asyncio.create_task 而非 BackgroundTasks）
        asyncio.create_task(
            process_face_swap_task(
                task_id,
                file_content,
                template_id,
                template_content,
                source_face_index,
                target_face_index,
                queue_size
            )
        )

        logger.info(f"已提交換臉任務：{task_id}，當前佇列大小: {queue_size}")
        
        return {
            "success": True,
            "message": "任務已提交，請使用任務 ID 查詢處理狀態",
            "task_id": task_id,
            "status": "pending",
            "queue_position": queue_size,
            "queue_ahead": queue_ahead
        }
        
    except HTTPException:
        # 重新拋出 HTTP 異常
        raise
    except Exception as e:
        logger.error(f"任務提交失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"任務提交失敗：{str(e)}"
        )

@router.get("/face-swap/status/{task_id}")
async def get_task_status_api(task_id: str):
    """
    查詢任務處理狀態 (從 Redis 讀取,立即回應)

    - **task_id**: 任務 ID
    """
    try:
        status = get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail="任務不存在")

        queue_size_snapshot = None
        try:
            queue_size_snapshot = get_queue_size()
        except Exception as redis_error:
            logger.warning(f"取得目前佇列大小失敗：{redis_error}")

        return {
            "success": True,
            "task_status": status,
            "queue_size": queue_size_snapshot
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查詢任務狀態失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"查詢任務狀態失敗：{str(e)}"
        )

@router.get("/face-swap/tasks")
async def list_tasks(limit: int = 10):
    """
    列出最近的任務
    
    - **limit**: 返回任務數量限制
    """
    try:
        # 按創建時間排序，返回最新的任務
        sorted_tasks = sorted(
            task_status.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True
        )
        
        return {
            "success": True,
            "tasks": sorted_tasks[:limit],
            "total": len(task_status)
        }
        
    except Exception as e:
        logger.error(f"列出任務失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"列出任務失敗：{str(e)}"
        )

@router.delete("/face-swap/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    刪除任務記錄
    
    - **task_id**: 任務 ID
    """
    try:
        if task_id not in task_status:
            raise HTTPException(status_code=404, detail="任務不存在")
        
        # 如果任務已完成且有結果檔案，嘗試刪除檔案
        task = task_status[task_id]
        if task.get("result_url"):
            try:
                result_filename = task["result_url"].split("/")[-1]
                result_path = RESULTS_DIR / result_filename
                if result_path.exists():
                    result_path.unlink()
                    logger.info(f"已刪除結果檔案：{result_filename}")
            except Exception as e:
                logger.warning(f"刪除結果檔案失敗：{e}")
        
        # 刪除原圖檔案
        if task.get("original_url"):
            try:
                original_filename = task["original_url"].split("/")[-1]
                original_path = UPLOADS_DIR / original_filename
                if original_path.exists():
                    original_path.unlink()
                    logger.info(f"已刪除原圖檔案：{original_filename}")
            except Exception as e:
                logger.warning(f"刪除原圖檔案失敗：{e}")
        
        # 刪除任務記錄
        del task_status[task_id]
        
        return {
            "success": True,
            "message": f"任務 {task_id} 已刪除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"刪除任務失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"刪除任務失敗：{str(e)}"
        )

@router.post("/validate-image")
async def validate_image(file: UploadFile = File(..., description="要驗證的圖片檔案")):
    """
    驗證圖片並返回臉部資訊
    
    - **file**: 要驗證的圖片檔案
    """
    try:
        # 驗證檔案
        validate_file(file)
        
        # 讀取檔案內容
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="檔案內容為空")
        
        # 獲取臉部處理器
        processor = get_face_processor()
        
        # 驗證圖片
        validation_result = processor.validate_image(file_content)
        
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"圖片驗證失敗：{validation_result.get('error', '未知錯誤')}"
            )
        
        return {
            "success": True,
            "message": "圖片驗證成功",
            "image_info": validation_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"圖片驗證失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"圖片驗證失敗：{str(e)}"
        )

@router.get("/results/{filename}")
async def get_result_file(filename: str):
    """
    獲取處理結果檔案
    
    - **filename**: 結果檔案名稱
    """
    try:
        # 安全檢查：只允許特定格式的檔名
        if not filename.startswith("result_") or not filename.endswith(".jpg"):
            raise HTTPException(status_code=400, detail="無效的檔案名稱")
        
        # 建構檔案路徑
        file_path = RESULTS_DIR / filename
        
        # 檢查檔案是否存在
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 返回檔案
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"檔案獲取失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"檔案獲取失敗：{str(e)}"
        )

@router.get("/uploads/{filename}")
async def get_original_file(filename: str):
    """
    獲取用戶上傳的原始檔案
    
    - **filename**: 原始檔案名稱
    """
    try:
        # 安全檢查：只允許特定格式的檔名
        if not filename.startswith("original_") or not filename.endswith(".jpg"):
            raise HTTPException(status_code=400, detail="無效的檔案名稱")
        
        # 建構檔案路徑
        file_path = UPLOADS_DIR / filename
        
        # 檢查檔案是否存在
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 返回檔案
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"原始檔案獲取失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"原始檔案獲取失敗：{str(e)}"
        )

@router.delete("/results/{filename}")
async def delete_result_file(filename: str):
    """
    刪除處理結果檔案
    
    - **filename**: 要刪除的檔案名稱
    """
    try:
        # 安全檢查
        if not filename.startswith("result_") or not filename.endswith(".jpg"):
            raise HTTPException(status_code=400, detail="無效的檔案名稱")
        
        # 建構檔案路徑
        file_path = RESULTS_DIR / filename
        
        # 檢查檔案是否存在
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 刪除檔案
        file_path.unlink()
        
        logger.info(f"已刪除檔案：{filename}")
        
        return {
            "success": True,
            "message": f"檔案 {filename} 已刪除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"檔案刪除失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"檔案刪除失敗：{str(e)}"
        )

@router.delete("/uploads/{filename}")
async def delete_original_file(filename: str):
    """
    刪除原始上傳檔案
    
    - **filename**: 要刪除的檔案名稱
    """
    try:
        # 安全檢查
        if not filename.startswith("original_") or not filename.endswith(".jpg"):
            raise HTTPException(status_code=400, detail="無效的檔案名稱")
        
        # 建構檔案路徑
        file_path = UPLOADS_DIR / filename
        
        # 檢查檔案是否存在
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="檔案不存在")
        
        # 刪除檔案
        file_path.unlink()
        
        logger.info(f"已刪除原始檔案：{filename}")
        
        return {
            "success": True,
            "message": f"原始檔案 {filename} 已刪除"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"原始檔案刪除失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"原始檔案刪除失敗：{str(e)}"
        )

@router.get("/queue/status")
async def get_queue_status_api():
    """
    獲取當前佇列狀態和系統負載資訊 (從 Redis 讀取)

    Returns:
        dict: 包含佇列大小、處理中任務、系統資源等資訊
    """
    try:
        import psutil

        # 系統資源資訊
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0)  # 改為 0 避免阻塞

        # 檢查 GPU 鎖狀態
        gpu_lock_exists = redis_client.exists(GPU_LOCK_KEY)

        return {
            "success": True,
            "queue_status": {
                "current_queue_size": get_queue_size(),
                "max_queue_size": "unlimited",  # 無限排隊模式
                "gpu_lock_active": bool(gpu_lock_exists),
                "max_concurrent": 1  # GPU串行處理
            },
            "task_statistics": {
                "note": "Task statistics disabled for performance"
            },
            "system_resources": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2)
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"獲取佇列狀態失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取佇列狀態失敗：{str(e)}"
        )

@router.post("/cleanup")
async def cleanup_results(max_age_hours: int = 24):
    """
    清理舊的結果檔案和任務記錄
    
    - **max_age_hours**: 檔案最大保存時間（小時）
    """
    try:
        # 清理檔案
        cleanup_old_results(max_age_hours)
        
        # 清理舊的任務記錄（保留最近100個）
        if len(task_status) > 100:
            sorted_tasks = sorted(
                task_status.items(),
                key=lambda x: x[1].get("created_at", ""),
                reverse=True
            )
            
            # 保留最新的100個任務
            keep_tasks = dict(sorted_tasks[:100])
            task_status.clear()
            task_status.update(keep_tasks)
            
            logger.info(f"已清理舊任務記錄，保留最新 100 個任務")
        
        return {
            "success": True,
            "message": f"已清理超過 {max_age_hours} 小時的舊檔案和任務記錄"
        }
        
    except Exception as e:
        logger.error(f"清理檔案失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理檔案失敗：{str(e)}"
        )

@router.get("/system/info")
async def get_system_status():
    """
    獲取系統狀態資訊，包括GPU支援狀態
    
    Returns:
        dict: 系統資訊包括GPU、記憶體、CPU等資訊
    """
    try:
        system_info = get_system_info()
        
        # 獲取處理器的GPU狀態
        processor = get_face_processor()
        processor_gpu_status = getattr(processor, 'gpu_available', False)
        
        return {
            "success": True,
            "system_info": system_info,
            "processor_gpu_enabled": processor_gpu_status,
            "message": f"目前使用{'GPU' if processor_gpu_status else 'CPU'}模式進行處理",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"獲取系統資訊失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取系統資訊失敗：{str(e)}"
        )

@router.post("/swapper")
async def swapper(
    file: UploadFile = File(..., description="使用者上傳的照片"),
    template_id: Optional[str] = Form(None, description="模板 ID"),
    template_file: Optional[UploadFile] = File(None, description="自訂模板檔案"),
    source_face_index: int = Form(0, description="來源臉部索引"),
    target_face_index: int = Form(0, description="目標臉部索引")
):
    """
    同步換臉 API
    
    實時處理換臉請求並直接返回結果
    
    Args:
        file: 使用者上傳的照片檔案
        template_id: 模板 ID (1-6)，可選參數
        template_file: 自訂模板檔案，可選參數
        source_face_index: 來源圖片中的臉部索引 (預設: 0)
        target_face_index: 模板圖片中的臉部索引 (預設: 0)
    """
    try:
        sync_task_id = f"sync-{uuid.uuid4()}"
        async with RedisLock():
            sync_queue_size: Optional[object] = None
            try:
                sync_queue_size = get_queue_size()
            except Exception as redis_error:
                logger.warning(f"同步任務 {sync_task_id} 無法取得佇列大小：{redis_error}")
                sync_queue_size = "unknown"
            logger.info(f"開始處理同步換臉請求，佇列大小: {sync_queue_size}")
            
            try:
                # 自動判斷使用自訂模板還是預設模板
                if template_file and template_file.filename:
                    template_id = "custom"
                elif not template_id:
                    # 如果都沒有提供，拋出錯誤
                    raise HTTPException(
                        status_code=400, 
                        detail="請提供 template_id 或上傳 template_file"
                    )
                    
                # 驗證檔案
                validate_file(file)
                
                # 讀取檔案內容
                file_content = await file.read()
                if not file_content:
                    raise HTTPException(status_code=400, detail="檔案內容為空")
                
                # 處理模板檔案
                template_content = None
                if template_id == "custom" and template_file:
                    validate_file(template_file)
                    template_content = await template_file.read()
                    if not template_content:
                        raise HTTPException(status_code=400, detail="模板檔案內容為空")
                elif template_id != "custom" and template_id not in TEMPLATE_CONFIG["TEMPLATES"]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"無效的模板 ID: {template_id}，可用的模板 ID: {list(TEMPLATE_CONFIG['TEMPLATES'].keys())}"
                    )
                
                # 獲取臉部處理器
                processor = get_face_processor()
                
                # 直接進行換臉處理
                start_time = datetime.now()
                
                # 保存原圖
                original_filename = f"original_{uuid.uuid4().hex[:8]}.jpg"
                original_path = UPLOADS_DIR / original_filename
                UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
                with open(original_path, 'wb') as f:
                    f.write(file_content)
                original_url = f"/uploads/{original_filename}"
                
                # 將檔案內容轉換為圖片
                source_image = processor._decode_image(file_content)
        
                # 處理模板圖片
                if template_id == "custom" and template_content:
                    target_image = processor._decode_image(template_content)
                else:
                    # 載入預設模板
                    template_path = get_template_path(template_id)
                    target_image = cv2.imread(str(template_path))
                    if target_image is None:
                        raise HTTPException(status_code=400, detail=f"無法載入模板 {template_id}")
        
                # 執行換臉
                result_image = await asyncio.get_event_loop().run_in_executor(
                    executor,
                    processor.swap_faces,
                    source_image,
                    target_image,
                    source_face_index,
                    target_face_index
                )
                
                # 保存結果
                result_filename = f"result_{uuid.uuid4().hex[:8]}.jpg"
                result_path = RESULTS_DIR / result_filename
                cv2.imwrite(str(result_path), result_image)
                
                result_url = f"/results/{result_filename}"
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                # 獲取模板資訊
                template_info = TEMPLATE_CONFIG["TEMPLATES"].get(template_id, {})
                template_name = template_info.get("name", f"模板 {template_id}")
                template_description = template_info.get("description", "")
                
                return {
                    "success": True,
                    "result_url": result_url,
                    "original_url": original_url,
                    "template_name": template_name,
                    "template_description": template_description,
                    "processing_time": f"{processing_time:.2f}s",
                    "message": "換臉處理完成"
                }
            finally:
                try:
                    final_queue_size = get_queue_size()
                except Exception as redis_error:
                    logger.warning(f"同步任務 {sync_task_id} 更新佇列大小失敗：{redis_error}")
                    final_queue_size = "unknown"
                logger.info(f"同步換臉請求完成，佇列大小: {final_queue_size}")
        
    except HTTPException:
        # 重新拋出 HTTP 異常
        raise
    except Exception as e:
        logger.error(f"簡化換臉 API 失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"處理失敗：{str(e)}"
        )
