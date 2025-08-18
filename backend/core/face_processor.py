"""
臉部處理核心模組
"""
import cv2
import numpy as np
from PIL import Image
import insightface
from insightface.app import FaceAnalysis
import uuid
import os
from pathlib import Path
from typing import Optional, Tuple, Union
import logging
import subprocess
import sys

from .config import MODEL_CONFIG, get_model_path, RESULTS_DIR

# 設定日誌
logger = logging.getLogger(__name__)

def check_gpu_availability():
    """檢查GPU是否可用"""
    try:
        import onnxruntime as ort
        # 檢查ONNX Runtime GPU支援
        gpu_providers = [provider for provider in ort.get_available_providers() 
                        if 'CUDA' in provider or 'GPU' in provider]
        
        if gpu_providers:
            logger.info(f"檢測到GPU Provider: {gpu_providers}")
            return True, gpu_providers[0]
        else:
            logger.info("未檢測到GPU Provider，將使用CPU")
            return False, 'CPUExecutionProvider'
            
    except ImportError:
        logger.warning("ONNX Runtime 未安裝，將使用CPU")
        return False, 'CPUExecutionProvider'
    except Exception as e:
        logger.warning(f"GPU檢測失敗: {e}，將使用CPU")
        return False, 'CPUExecutionProvider'

