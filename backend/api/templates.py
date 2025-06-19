"""
模板 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import logging
from pathlib import Path
from typing import List, Dict, Any

from core.config import TEMPLATE_CONFIG, get_template_path

# 設定日誌
logger = logging.getLogger(__name__)

# 建立路由器
router = APIRouter()

@router.get("/templates")
async def get_templates() -> Dict[str, Any]:
    """
    獲取所有可用的模板
    
    返回所有模板的詳細資訊，包括 ID、名稱、描述、分類等
    """
    try:
        templates = {}
        
        for template_id, template_info in TEMPLATE_CONFIG["TEMPLATES"].items():
            # 檢查模板檔案是否存在
            try:
                template_path = get_template_path(template_id)
                file_exists = template_path.exists()
            except Exception as e:
                logger.warning(f"模板 {template_id} 路徑檢查失敗：{e}")
                file_exists = False
            
            templates[template_id] = {
                "id": template_info["id"],
                "name": template_info["name"],
                "description": template_info["description"],
                "category": template_info["category"],
                "gender": template_info["gender"],
                "available": file_exists,
                "preview_url": f"/api/templates/{template_id}/preview" if file_exists else None
            }
        
        return {
            "success": True,
            "message": "模板列表獲取成功",
            "templates": templates,
            "total_count": len(templates),
            "available_count": sum(1 for t in templates.values() if t["available"])
        }
        
    except Exception as e:
        logger.error(f"獲取模板列表失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取模板列表失敗：{str(e)}"
        )

@router.get("/templates/{template_id}")
async def get_template(template_id: str) -> Dict[str, Any]:
    """
    獲取特定模板的詳細資訊
    
    - **template_id**: 模板 ID
    """
    try:
        if template_id not in TEMPLATE_CONFIG["TEMPLATES"]:
            raise HTTPException(
                status_code=404,
                detail=f"模板 {template_id} 不存在"
            )
        
        template_info = TEMPLATE_CONFIG["TEMPLATES"][template_id]
        
        # 檢查模板檔案是否存在
        try:
            template_path = get_template_path(template_id)
            file_exists = template_path.exists()
            file_size = template_path.stat().st_size if file_exists else 0
        except Exception as e:
            logger.warning(f"模板 {template_id} 檔案檢查失敗：{e}")
            file_exists = False
            file_size = 0
        
        return {
            "success": True,
            "message": f"模板 {template_id} 資訊獲取成功",
            "template": {
                "id": template_info["id"],
                "name": template_info["name"],
                "description": template_info["description"],
                "category": template_info["category"],
                "gender": template_info["gender"],
                "available": file_exists,
                "file_size": file_size,
                "preview_url": f"/api/templates/{template_id}/preview" if file_exists else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取模板 {template_id} 失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取模板資訊失敗：{str(e)}"
        )

@router.get("/templates/{template_id}/preview")
async def get_template_preview(template_id: str):
    """
    獲取模板預覽圖片
    
    - **template_id**: 模板 ID
    """
    try:
        if template_id not in TEMPLATE_CONFIG["TEMPLATES"]:
            raise HTTPException(
                status_code=404,
                detail=f"模板 {template_id} 不存在"
            )
        
        # 獲取模板檔案路徑
        template_path = get_template_path(template_id)
        
        if not template_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"模板 {template_id} 檔案不存在"
            )
        
        template_info = TEMPLATE_CONFIG["TEMPLATES"][template_id]
        
        # 返回圖片檔案
        return FileResponse(
            path=str(template_path),
            filename=f"template_{template_id}_{template_info['name']}.jpg",
            media_type="image/jpeg"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"獲取模板 {template_id} 預覽失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取模板預覽失敗：{str(e)}"
        )

@router.get("/templates/categories")
async def get_template_categories() -> Dict[str, Any]:
    """
    獲取所有模板分類
    
    返回按分類組織的模板列表
    """
    try:
        categories = {}
        
        for template_id, template_info in TEMPLATE_CONFIG["TEMPLATES"].items():
            category = template_info["category"]
            
            if category not in categories:
                categories[category] = {
                    "name": category,
                    "templates": [],
                    "count": 0
                }
            
            # 檢查模板檔案是否存在
            try:
                template_path = get_template_path(template_id)
                file_exists = template_path.exists()
            except Exception:
                file_exists = False
            
            if file_exists:
                categories[category]["templates"].append({
                    "id": template_info["id"],
                    "name": template_info["name"],
                    "description": template_info["description"],
                    "gender": template_info["gender"]
                })
                categories[category]["count"] += 1
        
        # 移除空分類
        categories = {k: v for k, v in categories.items() if v["count"] > 0}
        
        return {
            "success": True,
            "message": "模板分類獲取成功",
            "categories": categories,
            "total_categories": len(categories)
        }
        
    except Exception as e:
        logger.error(f"獲取模板分類失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"獲取模板分類失敗：{str(e)}"
        )

@router.get("/templates/gender/{gender}")
async def get_templates_by_gender(gender: str) -> Dict[str, Any]:
    """
    根據性別篩選模板
    
    - **gender**: 性別 (male, female, unisex)
    """
    try:
        valid_genders = {"male", "female", "unisex"}
        if gender not in valid_genders:
            raise HTTPException(
                status_code=400,
                detail=f"無效的性別參數，可用值：{', '.join(valid_genders)}"
            )
        
        filtered_templates = {}
        
        for template_id, template_info in TEMPLATE_CONFIG["TEMPLATES"].items():
            if template_info["gender"] == gender or template_info["gender"] == "unisex":
                # 檢查模板檔案是否存在
                try:
                    template_path = get_template_path(template_id)
                    file_exists = template_path.exists()
                except Exception:
                    file_exists = False
                
                if file_exists:
                    filtered_templates[template_id] = {
                        "id": template_info["id"],
                        "name": template_info["name"],
                        "description": template_info["description"],
                        "category": template_info["category"],
                        "gender": template_info["gender"],
                        "preview_url": f"/api/templates/{template_id}/preview"
                    }
        
        return {
            "success": True,
            "message": f"性別 {gender} 的模板獲取成功",
            "templates": filtered_templates,
            "count": len(filtered_templates)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"根據性別 {gender} 篩選模板失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"篩選模板失敗：{str(e)}"
        )

@router.get("/templates/search")
async def search_templates(
    q: str = None,
    category: str = None,
    gender: str = None
) -> Dict[str, Any]:
    """
    搜尋模板
    
    - **q**: 搜尋關鍵字（在名稱和描述中搜尋）
    - **category**: 分類篩選
    - **gender**: 性別篩選
    """
    try:
        filtered_templates = {}
        
        for template_id, template_info in TEMPLATE_CONFIG["TEMPLATES"].items():
            # 檢查模板檔案是否存在
            try:
                template_path = get_template_path(template_id)
                file_exists = template_path.exists()
            except Exception:
                file_exists = False
            
            if not file_exists:
                continue
            
            # 應用篩選條件
            if category and template_info["category"] != category:
                continue
            
            if gender and template_info["gender"] != gender and template_info["gender"] != "unisex":
                continue
            
            if q:
                search_text = f"{template_info['name']} {template_info['description']}".lower()
                if q.lower() not in search_text:
                    continue
            
            filtered_templates[template_id] = {
                "id": template_info["id"],
                "name": template_info["name"],
                "description": template_info["description"],
                "category": template_info["category"],
                "gender": template_info["gender"],
                "preview_url": f"/api/templates/{template_id}/preview"
            }
        
        return {
            "success": True,
            "message": "模板搜尋完成",
            "templates": filtered_templates,
            "count": len(filtered_templates),
            "filters": {
                "query": q,
                "category": category,
                "gender": gender
            }
        }
        
    except Exception as e:
        logger.error(f"搜尋模板失敗：{e}")
        raise HTTPException(
            status_code=500,
            detail=f"搜尋模板失敗：{str(e)}"
        )
