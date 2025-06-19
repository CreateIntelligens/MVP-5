// API 配置
const API_CONFIG = {
    // 後端 API 基礎 URL（通過 Nginx 代理）
    BASE_URL: '/api',
    
    // API 端點
    ENDPOINTS: {
        TEMPLATES: '/templates',
        FACE_SWAP: '/face-swap',
        RESULTS: '/results',
        HEALTH: '/health'
    },
    
    // 請求配置
    REQUEST: {
        TIMEOUT: 60000, // 60 秒超時
        HEADERS: {
            'Accept': 'application/json'
        }
    },
    
    // 檔案上傳配置
    UPLOAD: {
        MAX_SIZE: 10 * 1024 * 1024, // 10MB
        ALLOWED_TYPES: ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'],
        ALLOWED_EXTENSIONS: ['.jpg', '.jpeg', '.png', '.webp']
    },
    
    // UI 配置
    UI: {
        MESSAGE_DURATION: 5000, // 訊息顯示時間 5 秒
        ANIMATION_DURATION: 300 // 動畫持續時間
    }
};

// 模板配置
const TEMPLATE_CONFIG = {
    TEMPLATES: [
        {
            id: '1',
            name: '模板 1',
            description: '專業商務風格',
            color: '#2c3e50',
            image: 'assets/images/templates/step01.jpg'
        },
        {
            id: '2',
            name: '模板 2',
            description: '時尚潮流風格',
            color: '#e74c3c',
            image: 'assets/images/templates/step02.jpg'
        },
        {
            id: '3',
            name: '模板 3',
            description: '輕鬆休閒風格',
            color: '#3498db',
            image: 'assets/images/templates/step03.jpg'
        },
        {
            id: '4',
            name: '模板 4',
            description: '優雅知性風格',
            color: '#9b59b6',
            image: 'assets/images/templates/step04.jpg'
        },
        {
            id: '5',
            name: '模板 5',
            description: '活力運動風格',
            color: '#1abc9c',
            image: 'assets/images/templates/step05.jpg'
        },
        {
            id: '6',
            name: '模板 6',
            description: '青春學院風格',
            color: '#f39c12',
            image: 'assets/images/templates/step06.jpg'
        }
    ]
};

// 工具函數
const Utils = {
    // 建立完整的 API URL
    getApiUrl: (endpoint) => {
        return `${API_CONFIG.BASE_URL}${endpoint}`;
    },
    
    // 檢查檔案類型
    isValidFileType: (file) => {
        return API_CONFIG.UPLOAD.ALLOWED_TYPES.includes(file.type);
    },
    
    // 檢查檔案大小
    isValidFileSize: (file) => {
        return file.size <= API_CONFIG.UPLOAD.MAX_SIZE;
    },
    
    // 格式化檔案大小
    formatFileSize: (bytes) => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // 延遲函數
    delay: (ms) => {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    // 生成唯一 ID
    generateId: () => {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }
};

// 導出配置（如果在模組環境中）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        API_CONFIG,
        TEMPLATE_CONFIG,
        Utils
    };
}
