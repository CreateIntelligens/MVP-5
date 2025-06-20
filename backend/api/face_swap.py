"""
換臉 API 路由
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import uuid
import json
from pathlib import Path
import logging
from typing import Optional
from datetime import datetime
import asyncio

from core.face_processor import get_face_processor, cleanup_old_results
from core.config import UPLOAD_CONFIG, TEMPLATE_CONFIG, get_template_path, RESULTS_DIR
from core.file_cleanup import cleanup_upload_file

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()

# 任務狀態儲存（生產環境應使用 Redis 或資料庫）
task_status = {}

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
    target_face_index: int = 0
):
    """背景任務：執行換臉處理"""
    try:
        # 更新任務狀態：開始處理
        task_status[task_id].update({
            "status": "processing",
            "progress": 10,
            "message": "正在初始化 AI 模型..."
        })
        
        # 獲取臉部處理器
        processor = get_face_processor()
        
        # 更新進度：模型載入完成
        task_status[task_id].update({
            "progress": 30,
            "message": "正在偵測臉部特徵..."
        })
        
        # 處理模板
        if template_id == "custom" and template_content:
            template_info = {"description": "使用者自訂模板"}
            template_name = "自訂模板"
            
            # 執行換臉處理（使用模板檔案內容）
            result_path = processor.process_image_data(
                user_image_data=file_content,
                template_image_data=template_content,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
        else:
            # 使用預設模板
            template_info = TEMPLATE_CONFIG["TEMPLATES"][template_id]
            template_path = get_template_path(template_id)
            template_name = template_info["name"]
            
            # 更新進度：開始換臉處理
            task_status[task_id].update({
                "progress": 50,
                "message": "AI 正在進行換臉處理..."
            })
            
            # 執行換臉處理
            result_path = processor.process_image_file(
                user_image_data=file_content,
                template_image_path=template_path,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
        
        # 更新進度：生成結果
        task_status[task_id].update({
            "progress": 90,
            "message": "正在生成最終結果..."
        })
        
        # 生成結果 URL
        result_filename = Path(result_path).name
        result_url = f"/results/{result_filename}"
        
        # 任務完成
        task_status[task_id].update({
            "status": "completed",
            "progress": 100,
            "message": "換臉處理完成！",
            "result_url": result_url,
            "template_id": template_id,
            "template_name": template_name,
            "template_description": template_info["description"],
            "completed_at": datetime.now().isoformat()
        })
        
        logger.info(f"任務 {task_id} 換臉處理完成：{result_url}")
        
    except Exception as e:
        # 任務失敗
        task_status[task_id].update({
            "status": "failed",
            "progress": 0,
            "message": f"換臉處理失敗：{str(e)}",
            "error": str(e),
            "failed_at": datetime.now().isoformat()
        })
        
        logger.error(f"任務 {task_id} 換臉處理失敗：{e}")

@router.post("/face-swap")
async def swap_face(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="使用者上傳的照片"),
    template_id: str = Form(..., description="模板 ID"),
    template_file: Optional[UploadFile] = File(None, description="自訂模板檔案"),
    source_face_index: int = Form(0, description="來源臉部索引"),
    target_face_index: int = Form(0, description="目標臉部索引")
):
    """
    提交換臉任務（非同步處理）
    
    - **file**: 使用者上傳的照片檔案
    - **template_id**: 要使用的模板 ID (1-6)
    - **source_face_index**: 來源圖片中的臉部索引 (預設: 0)
    - **target_face_index**: 模板圖片中的臉部索引 (預設: 0)
    """
    try:
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
        
        # 生成任務 ID
        task_id = str(uuid.uuid4())
        
        # 初始化任務狀態
        task_status[task_id] = {
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
        }
        
        # 啟動背景任務
        background_tasks.add_task(
            process_face_swap_task,
            task_id,
            file_content,
            template_id,
            template_content,
            source_face_index,
            target_face_index
        )
        
        # 背景任務：清理舊檔案
        background_tasks.add_task(cleanup_old_results, max_age_hours=24)
        
        logger.info(f"已提交換臉任務：{task_id}")
        
        return {
            "success": True,
            "message": "任務已提交，請使用任務 ID 查詢處理狀態",
            "task_id": task_id,
            "status": "pending"
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
async def get_task_status(task_id: str):
    """
    查詢任務處理狀態
    
    - **task_id**: 任務 ID
    """
    try:
        if task_id not in task_status:
            raise HTTPException(status_code=404, detail="任務不存在")
        
        status = task_status[task_id].copy()
        
        return {
            "success": True,
            "task_status": status
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
