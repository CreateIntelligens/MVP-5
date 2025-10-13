// 全域變數
let selectedFile = null;
let selectedTemplate = null;
let customTemplate = null;
let isProcessing = false;

// DOM 元素
const elements = {
    uploadArea: null,
    fileInput: null,
    preview: null,
    templatesGrid: null,
    resultArea: null,
    processBtn: null,
    loadingOverlay: null,
    message: null
};

// 初始化應用
document.addEventListener('DOMContentLoaded', function() {
    initializeElements();
    initializeEventListeners();
    initializeTabSwitching();
    initializeEventLog();
    loadTemplates();
    checkApiHealth();
});

// 初始化 DOM 元素
function initializeElements() {
    elements.uploadArea = document.getElementById('uploadArea');
    elements.fileInput = document.getElementById('fileInput');
    elements.preview = document.getElementById('preview');
    elements.templatesGrid = document.getElementById('templatesGrid');
    elements.resultArea = document.getElementById('resultArea');
    elements.processBtn = document.getElementById('processBtn');
    elements.loadingOverlay = document.getElementById('loadingOverlay');
    elements.message = document.getElementById('message');
    elements.uploadContent = document.getElementById('uploadContent');
    elements.uploadPreview = document.getElementById('uploadPreview');
    elements.previewImage = document.getElementById('previewImage');
    elements.removeBtn = document.getElementById('removeBtn');
    
    // 模板上傳相關元素
    elements.templateUploadArea = document.getElementById('templateUploadArea');
    elements.templateFileInput = document.getElementById('templateFileInput');
    elements.templateUploadContent = document.getElementById('templateUploadContent');
    elements.templateUploadPreview = document.getElementById('templateUploadPreview');
    elements.templatePreviewImage = document.getElementById('templatePreviewImage');
    elements.templateRemoveBtn = document.getElementById('templateRemoveBtn');
}

// 初始化事件監聽器
function initializeEventListeners() {
    // 檔案上傳事件
    elements.uploadArea.addEventListener('click', (e) => {
        // 如果點擊的是取消按鈕，不觸發檔案選擇
        if (e.target.closest('.remove-btn')) {
            return;
        }
        elements.fileInput.click();
    });
    
    elements.fileInput.addEventListener('change', handleFileSelect);
    
    // 使用事件委託來處理取消按鈕（因為按鈕是動態創建的）
    elements.uploadArea.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-btn')) {
            handleRemoveImage(e);
        }
    });
    
    // 拖拽上傳事件
    elements.uploadArea.addEventListener('dragover', handleDragOver);
    elements.uploadArea.addEventListener('dragleave', handleDragLeave);
    elements.uploadArea.addEventListener('drop', handleDrop);
    
    // 模板上傳事件
    if (elements.templateUploadArea) {
        elements.templateUploadArea.addEventListener('click', (e) => {
            if (e.target.closest('.remove-btn')) {
                return;
            }
            elements.templateFileInput.click();
        });
        
        elements.templateFileInput.addEventListener('change', handleTemplateFileSelect);
        
        // 模板上傳拖拽事件
        elements.templateUploadArea.addEventListener('dragover', handleTemplateDragOver);
        elements.templateUploadArea.addEventListener('dragleave', handleTemplateDragLeave);
        elements.templateUploadArea.addEventListener('drop', handleTemplateDrop);
        
        // 模板取消按鈕事件
        elements.templateUploadArea.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-btn')) {
                handleRemoveTemplate(e);
            }
        });
    }
    
    // 處理按鈕事件
    elements.processBtn.addEventListener('click', handleProcessImage);
    
    // 防止頁面預設拖拽行為
    document.addEventListener('dragover', (e) => e.preventDefault());
    document.addEventListener('drop', (e) => e.preventDefault());
}

// 載入模板
function loadTemplates() {
    const templatesHtml = TEMPLATE_CONFIG.TEMPLATES.map(template => `
        <div class="template-item" data-template-id="${template.id}">
            <input type="radio" name="template" value="${template.id}" id="template${template.id}">
            <label for="template${template.id}">
                <div class="template-preview">
                    <img src="${template.image}" alt="${template.name}">
                </div>
            </label>
            <div class="template-name">${template.name}</div>
        </div>
    `).join('');
    
    elements.templatesGrid.innerHTML = templatesHtml;
    
    // 添加模板選擇事件
    elements.templatesGrid.addEventListener('change', handleTemplateSelect);
    elements.templatesGrid.addEventListener('click', handleTemplateClick);
}

