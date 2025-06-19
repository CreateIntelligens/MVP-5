# AI 頭像工作室

基於 InsightFace 的 AI 換臉應用，支援前後端分離架構和 Docker 容器化部署。

## 🎯 功能特色

- **AI 換臉技術**：基於 InsightFace 的高品質換臉
- **多臉部支援**：支援多人照片中指定臉部換臉
- **自訂模板**：支援上傳自訂模板圖片
- **預設模板**：提供 6 個預設風格模板
- **即時預覽**：上傳後立即預覽效果
- **自動清理**：智能檔案管理，防止儲存空間爆滿

## 🚀 快速開始

### 使用 Docker Compose（推薦）

```bash
# 克隆專案
git clone <repository-url>
cd ai-avatar-studio

# 啟動服務（會自動下載 AI 模型）
docker-compose up -d

# 訪問應用
# 前端：http://localhost:8882/faceswap/
# API 文檔：http://localhost:8882/faceswap/api
```

### 📦 自動模型下載

Docker 容器會在首次建置時自動下載 AI 模型檔案 `inswapper_128.onnx`（529MB）：

- **主要來源**：Hugging Face
- **備用來源**：GitHub Releases
- **自動重試**：如果主要來源失敗，會自動嘗試備用來源
- **無需手動操作**：完全自動化，無需額外步驟

**如果自動下載失敗，可以使用以下備用方案：**

1. **從 Hugging Face 克隆整個專案**（推薦）：
   ```bash
   # 克隆包含模型的完整專案
   git clone https://huggingface.co/spaces/mkrzyzan/face-swap temp-model
   
   # 複製模型檔案到正確位置
   cp temp-model/inswapper_128.onnx backend/models/
   
   # 清理臨時目錄
   rm -rf temp-model
   ```

2. **手動下載**：
   - 下載連結：https://huggingface.co/spaces/mkrzyzan/face-swap/resolve/main/inswapper_128.onnx
   - 將檔案放置到：`backend/models/inswapper_128.onnx`

3. **其他來源**：
   - GitHub Releases：https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx
   - 其他 InsightFace 相關專案

### 本地開發

#### 後端設置

```bash
cd backend

# 安裝依賴
pip install -r requirements.txt

# 啟動後端服務
python app.py
```

#### 前端設置

```bash
cd frontend

# 使用任何 HTTP 伺服器，例如：
python -m http.server 8882
# 然後訪問 http://localhost:8882

# 注意：建議使用 Docker Compose 進行開發
# 本地開發需要手動配置前後端連接
```

## 📋 API 文檔

