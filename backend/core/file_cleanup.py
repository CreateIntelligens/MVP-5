"""
檔案清理模組
自動清理過期的上傳檔案和結果檔案
"""
import os
import time
import asyncio
import logging
from pathlib import Path
from typing import List, Tuple
from datetime import datetime, timedelta

from .config import FILE_CLEANUP_CONFIG, UPLOADS_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)

class FileCleanupManager:
    """檔案清理管理器"""
    
    def __init__(self):
        self.config = FILE_CLEANUP_CONFIG
        self.uploads_dir = UPLOADS_DIR
        self.results_dir = RESULTS_DIR
        self.is_running = False
        
    def cleanup_old_files(self, directory: Path, max_age_seconds: int) -> Tuple[int, int]:
        """
        清理指定目錄中的過期檔案
        
        Args:
            directory: 要清理的目錄
            max_age_seconds: 檔案最大保留時間（秒）
            
        Returns:
            Tuple[清理的檔案數量, 清理的檔案大小(bytes)]
        """
        if not directory.exists():
            return 0, 0
            
        current_time = time.time()
        cleaned_count = 0
        cleaned_size = 0
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    # 檢查檔案年齡
                    file_age = current_time - file_path.stat().st_mtime
                    
                    if file_age > max_age_seconds:
                        try:
                            file_size = file_path.stat().st_size
                            file_path.unlink()
                            cleaned_count += 1
                            cleaned_size += file_size
                            logger.info(f"已清理過期檔案: {file_path.name} (年齡: {file_age/3600:.1f}小時)")
                        except Exception as e:
                            logger.error(f"清理檔案失敗 {file_path}: {e}")
                            
        except Exception as e:
            logger.error(f"清理目錄失敗 {directory}: {e}")
            
        return cleaned_count, cleaned_size
    
    def cleanup_excess_files(self, directory: Path, max_files: int) -> Tuple[int, int]:
        """
        清理超過數量限制的檔案（保留最新的）
        
        Args:
            directory: 要清理的目錄
            max_files: 最大檔案數量
            
        Returns:
            Tuple[清理的檔案數量, 清理的檔案大小(bytes)]
        """
        if not directory.exists():
            return 0, 0
            
        try:
            # 獲取所有檔案並按修改時間排序（最新的在前）
            files = []
            for file_path in directory.iterdir():
                if file_path.is_file():
                    files.append((file_path, file_path.stat().st_mtime))
            
            files.sort(key=lambda x: x[1], reverse=True)
            
            # 如果檔案數量超過限制，刪除最舊的
            if len(files) > max_files:
                files_to_delete = files[max_files:]
                cleaned_count = 0
                cleaned_size = 0
                
                for file_path, _ in files_to_delete:
                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleaned_count += 1
                        cleaned_size += file_size
                        # logger.info(f"已清理多餘檔案: {file_path.name}")
                    except Exception as e:
                        logger.error(f"清理檔案失敗 {file_path}: {e}")
                        
                return cleaned_count, cleaned_size
                
        except Exception as e:
            logger.error(f"清理多餘檔案失敗 {directory}: {e}")
            
        return 0, 0
    
    def get_directory_stats(self, directory: Path) -> dict:
        """獲取目錄統計資訊"""
        if not directory.exists():
            return {"file_count": 0, "total_size": 0, "oldest_file_age": 0}
            
        file_count = 0
        total_size = 0
        oldest_time = time.time()
        
        try:
            for file_path in directory.iterdir():
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size
                    oldest_time = min(oldest_time, file_path.stat().st_mtime)
                    
            oldest_age = time.time() - oldest_time if file_count > 0 else 0
            
        except Exception as e:
            logger.error(f"獲取目錄統計失敗 {directory}: {e}")
            return {"file_count": 0, "total_size": 0, "oldest_file_age": 0}
            
        return {
            "file_count": file_count,
            "total_size": total_size,
            "oldest_file_age": oldest_age
        }
    
    def cleanup_all(self) -> dict:
        """執行完整的檔案清理"""
        if not self.config["ENABLE_CLEANUP"]:
            logger.info("檔案清理已停用")
            return {"status": "disabled"}
            
        logger.info("開始執行檔案清理...")
        start_time = time.time()
        
        # 清理結果檔案
        result_age_cleaned, result_age_size = self.cleanup_old_files(
            self.results_dir, 
            self.config["RESULT_FILE_TTL"]
        )
        
        result_excess_cleaned, result_excess_size = self.cleanup_excess_files(
            self.results_dir,
            self.config["MAX_RESULT_FILES"]
        )
        
        # 清理上傳檔案
        upload_age_cleaned, upload_age_size = self.cleanup_old_files(
            self.uploads_dir,
            self.config["UPLOAD_FILE_TTL"]
        )
        
        upload_excess_cleaned, upload_excess_size = self.cleanup_excess_files(
            self.uploads_dir,
            self.config["MAX_UPLOAD_FILES"]
        )
        
        # 統計資訊
        total_cleaned = result_age_cleaned + result_excess_cleaned + upload_age_cleaned + upload_excess_cleaned
        total_size = result_age_size + result_excess_size + upload_age_size + upload_excess_size
        
        # 獲取清理後的目錄狀態
        results_stats = self.get_directory_stats(self.results_dir)
        uploads_stats = self.get_directory_stats(self.uploads_dir)
        
        cleanup_time = time.time() - start_time
        
        result = {
            "status": "completed",
            "cleanup_time": cleanup_time,
            "total_files_cleaned": total_cleaned,
            "total_size_cleaned": total_size,
            "results_directory": {
                "age_based_cleaned": result_age_cleaned,
                "excess_cleaned": result_excess_cleaned,
                "current_stats": results_stats
            },
            "uploads_directory": {
                "age_based_cleaned": upload_age_cleaned,
                "excess_cleaned": upload_excess_cleaned,
                "current_stats": uploads_stats
            }
        }
        
        logger.info(f"檔案清理完成: 清理了 {total_cleaned} 個檔案, "
                   f"釋放了 {total_size/1024/1024:.2f}MB 空間, "
                   f"耗時 {cleanup_time:.2f}秒")
        
        return result
    
    def cleanup_upload_file(self, file_path: Path) -> bool:
        """清理單個上傳檔案"""
        if not self.config["CLEANUP_AFTER_PROCESS"]:
            return False
            
        try:
            if file_path.exists():
                file_path.unlink()
                logger.info(f"已清理上傳檔案: {file_path.name}")
                return True
        except Exception as e:
            logger.error(f"清理上傳檔案失敗 {file_path}: {e}")
            
        return False
    
    async def start_periodic_cleanup(self):
        """啟動定期清理任務"""
        if not self.config["ENABLE_CLEANUP"]:
            return

        if self.is_running:
            return

        self.is_running = True
        interval = self.config["CLEANUP_INTERVAL"]

        try:
            while self.is_running:
                await asyncio.sleep(interval)
                if self.is_running:  # 再次檢查，防止在睡眠期間被停止
                    self.cleanup_all()
        except asyncio.CancelledError:
            pass  # 應用關閉時取消任務，靜默處理不記錄錯誤日誌
        except Exception as e:
            logger.error(f"定期清理任務錯誤: {e}")
        finally:
            self.is_running = False
    
    def stop_periodic_cleanup(self):
        """停止定期清理任務"""
        self.is_running = False
        logger.info("已停止定期清理任務")
    
    def format_size(self, size_bytes: int) -> str:
        """格式化檔案大小"""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f}KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/1024/1024:.1f}MB"
        else:
            return f"{size_bytes/1024/1024/1024:.1f}GB"

# 全域清理管理器實例
cleanup_manager = FileCleanupManager()

def get_cleanup_manager() -> FileCleanupManager:
    """獲取清理管理器實例"""
    return cleanup_manager

# 便捷函數
def cleanup_now() -> dict:
    """立即執行清理"""
    return cleanup_manager.cleanup_all()

def cleanup_upload_file(file_path: Path) -> bool:
    """清理上傳檔案"""
    return cleanup_manager.cleanup_upload_file(file_path)

def get_storage_stats() -> dict:
    """獲取儲存統計"""
    results_stats = cleanup_manager.get_directory_stats(RESULTS_DIR)
    uploads_stats = cleanup_manager.get_directory_stats(UPLOADS_DIR)
    
    return {
        "results": {
            **results_stats,
            "total_size_formatted": cleanup_manager.format_size(results_stats["total_size"])
        },
        "uploads": {
            **uploads_stats,
            "total_size_formatted": cleanup_manager.format_size(uploads_stats["total_size"])
        },
        "config": FILE_CLEANUP_CONFIG
    }