// 檢查 API 健康狀態
async function checkApiHealth() {
    try {
        const response = await fetch(Utils.getApiUrl(API_CONFIG.ENDPOINTS.HEALTH));
        if (response.ok) {
            console.log('API 連接正常');
        } else {
            showMessage('API 連接異常，請檢查後端服務', 'error');
        }
    } catch (error) {
        console.warn('無法連接到後端 API:', error);
        showMessage('無法連接到後端服務，請確認後端已啟動', 'error');
    }
}

// 處理檔案選擇
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        validateAndPreviewFile(file);
    }
}

// 處理拖拽懸停
function handleDragOver(event) {
    event.preventDefault();
    elements.uploadArea.classList.add('dragover');
}

// 處理拖拽離開
function handleDragLeave(event) {
    event.preventDefault();
    elements.uploadArea.classList.remove('dragover');
}

// 處理拖拽放下
function handleDrop(event) {
    event.preventDefault();
    elements.uploadArea.classList.remove('dragover');
    
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        validateAndPreviewFile(files[0]);
    }
}

// 驗證並預覽檔案
function validateAndPreviewFile(file) {
    // 檢查檔案類型
    if (!Utils.isValidFileType(file)) {
        showMessage('不支援的檔案格式，請上傳 JPG、PNG 或 WebP 格式的圖片', 'error');
        return;
    }
    
    // 檢查檔案大小
    if (!Utils.isValidFileSize(file)) {
        showMessage(`檔案過大，請上傳小於 ${Utils.formatFileSize(API_CONFIG.UPLOAD.MAX_SIZE)} 的圖片`, 'error');
        return;
    }
    
    selectedFile = file;
    previewImage(file);
    updateProcessButton();
    
    showMessage('圖片上傳成功！', 'success');
}

// 預覽圖片
function previewImage(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        // 隱藏上傳提示文字
        if (elements.uploadContent) {
            elements.uploadContent.style.display = 'none';
        }
        
        // 顯示預覽圖片和取消按鈕
        if (elements.uploadPreview && elements.previewImage) {
            elements.previewImage.src = e.target.result;
            elements.uploadPreview.style.display = 'flex';
        }
        
        // 下方只顯示檔案資訊
        elements.preview.innerHTML = `
            <p>檔案：${file.name}</p>
            <p>大小：${Utils.formatFileSize(file.size)}</p>
        `;
    };
    reader.readAsDataURL(file);
}

// 處理模板選擇
function handleTemplateSelect(event) {
    if (event.target.type === 'radio') {
        selectedTemplate = event.target.value;
        customTemplate = null; // 清除自訂模板
        
        // 清除自訂模板預覽
        if (elements.templateUploadPreview) {
            elements.templateUploadPreview.style.display = 'none';
        }
        if (elements.templateUploadContent) {
            elements.templateUploadContent.style.display = 'block';
        }
        
        updateTemplateSelection();
        updateProcessButton();
        
        const templateName = TEMPLATE_CONFIG.TEMPLATES.find(t => t.id === selectedTemplate)?.name;
        showMessage(`已選擇模板：${templateName}`, 'info');
    }
}

// 處理模板點擊
function handleTemplateClick(event) {
    const templateItem = event.target.closest('.template-item');
    if (templateItem) {
        const radio = templateItem.querySelector('input[type="radio"]');
        if (radio) {
            radio.checked = true;
            
            // 手動觸發選擇邏輯
            selectedTemplate = radio.value;
            customTemplate = null; // 清除自訂模板
            
            // 將選中的模板圖片顯示在自訂模板區域
            const template = TEMPLATE_CONFIG.TEMPLATES.find(t => t.id === selectedTemplate);
            if (template && elements.templateUploadPreview && elements.templatePreviewImage) {
                // 隱藏上傳提示
                if (elements.templateUploadContent) {
                    elements.templateUploadContent.style.display = 'none';
                }
                
                // 顯示選中的模板圖片
                elements.templatePreviewImage.src = template.image;
                elements.templateUploadPreview.style.display = 'flex';
            }
            
            updateTemplateSelection();
            updateProcessButton();
            
            const templateName = template?.name;
            showMessage(`已選擇模板：${templateName}`, 'info');
        }
    }
}

