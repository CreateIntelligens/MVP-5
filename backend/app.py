from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
import os
import asyncio
from pathlib import Path

# 導入 API 路由
from api.face_swap import router as face_swap_router
from api.templates import router as templates_router

# 導入配置和清理模組
from core.config import ensure_directories, FILE_CLEANUP_CONFIG, LOGGING_CONFIG
from core.file_cleanup import get_cleanup_manager, cleanup_now, get_storage_stats

# 設定日誌
import logging.config
logging.config.dictConfig(LOGGING_CONFIG)

# 建立 FastAPI 應用
app = FastAPI(
    title="AI 頭像工作室 API",
    description="基於 InsightFace 的 AI 換臉 API 服務",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生產環境中應該設定具體的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 確保必要目錄存在後再掛載靜態檔案服務
ensure_directories()
app.mount("/results", StaticFiles(directory="results"), name="results")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/models", StaticFiles(directory="models"), name="models")

# 註冊 API 路由
app.include_router(face_swap_router, prefix="/api", tags=["Face Swap"])
app.include_router(templates_router, prefix="/api", tags=["Templates"])

# 健康檢查端點
@app.get("/api/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "message": "AI 頭像工作室 API 運行正常",
        "version": "1.0.0"
    }

# 檔案清理相關端點
@app.post("/api/cleanup")
async def manual_cleanup():
    """手動執行檔案清理"""
    try:
        result = cleanup_now()
        return {
            "success": True,
            "message": "檔案清理完成",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清理失敗: {str(e)}")

@app.get("/api/storage/stats")
async def storage_statistics():
    """獲取儲存統計資訊"""
    try:
        stats = get_storage_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取統計失敗: {str(e)}")

# 根路徑
@app.get("/")
async def root():
    """根路徑資訊"""
    return {
        "message": "歡迎使用 AI 頭像工作室 API",
        "docs": "/api/docs",
        "health": "/api/health",
        "cleanup": "/api/cleanup",
        "storage_stats": "/api/storage/stats"
    }

# 啟動事件
@app.on_event("startup")
async def startup_event():
    """應用啟動時執行"""
    # 確保必要的目錄存在
    ensure_directories()
    
    # 檔案清理初始化
    cleanup_manager = get_cleanup_manager()
    
    # 啟動時清理（如果啟用）
    if FILE_CLEANUP_CONFIG["CLEANUP_ON_STARTUP"]:
        print("🧹 執行啟動清理...")
        cleanup_result = cleanup_now()
        if cleanup_result["status"] == "completed":
            print(f"✅ 清理完成: 清理了 {cleanup_result['total_files_cleaned']} 個檔案, "
                  f"釋放了 {cleanup_result['total_size_cleaned']/1024/1024:.2f}MB 空間")
    
    # 啟動定期清理任務
    if FILE_CLEANUP_CONFIG["ENABLE_CLEANUP"]:
        asyncio.create_task(cleanup_manager.start_periodic_cleanup())
        print(f"⏰ 定期清理已啟動，間隔: {FILE_CLEANUP_CONFIG['CLEANUP_INTERVAL']/3600:.1f}小時")
    
    # 測試 Redis 連接
    try:
        from core.redis_client import test_redis_connection, redis_client, TASK_KEY_PREFIX
        if test_redis_connection():
            print("✅ Redis 連接成功")

            # 清理孤兒任務（pending/processing 狀態的任務）
            print("🧹 正在檢查孤兒任務...")
            try:
                import json
                from datetime import datetime

                # 掃描所有任務
                task_keys = redis_client.keys(f"{TASK_KEY_PREFIX}*")
                orphan_count = 0

                for task_key in task_keys:
                    task_data = redis_client.get(task_key)
                    if task_data:
                        task = json.loads(task_data)
                        status = task.get("status")

                        # 如果任務是 pending 或 processing，標記為失敗
                        if status in ["pending", "processing"]:
                            task["status"] = "failed"
                            task["progress"] = 0
                            task["message"] = "系統重啟，任務已取消"
                            task["error"] = "Backend restarted while task was in progress"
                            task["failed_at"] = datetime.now().isoformat()

                            # 更新任務狀態
                            redis_client.setex(
                                task_key,
                                172800,  # 保持原有 TTL (48小時)
                                json.dumps(task, ensure_ascii=False)
                            )
                            orphan_count += 1

                if orphan_count > 0:
                    print(f"✅ 已清理 {orphan_count} 個孤兒任務")
                else:
                    print("✅ 沒有發現孤兒任務")

                # 重置佇列大小計數器
                from core.redis_client import QUEUE_SIZE_KEY, GPU_LOCK_KEY
                redis_client.set(QUEUE_SIZE_KEY, 0)
                print("✅ 佇列大小計數器已重置")

                # 清理 GPU 鎖 (避免舊鎖阻塞新任務)
                redis_client.delete(GPU_LOCK_KEY)
                print("✅ GPU 鎖已清理")

            except Exception as e:
                print(f"⚠️  清理孤兒任務失敗: {e}")
        else:
            print("⚠️  Redis 連接失敗,部分功能可能無法使用")
    except Exception as e:
        print(f"⚠️  Redis 初始化失敗: {e}")

    # 模型預熱
    print("🔥 正在預熱 AI 模型...")
    print("DEBUG: About to import get_face_processor")
    try:
        from core.face_processor import get_face_processor
        print("DEBUG: Import successful, calling get_face_processor()")
        processor = get_face_processor()
        print("DEBUG: get_face_processor() returned successfully")
        print("✅ AI 模型預熱完成")
    except Exception as e:
        print(f"⚠️  模型預熱失敗: {e}")
        import traceback
        traceback.print_exc()
        print("   首次請求時將進行模型初始化")

    print("DEBUG: About to print startup complete")
    print("🚀 AI 頭像工作室 API 啟動完成")
    print("📱 API 文檔：http://localhost:3001/api/docs")
    print("🔍 健康檢查：http://localhost:3001/api/health")
    print("🧹 手動清理：http://localhost:3001/api/cleanup")
    print("📊 儲存統計：http://localhost:3001/api/storage/stats")

# 關閉事件
@app.on_event("shutdown")
async def shutdown_event():
    """應用關閉時執行"""
    # 停止定期清理任務
    cleanup_manager = get_cleanup_manager()
    cleanup_manager.stop_periodic_cleanup()
    
    print("👋 AI 頭像工作室 API 已關閉")

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        log_level="info"
    )
