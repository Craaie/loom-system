from app.agents.ingestion.processor import decode_text_preview


def test_decode_text_preview_utf8():
    text, encoding = decode_text_preview("第一章 测试内容".encode("utf-8"))
    assert encoding == "utf-8"
    assert "测试内容" in text


def test_decode_text_preview_gbk():
    payload = "第一章 GBK 内容".encode("gbk", errors="ignore")
    text, encoding = decode_text_preview(payload)
    assert encoding == "gbk"
    assert "GBK" in text
