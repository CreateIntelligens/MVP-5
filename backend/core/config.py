"""
應用配置檔案
"""
import os
from pathlib import Path

# 基礎路徑
BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = BASE_DIR / "models"
UPLOADS_DIR = BASE_DIR / "uploads"
RESULTS_DIR = BASE_DIR / "results"

# API 配置
API_CONFIG = {
    "HOST": "0.0.0.0",
    "PORT": 3001,
    "RELOAD": True,
    "LOG_LEVEL": "info"
}

# CORS 配置
CORS_CONFIG = {
    "ALLOW_ORIGINS": ["*"],  # 生產環境應設定具體域名
    "ALLOW_CREDENTIALS": True,
    "ALLOW_METHODS": ["*"],
    "ALLOW_HEADERS": ["*"]
}

# 檔案上傳配置
UPLOAD_CONFIG = {
    "MAX_FILE_SIZE": 10 * 1024 * 1024,  # 10MB
    "ALLOWED_EXTENSIONS": {".jpg", ".jpeg", ".png", ".webp"},
    "ALLOWED_MIME_TYPES": {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp"
    }
}

# AI 模型配置
MODEL_CONFIG = {
    "FACE_ANALYSIS_MODEL": "buffalo_l",
    "FACE_SWAP_MODEL": "inswapper_128.onnx",
    "DETECTION_SIZE": (320, 320),  # 降低偵測尺寸提高成功率
    "CTX_ID": 0,  # CPU: -1, GPU: 0
    "DET_THRESH": 0.5,  # 降低偵測閾值
    "DET_SIZE": (640, 640),  # 備用偵測尺寸
    # GPU 相關設定
    "ENABLE_GPU": True,  # 是否啟用GPU支援
    "GPU_MEMORY_FRACTION": 0.8,  # GPU記憶體使用比例
    "GPU_PROVIDERS": [
        "CUDAExecutionProvider",
        "DirectMLExecutionProvider",  # Windows DirectML
        "OpenVINOExecutionProvider",  # Intel OpenVINO
        "CPUExecutionProvider"  # 備用CPU
    ],
    "GPU_FALLBACK_ENABLED": True,  # GPU失敗時是否自動切換CPU
}

# 模板配置
TEMPLATE_CONFIG = {
    "TEMPLATES": {
        "01": {
            "id": "01",
            "name": "模板 1",
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step01.jpg"
        },
        "02": {
            "id": "02", 
            "name": "模板 2",
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step02.jpg"
        },
        "03": {
            "id": "03",
            "name": "模板 3", 
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step03.jpg"
        },
        "04": {
            "id": "04",
            "name": "模板 4",
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex", 
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step04.jpg"
        },
        "05": {
            "id": "05",
            "name": "模板 5",
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step05.jpg"
        },
        "06": {
            "id": "06",
            "name": "模板 6",
            "description": "預設模板",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "主要人物",
                }
            ],
            "path": "./models/templates/step06.jpg"
        },
        "07": {
            "id": "07",
            "name": "模板 7",
            "description": "測試全家福",
            "category": "默認",
            "gender": "unisex",
            "faces": [
                {
                    "index": 0,
                    "name": "左1",
                },
                {
                    "index": 1,
                    "name": "左2",
                },
                {
                    "index": 2,
                    "name": "右2",
                },
                {
                    "index": 3,
                    "name": "右1",
                },
            ],
            "path": "./models/templates/4people.jpeg"
        },
        "kobe": {
            "id": "kobe",
            "name": "模板 7",
            "description": "kobe test",
            "category": "帥哥黑人",
            "gender": "male",
            "faces": [
                {
                    "index": 0,
                    "name": "kobe",
                }
            ],
            "path": "./models/templates/kobe.jpg"
        },
        "4": {
            "id": "wife",
            "name": "模板 8",
            "description": "犀利人妻",
            "category": "?",
            "gender": "?",
            "faces": [
                {
                    "index": 0,
                    "name": "左1",
                },
                {
                    "index": 1,
                    "name": "左2",
                },
                {
                    "index": 2,
                    "name": "左3",
                }
            ],
            "path": "./models/templates/犀利人妻.png"
        },
        "3": {
            "id": "love",
            "name": "模板 9",
            "description": "命中註定我愛你",
            "category": "?",
            "gender": "?",
            "faces": [
                {
                    "index": 0,
                    "name": "左1",
                },
                {
                    "index": 1,
                    "name": "阮經天",
                }
            ],
            "path": "./models/templates/命中註定.png"
        },
        "1": {
            "id": "play",
            "name": "模板 10",
            "description": "綜藝玩很大",
            "category": "?",
            "gender": "?",
            "faces": [
                {
                    "index": 1,
                    "name": "吳宗憲",
                },
            ],
            "path": "./models/templates/綜藝玩很大.png"
        },
        "2": {
            "id": "super",
            "name": "模板 11",
            "description": "超級夜總會",
            "category": "?",
            "gender": "?",
            "faces": [
                {
                    "index": 0,
                    "name": "許效舜",
                },
                {
                    "index": 1,
                    "name": "小燕?",
                },{
                    "index": 2,
                    "name": "鼻孔",
                }
            ],
            "path": "./models/templates/超級夜總會.png"
        },
    }
}

