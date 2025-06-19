# 使用 Python 3.9 slim 基礎映像
FROM python:3.9-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    build-essential \
    g++ \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# 複製 requirements.txt 並安裝 Python 依賴
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 創建模型目錄並下載 AI 模型檔案
RUN mkdir -p /app/models && \
    echo "正在下載 AI 模型檔案..." && \
    (wget -O /app/models/inswapper_128.onnx \
     "https://huggingface.co/spaces/mkrzyzan/face-swap/resolve/main/inswapper_128.onnx" || \
     wget -O /app/models/inswapper_128.onnx \
     "https://github.com/facefusion/facefusion-assets/releases/download/models/inswapper_128.onnx") && \
    echo "AI 模型下載完成" && \
    ls -lh /app/models/

# 由於使用 volume 掛載，不需要 COPY 後端代碼
# 後端代碼會通過 docker-compose.yml 中的 volume 掛載

# 設定環境變數
ENV PYTHONPATH=/app
ENV ENVIRONMENT=development

# 暴露端口
EXPOSE 3001

# 啟動命令（會被 docker-compose.yml 中的 command 覆蓋）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
