"""
====================================================
  Middleware / Utility: Data Masking
  Bộ lọc Regex che thông tin nhạy cảm (PII)
  VinUni AI20k Batch 02 · Day 05
====================================================
"""

import re
import logging

logger = logging.getLogger(__name__)

# Regex for matching email addresses
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# Regex for matching 9-11 digit numbers (commonly phone numbers or student IDs in Vietnam)
PHONE_STUDENT_ID_REGEX = re.compile(r'\b\d{9,11}\b')


def mask_sensitive_data(text: str) -> str:
    """
    Quét và tự động thay thế thông tin nhạy cảm của học viên (Emails, Số điện thoại, MSSV)
    trước khi gửi dữ liệu lên máy chủ API bên ngoài (OpenAI/Google).
    """
    if not text:
        return text

    original_text = text

    # Che mờ email thành [STUDENT_EMAIL_MASKED]
    text = EMAIL_REGEX.sub("[STUDENT_EMAIL_MASKED]", text)

    # Che mờ số điện thoại / mã sinh viên thành [ANONYMOUS_USER_ID]
    text = PHONE_STUDENT_ID_REGEX.sub("[ANONYMOUS_USER_ID]", text)

    if text != original_text:
        logger.info("🔒 PII data detected and masked successfully.")

    return text
