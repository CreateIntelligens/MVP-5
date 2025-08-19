# AI 換臉應用

基於 InsightFace 的 AI 換臉應用，支援 GPU 加速與高效能處理。

## 🎯 功能特色

- **AI 換臉技術**：高品質換臉處理
- **多臉部支援**：支援多人照片換臉
- **自訂模板**：可上傳自訂模板
- **GPU 加速**：自動GPU/CPU切換
- **同步/非同步 API**：靈活的處理方式
- **長期儲存**：圖片保留31天

## 🚀 快速啟動

```bash
# 啟動服務
docker-compose up -d --build

# 查看日誌
docker-compose logs -f

# 停止服務  
docker-compose down
```

### GPU 版本（可選）

如有 NVIDIA GPU：
```bash
docker-compose -f docker-compose.gpu.yml up -d --build
```

### 訪問地址

- **應用**: http://localhost:8882
- **API文件**: http://localhost:8882/api/docs
- **系統狀態**: http://localhost:8882/api/system/info

## 📊 API 新增功能

### 原圖保存
- 所有 API 回應現在包含 `original_url` 欄位
- 原圖和結果圖均保留31天
- 支援獲取和刪除原圖: `/api/uploads/{filename}`

### GPU 支援  
- 自動檢測 GPU可用性
- GPU 失敗時自動切換 CPU
- 即時監控 GPU/CPU 狀態

### 高效能最佳化
- 間歇性突發流量優化 (2500請求/秒)
- 精簡化的部署與監控