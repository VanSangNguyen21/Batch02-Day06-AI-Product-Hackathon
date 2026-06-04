import os
import re
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Tìm đường dẫn đến file guardrail_rules.json
def get_guardrail_rules_path() -> str:
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "guardrail_rules.json"),
        os.path.join(os.path.dirname(__file__), "..", "prompts", "guardrail_rules.json"),
        os.path.join(os.path.dirname(__file__), "prompts", "guardrail_rules.json"),
        "C:\\ai_vinuni\\code_vinuni\Batch02-Day05\\project\\prompts\\guardrail_rules.json"
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    # Trả về đường dẫn mặc định nếu không tìm thấy
    return os.path.join(os.path.dirname(__file__), "guardrail_rules.json")

class GuardrailManager:
    def __init__(self):
        self.rules_path = get_guardrail_rules_path()
        self.rules = {}
        self.banned_keywords = []
        self.jailbreak_patterns = []
        self.out_of_scope_keywords = []
        self.response_templates = {}
        self.spam_config = {}
        self.load_rules()

    def load_rules(self):
        try:
            if os.path.exists(self.rules_path):
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    self.rules = json.load(f)
                self.banned_keywords = self.rules.get("banned_keywords", [])
                self.jailbreak_patterns = [
                    re.compile(p, re.IGNORECASE | re.UNICODE) for p in self.rules.get("jailbreak_patterns", [])
                ]
                self.out_of_scope_keywords = self.rules.get("out_of_scope_keywords", [])
                self.response_templates = self.rules.get("response_templates", {})
                self.spam_config = self.rules.get("spam_detection", {})
                logger.info(f"✅ Loaded guardrail rules from {self.rules_path}")
            else:
                logger.warning(f"⚠️ Guardrail rules file not found at {self.rules_path}, using default hardcoded rules")
                self._load_defaults()
        except Exception as e:
            logger.error(f"❌ Error loading guardrail rules: {e}")
            self._load_defaults()

    def _load_defaults(self):
        self.banned_keywords = ["hack", "jailbreak", "override", "bypass security"]
        self.jailbreak_patterns = [re.compile(r"ignore previous instructions", re.IGNORECASE)]
        self.out_of_scope_keywords = ["hack ngân hàng", "cờ bạc online"]
        self.response_templates = {
            "blocked_harmful": "🛡️ [Yêu cầu vi phạm ranh giới bảo mật của hệ thống].",
            "blocked_spam": "🚫 Phát hiện hành vi spam. Vui lòng nhập câu hỏi thực sự của bạn.",
            "blocked_jailbreak": "🛡️ [Yêu cầu vi phạm ranh giới bảo mật của hệ thống]",
            "out_of_scope": "📚 Câu hỏi của bạn nằm ngoài phạm vi của AI Path.",
            "too_short": "Vui lòng nhập câu hỏi rõ ràng hơn.",
            "too_long": "Câu hỏi quá dài."
        }
        self.spam_config = {
            "max_repeated_chars": 50,
            "max_repeated_words": 10,
            "min_message_length": 2,
            "max_message_length": 2000
        }

    def check_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Kiểm tra tin nhắn qua các bộ lọc: Spam, Jailbreak, Banned Keywords, Out of Scope.
        Trả về dictionary chứa kết quả chặn nếu vi phạm, ngược lại trả về None.
        """
        msg = message.strip()
        msg_lower = msg.lower()

        # 1. Kiểm tra độ dài tối thiểu
        min_len = self.spam_config.get("min_message_length", 2)
        if len(msg) < min_len:
            return {
                "blocked": True,
                "reason": "too_short",
                "response": self.response_templates.get("too_short", "Vui lòng nhập tin nhắn dài hơn.")
            }

        # 2. Kiểm tra độ dài tối đa
        max_len = self.spam_config.get("max_message_length", 2000)
        if len(msg) > max_len:
            return {
                "blocked": True,
                "reason": "too_long",
                "response": self.response_templates.get("too_long", "Tin nhắn quá dài.")
            }

        # 3. Kiểm tra spam (lặp ký tự liên tục)
        spam_pattern_str = self.spam_config.get("pattern", "(.{1,5})\\1{20,}")
        try:
            if re.search(spam_pattern_str, msg_lower):
                return {
                    "blocked": True,
                    "reason": "spam_repeated_chars",
                    "response": self.response_templates.get("blocked_spam")
                }
        except Exception:
            pass

        # Kiểm tra lặp từ quá nhiều
        words = msg_lower.split()
        if len(words) > 10:
            word_counts = {}
            for w in words:
                word_counts[w] = word_counts.get(w, 0) + 1
            max_repeated_words = self.spam_config.get("max_repeated_words", 10)
            if any(count > max_repeated_words for count in word_counts.values()):
                return {
                    "blocked": True,
                    "reason": "spam_repeated_words",
                    "response": self.response_templates.get("blocked_spam")
                }

        # 4. Kiểm tra Jailbreak patterns
        for pattern in self.jailbreak_patterns:
            if pattern.search(msg):
                logger.warning(f"🚫 Jailbreak pattern detected: {pattern.pattern}")
                return {
                    "blocked": True,
                    "reason": "jailbreak",
                    "response": self.response_templates.get("blocked_jailbreak")
                }

        # 5. Kiểm tra Banned Keywords
        for kw in self.banned_keywords:
            if kw.lower() in msg_lower:
                logger.warning(f"🚫 Banned keyword detected: {kw}")
                return {
                    "blocked": True,
                    "reason": "banned_keyword",
                    "response": self.response_templates.get("blocked_harmful")
                }

        # 6. Kiểm tra Out of Scope
        for kw in self.out_of_scope_keywords:
            if kw.lower() in msg_lower:
                logger.warning(f"🚫 Out of scope keyword detected: {kw}")
                return {
                    "blocked": True,
                    "reason": "out_of_scope",
                    "response": self.response_templates.get("out_of_scope")
                }

        return None

# Singleton instance
guardrail_manager = GuardrailManager()