// 更新模板選擇狀態
function updateTemplateSelection() {
    document.querySelectorAll('.template-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    if (selectedTemplate) {
        const selectedItem = document.querySelector(`[data-template-id="${selectedTemplate}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }
    }
}

// 更新處理按鈕狀態
function updateProcessButton() {
    const canProcess = selectedFile && selectedTemplate && !isProcessing;
    elements.processBtn.disabled = !canProcess;
    
    if (canProcess) {
        elements.processBtn.textContent = '🚀 開始處理';
    } else if (isProcessing) {
        elements.processBtn.textContent = '⏳ 處理中...';
    } else {
        elements.processBtn.textContent = '🚀 開始處理';
    }
}

// 處理圖片換臉
async function handleProcessImage() {
    if (!selectedFile || !selectedTemplate || isProcessing) {
        return;
    }
    
    isProcessing = true;
    updateProcessButton();
    showProgressInResult(true);
    
    // 添加處理狀態
    const templateName = selectedTemplate === 'custom' ? '自訂模板' : 
        TEMPLATE_CONFIG.TEMPLATES.find(t => t.id === selectedTemplate)?.name || '未知模板';
    const statusId = addStatusItem('AI 換臉處理', `使用模板：${templateName}`, 'processing');
    
    try {
        // 設置任務開始時間
        window.taskStartTime = Date.now();
        
        // 提交任務
        const taskResult = await submitFaceSwapTask(selectedFile, selectedTemplate);
        const taskId = taskResult.task_id;
        
        // 更新狀態顯示任務ID
        updateStatusItem(statusId, {
            description: `任務已提交 (ID: ${taskId.substring(0, 8)}...)，正在處理...`
        });
        
        // 開始輪詢任務狀態
        const result = await pollTaskStatus(taskId, statusId);
        
        // 更新狀態為完成
        updateStatusItem(statusId, {
            type: 'completed',
            resultUrl: result.result_url,
            templateName: result.template_name,
            description: `完成！使用模板：${result.template_name}`
        });
        
        showResult(result);
        cleanupStatusItems();
    } catch (error) {
        console.error('換臉處理失敗:', error);
        
        // 更新狀態為錯誤
        updateStatusItem(statusId, {
            type: 'error',
            description: `失敗：${error.message}`
        });
        
        showMessage(`換臉失敗：${error.message}`, 'error');
        showProgressInResult(false);
    } finally {
        isProcessing = false;
        updateProcessButton();
    }
}

// 提交換臉任務（帶重試機制）
async function submitFaceSwapTask(file, templateId, retryCount = 0) {
    const formData = new FormData();
    formData.append('file', file);
    
    // 如果是自訂模板，上傳模板檔案；否則使用模板 ID
    if (templateId === 'custom' && customTemplate) {
        formData.append('template_file', customTemplate);
        formData.append('template_id', 'custom');
    } else {
        formData.append('template_id', templateId);
    }
    
    // 添加臉部索引參數（從 1-based 轉換為 0-based）
    const sourceFaceInput = document.getElementById('sourceFaceIndex')?.value || '1';
    const targetFaceInput = document.getElementById('targetFaceIndex')?.value || '1';
    const sourceFaceIndex = Math.max(0, parseInt(sourceFaceInput) - 1);
    const targetFaceIndex = Math.max(0, parseInt(targetFaceInput) - 1);
    formData.append('source_face_index', sourceFaceIndex.toString());
    formData.append('target_face_index', targetFaceIndex.toString());
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.REQUEST.TIMEOUT);
    
    try {
        const response = await fetch(Utils.getApiUrl(API_CONFIG.ENDPOINTS.FACE_SWAP), {
            method: 'POST',
            body: formData,
            signal: controller.signal,
            headers: {
                // 不設定 Content-Type，讓瀏覽器自動設定 multipart/form-data
            }
        });
        
        clearTimeout(timeoutId);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));

            // 特殊處理 503 佇列已滿錯誤
            if (response.status === 503 && errorData.detail) {
                const detail = errorData.detail;

                // 如果是結構化的錯誤訊息
                if (typeof detail === 'object' && detail.error === 'queue_full') {
                    throw new Error('系統繁忙，佇列已滿，請稍後再試');
                }

                // 如果是字串格式的錯誤
                throw new Error(typeof detail === 'string' ? detail : detail.message || '系統繁忙，請稍後再試');
            }

            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        return result;
        
    } catch (error) {
        clearTimeout(timeoutId);
        
        // 如果是超時錯誤且還有重試次數，則重試
        if ((error.name === 'AbortError' || error.message.includes('timeout')) && 
            retryCount < API_CONFIG.REQUEST.MAX_RETRIES) {
            
            console.log(`任務提交失敗，${API_CONFIG.REQUEST.RETRY_DELAY / 1000}秒後進行第${retryCount + 1}次重試...`);
            
            // 等待重試延遲
            await Utils.delay(API_CONFIG.REQUEST.RETRY_DELAY);
            
            // 遞歸重試
            return submitFaceSwapTask(file, templateId, retryCount + 1);
        }
        
        if (error.name === 'AbortError') {
            throw new Error(`任務提交超時，已重試 ${retryCount} 次，請稍後再試`);
        }
        
        throw error;
    }
}

// 輪詢任務狀態
async function pollTaskStatus(taskId, statusId) {
    const startTime = Date.now();
    const maxPollTime = API_CONFIG.REQUEST.MAX_POLL_TIME;
    const pollInterval = API_CONFIG.REQUEST.POLL_INTERVAL;
    
    while (Date.now() - startTime < maxPollTime) {
        try {
            const response = await fetch(Utils.getApiUrl(`${API_CONFIG.ENDPOINTS.FACE_SWAP_STATUS}/${taskId}`));
            
            if (!response.ok) {
                throw new Error(`查詢狀態失敗: ${response.status}`);
            }
            
            const result = await response.json();
            const taskStatus = result.task_status;
            
            // 更新進度顯示
            updateTaskProgress(taskStatus, statusId);
            
            if (taskStatus.status === 'completed') {
                return taskStatus;
            } else if (taskStatus.status === 'failed') {
                throw new Error(taskStatus.error || '任務處理失敗');
            }
            
            // 等待下次輪詢
            await Utils.delay(pollInterval);
            
        } catch (error) {
            console.error('輪詢任務狀態失敗:', error);
            throw error;
        }
    }
    
    throw new Error('任務處理超時，請稍後查看結果或重新提交');
}

// 更新任務進度
function updateTaskProgress(taskStatus, statusId) {
    // 更新結果區域進度
    updateResultProgress(taskStatus.progress, taskStatus.message);
    
    // 更新狀態項目
    updateStatusItem(statusId, {
        description: `${taskStatus.message} (${taskStatus.progress}%)`
    });
}

// 更新結果區域進度
function updateResultProgress(progress, message) {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const progressTime = document.getElementById('progressTime');
    
    if (progressFill) {
        progressFill.style.width = `${progress}%`;
    }
    
    if (progressText) {
        progressText.textContent = message;
    }
    
    if (progressTime) {
        const elapsed = Math.floor((Date.now() - (window.taskStartTime || Date.now())) / 1000);
        progressTime.textContent = `處理時間：${elapsed}s`;
    }
    
    // 更新步驟狀態
    updateStepsByProgress(progress);
}

// 根據進度更新步驟狀態
function updateStepsByProgress(progress) {
    if (progress >= 10 && progress < 30) {
        updateStep(1, 'completed');
        updateStep(2, 'active');
    } else if (progress >= 30 && progress < 50) {
        updateStep(2, 'completed');
        updateStep(3, 'active');
    } else if (progress >= 50 && progress < 90) {
        updateStep(3, 'completed');
        updateStep(4, 'active');
    } else if (progress >= 90) {
        updateStep(4, 'completed');
    }
}

// 在結果區域顯示進度
function showProgressInResult(show) {
    if (show) {
        elements.resultArea.innerHTML = `
            <div class="progress-container">
                <div class="progress-steps">
                    <div class="progress-step active" id="step1">
                        <span class="step-icon">📤</span>
                        <span>步驟 1：上傳圖片</span>
                    </div>
                    <div class="progress-step" id="step2">
                        <span class="step-icon">🔍</span>
                        <span>步驟 2：臉部偵測</span>
                    </div>
                    <div class="progress-step" id="step3">
                        <span class="step-icon">🎭</span>
                        <span>步驟 3：AI 換臉處理</span>
                    </div>
                    <div class="progress-step" id="step4">
                        <span class="step-icon">✨</span>
                        <span>步驟 4：生成結果</span>
                    </div>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="progress-text" id="progressText">正在準備處理...</div>
                <div class="progress-time" id="progressTime">首次使用可能需要較長時間進行模型初始化</div>
            </div>
        `;
        startResultProgressTimer();
    } else {
        stopResultProgressTimer();
        elements.resultArea.innerHTML = '<p class="placeholder">處理結果將在這裡顯示</p>';
    }
}

// 結果區域進度計時器
let resultProgressTimer = null;
let resultProgressSeconds = 0;
let currentStep = 1;

function startResultProgressTimer() {
    resultProgressSeconds = 0;
    currentStep = 1;
    updateResultProgress();
    
    resultProgressTimer = setInterval(() => {
        resultProgressSeconds++;
        updateResultProgress();
    }, 1000);
}

function stopResultProgressTimer() {
    if (resultProgressTimer) {
        clearInterval(resultProgressTimer);
        resultProgressTimer = null;
    }
}

function updateResultProgress() {
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const progressTime = document.getElementById('progressTime');
    
    if (!progressFill || !progressText || !progressTime) return;
    
    // 動態進度條（基於時間但不設上限）
    const progress = Math.min(95, Math.log(resultProgressSeconds + 1) * 20);
    progressFill.style.width = `${progress}%`;
    
    // 更新步驟狀態
    if (resultProgressSeconds >= 3 && currentStep < 2) {
        updateStep(1, 'completed');
        updateStep(2, 'active');
        currentStep = 2;
        progressText.textContent = '正在偵測臉部特徵...';
    } else if (resultProgressSeconds >= 10 && currentStep < 3) {
        updateStep(2, 'completed');
        updateStep(3, 'active');
        currentStep = 3;
        progressText.textContent = 'AI 正在進行換臉處理...';
    } else if (resultProgressSeconds >= 30 && currentStep < 4) {
        updateStep(3, 'completed');
        updateStep(4, 'active');
        currentStep = 4;
        progressText.textContent = '正在生成最終結果...';
    }
    
    // 更新時間顯示（累計時間 + 首次使用提示）
    let timeMessage = `處理時間：${resultProgressSeconds}s`;
    
    if (resultProgressSeconds <= 60) {
        timeMessage += ' (首次使用可能需要較長時間進行模型初始化)';
    } else if (resultProgressSeconds <= 120) {
        timeMessage += ' (正在處理中，請耐心等候)';
    } else {
        timeMessage += ' (處理時間較長，但系統正在運行中)';
    }
    
    progressTime.textContent = timeMessage;
}

function updateStep(stepNumber, status) {
    const step = document.getElementById(`step${stepNumber}`);
    if (step) {
        step.className = `progress-step ${status}`;
    }
}

// 顯示處理結果
function showResult(result) {
    stopResultProgressTimer();
    
    const resultUrl = result.result_url;
    const templateName = result.template_name;
    
    elements.resultArea.innerHTML = `
        <div class="result-content">
            <img src="${resultUrl}" class="result-image" alt="換臉結果">
            <div class="download-container">
                <a href="${resultUrl}" 
                   download="ai_face_swap_result.jpg" 
                   class="download-btn" 
                   id="downloadBtn">
                    💾 下載結果
                </a>
                <p class="result-info">使用模板：${templateName}</p>
            </div>
        </div>
    `;
    
    // 不需要額外的成功事件，狀態面板已經處理了
}

// 顯示載入動畫
function showLoading(show) {
    elements.loadingOverlay.style.display = show ? 'flex' : 'none';
}

// 顯示帶進度的載入動畫
function showLoadingWithProgress(show) {
    if (show) {
        elements.loadingOverlay.style.display = 'flex';
        startProgressTimer();
    } else {
        elements.loadingOverlay.style.display = 'none';
        stopProgressTimer();
    }
}

// 進度計時器
let progressTimer = null;
let progressSeconds = 0;

function startProgressTimer() {
    progressSeconds = 0;
    updateProgressDisplay();
    
    progressTimer = setInterval(() => {
        progressSeconds++;
        updateProgressDisplay();
    }, 1000);
}

function stopProgressTimer() {
    if (progressTimer) {
        clearInterval(progressTimer);
        progressTimer = null;
    }
}

function updateProgressDisplay() {
    const loadingContent = document.querySelector('.loading-content p');
    if (loadingContent) {
        const estimatedTime = 30; // 預估 30 秒
        const remaining = Math.max(0, estimatedTime - progressSeconds);
        
        if (progressSeconds < estimatedTime) {
            loadingContent.textContent = `AI 正在處理中... ${progressSeconds}s / 預估 ${estimatedTime}s (剩餘約 ${remaining}s)`;
        } else {
            loadingContent.textContent = `AI 正在處理中... ${progressSeconds}s (處理時間較長，請耐心等候)`;
        }
    }
}

// 狀態面板系統
let statusItems = [];
let statusIdCounter = 0;

// 初始化狀態面板
function initializeEventLog() {
    // 不需要特別初始化
}

// 顯示訊息（簡化版）
function showMessage(text, type = 'info') {
    console.log(`[${type}] ${text}`);
}

// 添加狀態項目
function addStatusItem(title, description, type = 'processing') {
    const statusId = ++statusIdCounter;
    const statusItem = {
        id: statusId,
        title,
        description,
        type,
        timestamp: new Date(),
        resultUrl: null,
        templateName: null
    };
    
    statusItems.push(statusItem);
    updateStatusPanel();
    return statusId;
}

// 更新狀態項目
function updateStatusItem(statusId, updates) {
    const item = statusItems.find(item => item.id === statusId);
    if (item) {
        Object.assign(item, updates);
        updateStatusPanel();
    }
}

// 更新狀態面板顯示
function updateStatusPanel() {
    const statusContent = document.getElementById('statusContent');
    if (!statusContent) return;
    
    if (statusItems.length === 0) {
        statusContent.innerHTML = '<p class="status-placeholder">尚未開始處理</p>';
        return;
    }
    
    const statusHtml = statusItems.map(item => {
        const timeStr = item.timestamp.toLocaleTimeString('zh-TW', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        let actionsHtml = '';
        if (item.type === 'processing') {
            actionsHtml = '<div class="status-spinner"></div>';
        } else if (item.type === 'completed' && item.resultUrl) {
            actionsHtml = `
                <img src="${item.resultUrl}" class="status-preview" alt="結果預覽">
                <a href="${item.resultUrl}" download="ai_face_swap_result.jpg" class="status-download">下載</a>
            `;
        }
        
        return `
            <div class="status-item ${item.type}">
                <div class="status-info">
                    <div class="status-title">${item.title}</div>
                    <div class="status-desc">${item.description} - ${timeStr}</div>
                </div>
                <div class="status-actions">
                    ${actionsHtml}
                </div>
            </div>
        `;
    }).join('');
    
    statusContent.innerHTML = statusHtml;
}

// 清除舊的狀態項目（保留最近5個）
function cleanupStatusItems() {
    if (statusItems.length > 5) {
        statusItems = statusItems.slice(-5);
        updateStatusPanel();
    }
}

// 處理移除圖片
function handleRemoveImage(event) {
    event.stopPropagation(); // 防止觸發上傳區域的點擊事件
    
    selectedFile = null;
    
    // 重置檔案輸入
    elements.fileInput.value = '';
    
    // 隱藏預覽圖片，顯示上傳提示
    if (elements.uploadPreview) {
        elements.uploadPreview.style.display = 'none';
    }
    if (elements.uploadContent) {
        elements.uploadContent.style.display = 'block';
    }
    
    // 清空舊的預覽區域
    elements.preview.innerHTML = '';
    
    updateProcessButton();
    showMessage('已移除圖片', 'info');
}

// 模板上傳相關函數
function handleTemplateFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        validateAndPreviewTemplate(file);
    }
}

function handleTemplateDragOver(event) {
    event.preventDefault();
    elements.templateUploadArea.classList.add('dragover');
}

function handleTemplateDragLeave(event) {
    event.preventDefault();
    elements.templateUploadArea.classList.remove('dragover');
}

function handleTemplateDrop(event) {
    event.preventDefault();
    elements.templateUploadArea.classList.remove('dragover');
    
    const files = event.dataTransfer.files;
    if (files.length > 0) {
        validateAndPreviewTemplate(files[0]);
    }
}

function validateAndPreviewTemplate(file) {
    if (!Utils.isValidFileType(file)) {
        showMessage('不支援的檔案格式，請上傳 JPG、PNG 或 WebP 格式的圖片', 'error');
        return;
    }
    
    if (!Utils.isValidFileSize(file)) {
        showMessage(`檔案過大，請上傳小於 ${Utils.formatFileSize(API_CONFIG.UPLOAD.MAX_SIZE)} 的圖片`, 'error');
        return;
    }
    
    customTemplate = file;
    selectedTemplate = 'custom';
    previewTemplate(file);
    
    // 取消預設模板選擇
    document.querySelectorAll('input[name="template"]').forEach(radio => {
        radio.checked = false;
    });
    document.querySelectorAll('.template-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    updateProcessButton();
    showMessage('自訂模板上傳成功！', 'success');
}

function previewTemplate(file) {
    const reader = new FileReader();
    reader.onload = function(e) {
        if (elements.templateUploadContent) {
            elements.templateUploadContent.style.display = 'none';
        }
        
        if (elements.templateUploadPreview && elements.templatePreviewImage) {
            elements.templatePreviewImage.src = e.target.result;
            elements.templateUploadPreview.style.display = 'flex';
        }
    };
    reader.readAsDataURL(file);
}

function handleRemoveTemplate(event) {
    event.stopPropagation();
    
    customTemplate = null;
    selectedTemplate = null;
    
    elements.templateFileInput.value = '';
    
    if (elements.templateUploadPreview) {
        elements.templateUploadPreview.style.display = 'none';
    }
    if (elements.templateUploadContent) {
        elements.templateUploadContent.style.display = 'block';
    }
    
    updateProcessButton();
    showMessage('已移除自訂模板', 'info');
}

// 重置應用狀態
function resetApp() {
    selectedFile = null;
    selectedTemplate = null;
    customTemplate = null;
    isProcessing = false;
    
    elements.fileInput.value = '';
    elements.preview.innerHTML = '';
    elements.resultArea.innerHTML = '<p class="placeholder">處理結果將在這裡顯示</p>';
    
    // 重置上傳區域
    if (elements.uploadPreview) {
        elements.uploadPreview.style.display = 'none';
    }
    if (elements.uploadContent) {
        elements.uploadContent.style.display = 'block';
    }
    
    // 重置模板上傳區域
    if (elements.templateUploadPreview) {
        elements.templateUploadPreview.style.display = 'none';
    }
    if (elements.templateUploadContent) {
        elements.templateUploadContent.style.display = 'block';
    }
    
    document.querySelectorAll('input[name="template"]').forEach(radio => {
        radio.checked = false;
    });
    
    document.querySelectorAll('.template-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    updateProcessButton();
}

// 工具函數：格式化錯誤訊息
function formatErrorMessage(error) {
    if (typeof error === 'string') {
        return error;
    }
    
    if (error.message) {
        return error.message;
    }
    
    return '發生未知錯誤，請重試';
}

// 初始化分頁切換
function initializeTabSwitching() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            // 移除所有按鈕的 active 狀態
            tabBtns.forEach(b => b.classList.remove('active'));
            // 添加當前按鈕的 active 狀態
            btn.classList.add('active');
            
            // 隱藏所有分頁內容
            tabContents.forEach(content => {
                content.style.display = 'none';
            });
            
            // 顯示目標分頁內容
            const targetContent = document.getElementById(`${targetTab}-tab`);
            if (targetContent) {
                targetContent.style.display = 'block';
            }
        });
    });
}

// 導出函數（用於除錯）
window.AvatarStudio = {
    resetApp,
    checkApiHealth,
    selectedFile: () => selectedFile,
    selectedTemplate: () => selectedTemplate,
    isProcessing: () => isProcessing
};
