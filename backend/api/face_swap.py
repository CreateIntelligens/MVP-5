"""
換臉 API 路由
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
from pathlib import Path
import logging
from typing import Optional

from core.face_processor import get_face_processor, cleanup_old_results
from core.config import UPLOAD_CONFIG, TEMPLATE_CONFIG, get_template_path
from core.file_cleanup import cleanup_upload_file

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()

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
    執行換臉操作
    
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
        
        # 處理模板
        if template_id == "custom" and template_file:
            # 使用自訂模板
            validate_file(template_file)
            template_content = await template_file.read()
            if not template_content:
                raise HTTPException(status_code=400, detail="模板檔案內容為空")
            
            template_name = "自訂模板"
            template_info = {"description": "使用者自訂模板"}
            logger.info(f"開始處理換臉請求：使用自訂模板")
            
            # 獲取臉部處理器
            processor = get_face_processor()
            
            # 執行換臉處理（使用模板檔案內容）
            result_path = processor.process_image_data(
                user_image_data=file_content,
                template_image_data=template_content,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
        else:
            # 使用預設模板
            if template_id not in TEMPLATE_CONFIG["TEMPLATES"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"無效的模板 ID: {template_id}，可用的模板 ID: {list(TEMPLATE_CONFIG['TEMPLATES'].keys())}"
                )
            
            # 獲取模板資訊
            template_info = TEMPLATE_CONFIG["TEMPLATES"][template_id]
            template_path = get_template_path(template_id)
            template_name = template_info["name"]
            
            logger.info(f"開始處理換臉請求：模板 {template_id} ({template_name})")
            
            # 獲取臉部處理器
            processor = get_face_processor()
            
            # 執行換臉處理
            result_path = processor.process_image_file(
                user_image_data=file_content,
                template_image_path=template_path,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
        
        # 生成結果 URL
        result_filename = Path(result_path).name
        result_url = f"/results/{result_filename}"
        
        # 背景任務：清理舊檔案
        background_tasks.add_task(cleanup_old_results, max_age_hours=24)
        
        logger.info(f"換臉處理完成：{result_url}")
        
        return {
            "success": True,
            "message": "換臉完成！",
            "result_url": result_url,
            "template_id": template_id,
            "template_name": template_name,
            "template_description": template_info["description"]
        }
        
    except HTTPException:
        # 重新拋出 HTTP 異常
        raise
    except Exception as e:
        logger.error(f"換臉處理失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"換臉處理失敗：{str(e)}"
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
        from core.config import RESULTS_DIR
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
        from core.config import RESULTS_DIR
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
    清理舊的結果檔案
    
    - **max_age_hours**: 檔案最大保存時間（小時）
    """
    try:
        cleanup_old_results(max_age_hours)
        
        return {
            "success": True,
            "message": f"已清理超過 {max_age_hours} 小時的舊檔案"
        }
        
    except Exception as e:
        logger.error(f"清理檔案失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"清理檔案失敗：{str(e)}"
        )
