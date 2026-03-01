#!/bin/bash
# Install script cho YXWL 318Pro Shopee Label Printer
# Chạy với: sudo bash install.sh

set -e

echo "=== Cài đặt YXWL 318Pro TSPL Driver ==="

# 1. Kiểm tra dependencies
echo "[1/6] Kiểm tra dependencies..."
if ! command -v gs &>/dev/null; then
    echo "Cài ghostscript..."
    pacman -S --noconfirm ghostscript
fi
if ! command -v python3 &>/dev/null; then
    echo "Cài python..."
    pacman -S --noconfirm python
fi

# 2. Cài Python script
echo "[2/6] Cài pdf_to_tspl.py..."
cp pdf_to_tspl.py /usr/local/bin/pdf_to_tspl.py
chmod 755 /usr/local/bin/pdf_to_tspl.py

# 3. Cài CUPS filter
echo "[3/6] Cài CUPS filter..."
cp pdftolabel /usr/lib/cups/filter/pdftolabel
chmod 755 /usr/lib/cups/filter/pdftolabel
chown root:root /usr/lib/cups/filter/pdftolabel

# 4. Cài PPD
echo "[4/6] Cài PPD file..."
cp YXWL318Pro.ppd /usr/share/ppd/YXWL318Pro.ppd

# 5. Xóa printer cũ lỗi, tạo printer mới
echo "[5/6] Cấu hình CUPS printer..."
lpadmin -x 318Pro 2>/dev/null || true
lpadmin -x A318 2>/dev/null || true
lpadmin -x A318BT 2>/dev/null || true

lpadmin -p Shopee318Pro \
    -E \
    -v "usb:///318Pro?serial=0.0" \
    -P /usr/share/ppd/YXWL318Pro.ppd \
    -D "YXWL 318Pro - Shopee Label" \
    -L "USB"

# Set làm default
lpoptions -d Shopee318Pro

# 6. Restart CUPS
echo "[6/6] Restart CUPS..."
systemctl restart cups

echo ""
echo "=== Cài đặt hoàn tất! ==="
echo ""
echo "Printer: Shopee318Pro"
echo "Test in:  lp -d Shopee318Pro /đường/dẫn/label.pdf"
echo "Hoặc chọn 'Shopee318Pro' từ dialog in trong Chrome/Firefox"
echo ""
echo "Nếu gặp lỗi permission với /dev/usb/lp0:"
echo "  sudo usermod -aG lp \$USER && newgrp lp"