class FaceProcessor:
    """臉部處理器"""
    
    def __init__(self):
        """初始化臉部處理器"""
        self.face_app = None
        self.swapper = None
        self._initialize_models()
    
    def _initialize_models(self):
        """初始化 AI 模型"""
        try:
            logger.info("正在載入 AI 模型...")
            
            # 確保 InsightFace 版本
            assert insightface.__version__ >= '0.7', f"需要 InsightFace 0.7+，目前版本：{insightface.__version__}"
            
            # 檢查GPU可用性
            gpu_available, provider = check_gpu_availability()
            self.gpu_available = gpu_available
            
            # 設定計算設備
            if gpu_available:
                ctx_id = 0  # GPU
                logger.info("使用GPU模式")
            else:
                ctx_id = -1  # CPU
                logger.info("使用CPU模式")
            
            # 初始化臉部分析模型
            self.face_app = FaceAnalysis(name=MODEL_CONFIG["FACE_ANALYSIS_MODEL"])
            
            # 根據可用記憶體調整檢測尺寸
            import psutil
            available_memory = psutil.virtual_memory().available / (1024**3)  # GB
            
            if available_memory < 2:
                detection_size = (320, 320)  # 低記憶體
                logger.info("低記憶體模式：使用較小的檢測尺寸")
            elif available_memory < 4:
                detection_size = (480, 480)  # 中等記憶體
                logger.info("中等記憶體模式：使用標準檢測尺寸")
            else:
                detection_size = MODEL_CONFIG["DETECTION_SIZE"]  # 高記憶體
            
            self.face_app.prepare(
                ctx_id=ctx_id, 
                det_size=detection_size
            )
            
            # 初始化換臉模型
            model_path = get_model_path(MODEL_CONFIG["FACE_SWAP_MODEL"])
            if model_path.exists():
                self.swapper = insightface.model_zoo.get_model(str(model_path))
            else:
                # 如果本地沒有模型，嘗試下載
                logger.info("本地模型不存在，嘗試下載...")
                self.swapper = insightface.model_zoo.get_model(
                    MODEL_CONFIG["FACE_SWAP_MODEL"], 
                    download=True, 
                    download_zip=True
                )
            
            logger.info(f"AI 模型載入完成！(使用{'GPU' if gpu_available else 'CPU'}模式)")
            
        except Exception as e:
            # 如果GPU初始化失敗，嘗試CPU模式
            if hasattr(self, 'gpu_available') and self.gpu_available:
                logger.warning(f"GPU模式初始化失敗：{e}，嘗試CPU模式...")
                self.gpu_available = False
                self._initialize_cpu_fallback()
            else:
                logger.error(f"模型初始化失敗：{e}")
                raise RuntimeError(f"無法初始化 AI 模型：{e}")
    
    def _initialize_cpu_fallback(self):
        """CPU模式初始化（GPU失敗時的備用方案）"""
        try:
            logger.info("正在切換至CPU模式...")
            
            # 重新初始化臉部分析模型 (CPU模式)
            self.face_app = FaceAnalysis(name=MODEL_CONFIG["FACE_ANALYSIS_MODEL"])
            
            # 根據可用記憶體調整檢測尺寸
            import psutil
            available_memory = psutil.virtual_memory().available / (1024**3)  # GB
            
            if available_memory < 2:
                detection_size = (320, 320)  # 低記憶體
                logger.info("低記憶體模式：使用較小的檢測尺寸")
            elif available_memory < 4:
                detection_size = (480, 480)  # 中等記憶體
                logger.info("中等記憶體模式：使用標準檢測尺寸")
            else:
                detection_size = MODEL_CONFIG["DETECTION_SIZE"]  # 高記憶體
            
            self.face_app.prepare(
                ctx_id=-1,  # 強制使用CPU
                det_size=detection_size
            )
            
            # 重新初始化換臉模型
            model_path = get_model_path(MODEL_CONFIG["FACE_SWAP_MODEL"])
            if model_path.exists():
                self.swapper = insightface.model_zoo.get_model(str(model_path))
            else:
                logger.info("本地模型不存在，嘗試下載...")
                self.swapper = insightface.model_zoo.get_model(
                    MODEL_CONFIG["FACE_SWAP_MODEL"], 
                    download=True, 
                    download_zip=True
                )
            
            logger.info("CPU模式初始化完成！")
            
        except Exception as e:
            logger.error(f"CPU模式初始化失敗：{e}")
            raise RuntimeError(f"CPU模式也無法初始化：{e}")
    
    def detect_faces(self, image: np.ndarray) -> list:
        """
        偵測圖片中的臉部（使用多重策略）
        
        Args:
            image: OpenCV 格式的圖片 (BGR)
            
        Returns:
            list: 偵測到的臉部列表
        """
        try:
            # 第一次嘗試：使用原始圖片
            faces = self.face_app.get(image)
            if len(faces) > 0:
                # 按照臉部位置排序（從左到右）
                faces = sorted(faces, key=lambda x: x.bbox[0])
                logger.info(f"偵測到 {len(faces)} 張臉部")
                return faces
            
            # 第二次嘗試：調整圖片亮度和對比度
            logger.info("第一次偵測失敗，嘗試調整圖片亮度...")
            enhanced_image = self._enhance_image(image)
            faces = self.face_app.get(enhanced_image)
            if len(faces) > 0:
                faces = sorted(faces, key=lambda x: x.bbox[0])
                logger.info(f"調整亮度後偵測到 {len(faces)} 張臉部")
                return faces
            
            # 第三次嘗試：縮放圖片
            logger.info("第二次偵測失敗，嘗試縮放圖片...")
            resized_image = self._resize_image(image)
            faces = self.face_app.get(resized_image)
            if len(faces) > 0:
                # 將座標縮放回原始尺寸
                scale_factor = image.shape[0] / resized_image.shape[0]
                for face in faces:
                    face.bbox *= scale_factor
                    if hasattr(face, 'kps'):
                        face.kps *= scale_factor
                faces = sorted(faces, key=lambda x: x.bbox[0])
                logger.info(f"縮放後偵測到 {len(faces)} 張臉部")
                return faces
            
            logger.warning("所有偵測策略都失敗了")
            return []
            
        except Exception as e:
            logger.error(f"臉部偵測失敗：{e}")
            raise RuntimeError(f"臉部偵測失敗：{e}")
    
    def _enhance_image(self, image: np.ndarray) -> np.ndarray:
        """增強圖片亮度和對比度"""
        try:
            # 轉換為 LAB 色彩空間
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # 應用 CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            
            # 合併通道並轉回 BGR
            enhanced = cv2.merge([l, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            return enhanced
        except Exception as e:
            logger.warning(f"圖片增強失敗：{e}")
            return image
    
    def _resize_image(self, image: np.ndarray, target_size: int = 800) -> np.ndarray:
        """調整圖片大小"""
        try:
            height, width = image.shape[:2]
            
            # 如果圖片已經很小，就放大
            if max(height, width) < target_size:
                scale = target_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
            else:
                # 如果圖片太大，就縮小
                scale = target_size / max(height, width)
                new_width = int(width * scale)
                new_height = int(height * scale)
            
            resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            return resized
        except Exception as e:
            logger.warning(f"圖片縮放失敗：{e}")
            return image
    
    def swap_faces(
        self, 
        source_image: np.ndarray, 
        target_image: np.ndarray,
        source_face_index: int = 0,
        target_face_index: int = 0
    ) -> np.ndarray:
        """
        執行換臉操作
        
        Args:
            source_image: 來源圖片（提供臉部）
            target_image: 目標圖片（被替換臉部）
            source_face_index: 來源臉部索引
            target_face_index: 目標臉部索引
            
        Returns:
            np.ndarray: 換臉後的圖片
        """
        try:
            # 偵測來源圖片中的臉部
            source_faces = self.detect_faces(source_image)
            if len(source_faces) == 0:
                raise ValueError("在來源圖片中沒有偵測到臉部，請上傳清晰的正面照片")
            
            if source_face_index >= len(source_faces):
                raise ValueError(f"來源圖片只有 {len(source_faces)} 張臉，但指定了第 {source_face_index + 1} 張臉")
            
            source_face = source_faces[source_face_index]
            
            # 偵測目標圖片中的臉部
            target_faces = self.detect_faces(target_image)
            if len(target_faces) == 0:
                raise ValueError("在目標圖片中沒有偵測到臉部")
            
            if target_face_index >= len(target_faces):
                raise ValueError(f"目標圖片只有 {len(target_faces)} 張臉，但指定了第 {target_face_index + 1} 張臉")
            
            target_face = target_faces[target_face_index]
            
            try:
                # 執行換臉
                result = self.swapper.get(target_image, target_face, source_face, paste_back=True)
                logger.info(f"換臉處理完成 ({'GPU' if self.gpu_available else 'CPU'} 模式)")
                return result
                
            except Exception as swap_error:
                # 如果GPU模式失敗，嘗試切換到CPU模式重試
                if hasattr(self, 'gpu_available') and self.gpu_available:
                    logger.warning(f"GPU換臉失敗: {swap_error}，嘗試使用CPU模式...")
                    try:
                        # 重新初始化為CPU模式
                        self._initialize_cpu_fallback()
                        # 重新偵測臉部（因為模型已切換）
                        source_faces = self.detect_faces(source_image)
                        target_faces = self.detect_faces(target_image)
                        
                        if len(source_faces) > source_face_index and len(target_faces) > target_face_index:
                            source_face = source_faces[source_face_index]
                            target_face = target_faces[target_face_index]
                            result = self.swapper.get(target_image, target_face, source_face, paste_back=True)
                            logger.info("CPU模式換臉處理完成")
                            return result
                        else:
                            raise ValueError("切換到CPU模式後臉部偵測失敗")
                    except Exception as cpu_error:
                        logger.error(f"CPU模式也失敗了: {cpu_error}")
                        raise RuntimeError(f"GPU和CPU模式都失敗了。GPU錯誤: {swap_error}，CPU錯誤: {cpu_error}")
                else:
                    raise swap_error
            
        except Exception as e:
            logger.error(f"換臉處理失敗：{e}")
            raise RuntimeError(f"換臉處理失敗：{e}")
    
    def process_image_file(
        self, 
        user_image_data: bytes, 
        template_image_path: Union[str, Path],
        source_face_index: int = 0,
        target_face_index: int = 0
    ) -> str:
        """
        處理圖片檔案並執行換臉
        
        Args:
            user_image_data: 使用者圖片的二進位資料
            template_image_path: 模板圖片路徑
            source_face_index: 來源臉部索引
            target_face_index: 目標臉部索引
            
        Returns:
            str: 結果圖片的檔案路徑
        """
        try:
            # 解析使用者圖片
            user_image = self._decode_image(user_image_data)
            
            # 載入模板圖片
            template_image = self._load_template_image(template_image_path)
            
            # 執行換臉
            result_image = self.swap_faces(
                source_image=user_image,
                target_image=template_image,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
            
            # 儲存結果
            result_path = self._save_result(result_image)
            
            return result_path
            
        except Exception as e:
            logger.error(f"圖片處理失敗：{e}")
            raise
    
    def process_image_data(
        self, 
        user_image_data: bytes, 
        template_image_data: bytes,
        source_face_index: int = 0,
        target_face_index: int = 0
    ) -> str:
        """
        處理圖片資料並執行換臉（用於自訂模板）
        
        Args:
            user_image_data: 使用者圖片的二進位資料
            template_image_data: 模板圖片的二進位資料
            source_face_index: 來源臉部索引
            target_face_index: 目標臉部索引
            
        Returns:
            str: 結果圖片的檔案路徑
        """
        try:
            # 解析使用者圖片
            user_image = self._decode_image(user_image_data)
            
            # 解析模板圖片
            template_image = self._decode_image(template_image_data)
            
            # 執行換臉
            result_image = self.swap_faces(
                source_image=user_image,
                target_image=template_image,
                source_face_index=source_face_index,
                target_face_index=target_face_index
            )
            
            # 儲存結果
            result_path = self._save_result(result_image)
            
            return result_path
            
        except Exception as e:
            logger.error(f"圖片處理失敗：{e}")
            raise
    
    def _decode_image(self, image_data: bytes) -> np.ndarray:
        """解碼圖片資料"""
        try:
            # 從 bytes 轉換為 numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if image is None:
                raise ValueError("無法解析圖片資料")
            
            return image
            
        except Exception as e:
            raise ValueError(f"圖片解碼失敗：{e}")
    
    def _load_template_image(self, template_path: Union[str, Path]) -> np.ndarray:
        """載入模板圖片"""
        try:
            template_path = Path(template_path)
            if not template_path.exists():
                raise FileNotFoundError(f"模板圖片不存在：{template_path}")
            
            image = cv2.imread(str(template_path))
            if image is None:
                raise ValueError(f"無法載入模板圖片：{template_path}")
            
            return image
            
        except Exception as e:
            raise ValueError(f"模板圖片載入失敗：{e}")
    
    def _save_result(self, result_image: np.ndarray) -> str:
        """儲存處理結果"""
        try:
            # 生成唯一檔名
            result_filename = f"result_{uuid.uuid4().hex}.jpg"
            result_path = RESULTS_DIR / result_filename
            
            # 確保結果目錄存在
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            
            # 儲存圖片
            success = cv2.imwrite(str(result_path), result_image)
            if not success:
                raise RuntimeError("圖片儲存失敗")
            
            logger.info(f"結果已儲存：{result_path}")
            return str(result_path)
            
        except Exception as e:
            raise RuntimeError(f"結果儲存失敗：{e}")
    
    def get_face_count(self, image_data: bytes) -> int:
        """獲取圖片中的臉部數量"""
        try:
            image = self._decode_image(image_data)
            faces = self.detect_faces(image)
            return len(faces)
        except Exception as e:
            logger.error(f"臉部計數失敗：{e}")
            return 0
    
    def validate_image(self, image_data: bytes) -> dict:
        """驗證圖片並返回資訊"""
        try:
            image = self._decode_image(image_data)
            faces = self.detect_faces(image)
            
            height, width = image.shape[:2]
            
            return {
                "valid": True,
                "width": width,
                "height": height,
                "face_count": len(faces),
                "faces": [
                    {
                        "index": i,
                        "bbox": face.bbox.tolist(),
                        "confidence": float(face.det_score)
                    }
                    for i, face in enumerate(faces)
                ]
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e)
            }

# 全域處理器實例
_processor_instance = None

def get_face_processor() -> FaceProcessor:
    """獲取臉部處理器實例（單例模式）"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = FaceProcessor()
    return _processor_instance

def get_system_info() -> dict:
    """獲取系統資訊，包括GPU狀態"""
    try:
        import psutil
        gpu_available, provider = check_gpu_availability()
        
        # 獲取記憶體資訊
        memory = psutil.virtual_memory()
        
        # 嘗試獲取GPU資訊
        gpu_info = "N/A"
        if gpu_available:
            try:
                import GPUtil
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    gpu_info = f"{gpu.name} ({gpu.memoryTotal}MB)"
            except ImportError:
                gpu_info = "GPU可用但未安裝GPUtil"
            except Exception:
                gpu_info = "GPU可用但獲取資訊失敗"
        
        return {
            "gpu_available": gpu_available,
            "gpu_provider": provider,
            "gpu_info": gpu_info,
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "memory_percent": memory.percent,
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=1)
        }
        
    except Exception as e:
        logger.error(f"獲取系統資訊失敗：{e}")
        return {
            "gpu_available": False,
            "gpu_provider": "Unknown",
            "gpu_info": "獲取失敗",
            "error": str(e)
        }

def cleanup_old_results(max_age_hours: int = 24):
    """清理舊的結果檔案"""
    try:
        import time
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        for file_path in RESULTS_DIR.glob("result_*.jpg"):
            if current_time - file_path.stat().st_mtime > max_age_seconds:
                file_path.unlink()
                logger.info(f"已清理舊檔案：{file_path}")
                
    except Exception as e:
        logger.error(f"清理舊檔案失敗：{e}")
