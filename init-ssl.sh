#!/bin/bash

# SSL憑證自動生成腳本
echo "🔐 正在檢查SSL憑證..."

# 建立SSL目錄
mkdir -p /ssl

# 檢查是否需要重新生成憑證
NEED_REGEN=false

# 檢查憑證檔案是否存在
if [[ ! -f "/ssl/nginx-selfsigned.crt" ]] || [[ ! -f "/ssl/nginx-selfsigned.key" ]]; then
    echo "📝 憑證檔案不存在，需要生成..."
    NEED_REGEN=true
fi

# 檢查憑證是否包含正確的主機資訊
if [[ -f "/ssl/nginx-selfsigned.crt" ]] && [[ "$NEED_REGEN" == "false" ]]; then
    if ! openssl x509 -in /ssl/nginx-selfsigned.crt -text -noout | grep -q "$HOST_IP"; then
        echo "📝 憑證不包含當前主機IP ($HOST_IP)，需要重新生成..."
        NEED_REGEN=true
    fi
fi

# 生成或重新生成憑證
if [[ "$NEED_REGEN" == "true" ]]; then
    echo "🔄 正在生成SSL憑證..."
    
    # 生成私鑰
    if [[ ! -f "/ssl/nginx-selfsigned.key" ]]; then
        openssl genrsa -out /ssl/nginx-selfsigned.key 2048
        echo "✅ 私鑰生成完成"
    fi
    
    # 準備Subject Alternative Name
    SAN="DNS:localhost,DNS:$DOMAIN_NAME"
    if [[ "$HOST_IP" != "localhost" ]] && [[ "$HOST_IP" != "$DOMAIN_NAME" ]]; then
        # 檢查是否為IP格式
        if [[ $HOST_IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            SAN="$SAN,IP:$HOST_IP"
        else
            SAN="$SAN,DNS:$HOST_IP"
        fi
    fi
    
    # 生成憑證
    openssl req -new -x509 -key /ssl/nginx-selfsigned.key -out /ssl/nginx-selfsigned.crt -days $SSL_DAYS \
        -subj "/C=$SSL_COUNTRY/ST=$SSL_STATE/L=$SSL_CITY/O=$SSL_ORG/CN=$DOMAIN_NAME" \
        -addext "subjectAltName=$SAN"
    
    echo "✅ SSL憑證生成完成"
    echo "📊 憑證資訊:"
    echo "   - 主機IP: $HOST_IP"
    echo "   - 域名: $DOMAIN_NAME"
    echo "   - 有效期: $SSL_DAYS 天"
    echo "   - SAN: $SAN"
else
    echo "✅ SSL憑證已存在且有效"
fi

# 設定權限
chmod 600 /ssl/nginx-selfsigned.key
chmod 644 /ssl/nginx-selfsigned.crt

echo "🚀 SSL憑證準備完成！"