# 日誌配置
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["default"],
    },
}

# 安全配置
SECURITY_CONFIG = {
    "SECRET_KEY": os.getenv("SECRET_KEY", "your-secret-key-here"),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 30
}

# 快取配置
CACHE_CONFIG = {
    "REDIS_URL": os.getenv("REDIS_URL", "redis://localhost:6379"),
    "CACHE_TTL": 3600,  # 1 小時
    "MAX_CACHE_SIZE": 100  # 最大快取項目數
}

# 檔案清理配置
FILE_CLEANUP_CONFIG = {
    "ENABLE_CLEANUP": True,  # 是否啟用自動清理
    "RESULT_FILE_TTL": 31 * 24 * 3600,  # 結果檔案保留時間（秒）- 31天
    "UPLOAD_FILE_TTL": 31 * 24 * 3600,  # 上傳檔案保留時間（秒）- 31天
    "MAX_RESULT_FILES": 1000,  # 最大結果檔案數量（增加以支援長期儲存）
    "MAX_UPLOAD_FILES": 1000,  # 最大上傳檔案數量（增加以支援長期儲存）
    "CLEANUP_INTERVAL": 24 * 3600,  # 清理檢查間隔（秒）- 24小時
    "CLEANUP_ON_STARTUP": True,  # 啟動時是否清理
    "CLEANUP_AFTER_PROCESS": False,  # 處理完成後不立即清理上傳檔案（保留31天）
}

# 監控配置
MONITORING_CONFIG = {
    "ENABLE_METRICS": True,
    "METRICS_PATH": "/metrics",
    "HEALTH_CHECK_PATH": "/health"
}

# 環境變數
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"

# 資料庫配置（如果需要）
DATABASE_CONFIG = {
    "DATABASE_URL": os.getenv("DATABASE_URL", "sqlite:///./avatar_studio.db"),
    "ECHO": DEBUG
}


def get_model_path(model_name: str) -> Path:
    """獲取模型檔案路徑"""
    return MODELS_DIR / model_name


def get_template_path(template_id: str) -> Path:
    """獲取模板圖片路徑"""
    template = TEMPLATE_CONFIG["TEMPLATES"].get(template_id)
    if not template:
        raise ValueError(f"Template {template_id} not found")

    # 轉換相對路徑為絕對路徑
    template_path = template["path"]
    if template_path.startswith("./"):
        return BASE_DIR / template_path[2:]
    return Path(template_path)


def ensure_directories():
    """確保必要的目錄存在"""
    directories = [
        UPLOADS_DIR,
        RESULTS_DIR,
        MODELS_DIR,
        MODELS_DIR / "templates"
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def validate_config():
    """驗證配置"""
    # 檢查GPU支援
    if MODEL_CONFIG["ENABLE_GPU"]:
        try:
            import onnxruntime as ort
            gpu_providers = [p for p in ort.get_available_providers()
                             if any(gpu_name in p for gpu_name in ['CUDA', 'DirectML', 'OpenVINO'])]
            if gpu_providers:
                print(f"檢測到GPU Provider: {gpu_providers}")
            else:
                print("警告：未檢測到GPU Provider，將使用CPU模式")
        except ImportError:
            print("警告：ONNX Runtime 未安裝，無法使用GPU")

    # 檢查模型檔案是否存在
    model_path = get_model_path(MODEL_CONFIG["FACE_SWAP_MODEL"])
    if not model_path.exists():
        print(f"警告：AI 模型檔案不存在：{model_path}")

    # 檢查模板檔案
    for template_id, template in TEMPLATE_CONFIG["TEMPLATES"].items():
        try:
            template_path = get_template_path(template_id)
            if not template_path.exists():
                print(f"警告：模板檔案不存在：{template_path}")
        except Exception as e:
            print(f"警告：模板 {template_id} 配置錯誤：{e}")


# 初始化配置
if __name__ == "__main__":
    ensure_directories()
    validate_config()
    print("配置驗證完成")
