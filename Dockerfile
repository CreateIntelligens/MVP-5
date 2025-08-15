# 使用 Ubuntu 20.04 基礎映像，相容性更好
FROM ubuntu:20.04

# 設定時區避免互動式安裝
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Taipei

# 安裝 Python 3.9 和系統依賴
RUN apt-get update && apt-get install -y \
    python3.9 \
    python3.9-distutils \
    python3.9-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 pip
RUN curl https://bootstrap.pypa.io/get-pip.py | python3.9

# 設定 Python 別名
RUN ln -s /usr/bin/python3.9 /usr/bin/python

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    libgl1 \
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

# 創建模型目錄（模型檔案由 docker-compose.yml 中的 model-downloader 服務下載）
RUN mkdir -p /app/{models,results,uploads}

# 由於使用 volume 掛載，不需要 COPY 後端代碼
# 後端代碼會通過 docker-compose.yml 中的 volume 掛載

# 設定環境變數
ENV PYTHONPATH=/app
ENV ENVIRONMENT=development

# 暴露端口
EXPOSE 3001

# 啟動命令（會被 docker-compose.yml 中的 command 覆蓋）
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "3001", "--reload"]
