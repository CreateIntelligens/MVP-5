# AI 換臉應用程式

基於 InsightFace 的 AI 換臉應用，支援前後端分離架構和 Docker 容器化部署。

## 🎯 功能特色

- **AI 換臉技術**：基於 InsightFace 的高品質換臉。
- **多臉部支援**：支援多人照片中指定臉部進行換臉。
- **自訂模板**：支援上傳自訂圖片作為換臉模板。
- **預設模板**：內建多款預設風格模板。
- **同步與非同步 API**：提供即時返回結果的同步 API 和用於處理耗時任務的非同步 API。
- **GPU 加速**：支援 NVIDIA GPU 進行硬體加速，大幅提升處理速度。

## 📋 環境前提

在開始之前，請確保您的系統已安裝以下軟體：

- **Docker**: [安裝指引](https://docs.docker.com/get-docker/)
- **Docker Compose**: 通常隨 Docker Desktop 一同安裝。

### GPU 版本額外要求

如果您希望使用 GPU 加速功能，還需滿足以下條件：
- 一張支援 CUDA 的 **NVIDIA GPU**。
- 已在您的主機上安裝對應的 **NVIDIA 驅動程式**。

---

## 🚀 快速開始

我們提供兩種基於 Docker Compose 的啟動模式：CPU 模式和 GPU 模式。

### 模式一：CPU 版本 (通用，無需 NVIDIA GPU)

此模式使用 CPU 進行 AI 運算，處理速度較慢，但無需特殊硬體。

```bash
# 啟動所有服務
docker-compose up -d --build

# 查看日誌
docker-compose logs -f

# 停止服務
docker-compose down
```

### 模式二：GPU 版本 (推薦，需 NVIDIA GPU)

此模式利用 NVIDIA GPU 進行硬體加速，處理速度極快。請確保您已滿足 GPU 版本的額外要求。

```bash
# 使用 GPU 設定檔啟動所有服務
docker-compose -f docker-compose.gpu.yml up -d --build

# 查看日誌
docker-compose -f docker-compose.gpu.yml logs -f

# 停止服務
docker-compose -f docker-compose.gpu.yml down
```

---

### 訪問應用

服務啟動後，您可以透過以下地址訪問：

- **前端應用**: [http://localhost:8882/](http://localhost:8882/)
- **API 文件**: [http://localhost:8882/docs](http://localhost:8882/docs) (Swagger UI)