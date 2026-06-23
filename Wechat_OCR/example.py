import OCR
texts = OCR.wechat_ocr("QQ20250207-102251.png")
print(f"ocr_picture:{texts}")
print("=========================")
texts = OCR.ocr_pdf("QQ20250207-102251.png")
print(f"ocr_pdf:{texts}")