詳細的 API 文檔請訪問：[http://localhost:8882/faceswap/api](http://localhost:8882/faceswap/api)

### 主要 API 端點

| 方法 | 端點 | 描述 |
|------|------|------|
| POST | `/api/face-swap` | 執行換臉操作 |
| POST | `/api/validate-image` | 驗證圖片並返回臉部資訊 |
| GET | `/api/templates` | 獲取可用模板列表 |
| GET | `/api/health` | 健康檢查 |
| POST | `/api/cleanup` | 手動執行檔案清理 |
| GET | `/api/storage/stats` | 獲取儲存統計資訊 |

## 🛠️ 技術架構

### 前端
- **純 HTML/CSS/JavaScript**：無框架依賴
- **響應式設計**：支援桌面和行動裝置
- **模組化架構**：CSS 和 JS 分離

### 後端
- **FastAPI**：高效能 Python Web 框架
- **InsightFace**：AI 臉部識別和換臉
- **自動清理**：智能檔案生命週期管理
- **RESTful API**：標準化 API 設計

### 容器化
- **Docker Compose**：一鍵部署
- **Volume 掛載**：開發模式熱重載
- **Nginx**：前端靜態檔案服務

## 📁 專案結構

```
ai-avatar-studio/
├── frontend/                 # 前端代碼
│   ├── index.html           # 主頁面
│   ├── assets/
│   │   ├── css/main.css     # 樣式檔案
│   │   ├── js/main.js       # 主要邏輯
│   │   └── images/          # 圖片資源
│   └── config.js            # 前端配置
├── backend/                 # 後端代碼
│   ├── app.py              # FastAPI 主應用
│   ├── requirements.txt    # Python 依賴
│   ├── api/                # API 路由
│   │   ├── face_swap.py    # 換臉 API
│   │   └── templates.py    # 模板 API
│   ├── core/               # 核心邏輯
│   │   ├── config.py       # 配置管理
│   │   ├── face_processor.py # 臉部處理
│   │   └── file_cleanup.py # 檔案清理
│   ├── models/             # AI 模型和模板
│   ├── uploads/            # 上傳檔案（臨時）
│   └── results/            # 處理結果
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile             # Docker 映像配置
├── nginx.conf             # Nginx 配置
└── README.md              # 專案說明
```

## ⚙️ 配置說明

### 檔案清理配置

系統會自動清理過期檔案，防止儲存空間爆滿：

- **結果檔案**：24 小時後自動清理
- **上傳檔案**：1 小時後自動清理
- **數量限制**：結果檔案最多 50 個，上傳檔案最多 20 個
- **清理頻率**：每小時自動檢查一次

### 環境變數

```bash
# 開發環境
ENVIRONMENT=development
DEBUG=true
API_HOST=localhost
API_PORT=3001

# 生產環境
ENVIRONMENT=production
DEBUG=false
```

## 🔧 開發指南

### 添加新的 API 端點

1. 在 `backend/api/` 目錄下創建或修改路由檔案
2. 在 `backend/app.py` 中註冊新的路由
3. 更新 API 文檔

### 修改前端界面

1. 編輯 `frontend/assets/css/main.css` 修改樣式
2. 編輯 `frontend/assets/js/main.js` 修改邏輯
3. 編輯 `frontend/index.html` 修改結構

### 添加新的模板

1. 將模板圖片放入 `backend/models/templates/`
2. 同時放入 `frontend/assets/images/templates/`
3. 更新 `backend/core/config.py` 中的 `TEMPLATE_CONFIG`

## 🚀 部署說明

### Docker 部署（推薦）

```bash
# 生產環境部署
docker compose up 

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 傳統部署

1. 設置 Python 環境並安裝依賴
2. 配置 Nginx 服務前端靜態檔案
3. 使用 Gunicorn 或 Uvicorn 運行後端
4. 設置反向代理和 SSL

## 🔍 故障排除

### 常見問題

**Q: 換臉失敗，提示找不到臉部**
A: 確保上傳的圖片清晰，臉部正面且光線充足

**Q: 處理時間過長**
A: 檢查圖片大小，建議使用小於 5MB 的圖片

**Q: Docker 啟動失敗**
A: 檢查端口是否被佔用，確保 Docker 服務正常運行

### 日誌查看

```bash
# Docker 日誌
docker-compose logs backend
docker-compose logs frontend

# 本地開發日誌
# 後端日誌會直接輸出到控制台
```

## 📊 監控和維護

### 儲存空間監控

訪問 `/api/storage/stats` 查看當前儲存使用情況：

```json
{
  "results": {
    "file_count": 15,
    "total_size": 52428800,
    "total_size_formatted": "50.0MB"
  },
  "uploads": {
    "file_count": 3,
    "total_size": 10485760,
    "total_size_formatted": "10.0MB"
  }
}
```

### 手動清理

```bash
# 通過 nginx 代理訪問 API
curl -X POST http://localhost:8882/api/cleanup

# 或訪問 API 文檔進行操作
http://localhost:8882/faceswap/api
```

## 📄 授權

本專案採用 MIT 授權條款。

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request 來改進這個專案。

---

**注意**：本專案僅供學習和研究使用，請勿用於非法用途。
