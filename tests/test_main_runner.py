import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODE = ROOT / "code"
sys.path.insert(0, str(CODE))

from main import has_message_model_config, has_image_model_config


def test_model_config_checks_report_missing_environment(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("VISION_MODEL", raising=False)

    assert has_message_model_config() is False
    assert has_image_model_config() is False
