import pytest

from app.core.errors import AppError
from app.utils.webpage import _assert_public_host, extract_text, fetch_page_text


def test_extract_text_strips_scripts_and_nav():
    html = """
    <html><head><title>  My Great Article  </title>
    <style>.x{color:red}</style></head>
    <body>
    <nav>Home | About</nav>
    <script>console.log('nope')</script>
    <article><h1>Hello World</h1><p>This is the real content.</p></article>
    <footer>Copyright 2026</footer>
    </body></html>
    """
    title, text = extract_text(html)
    assert title == "My Great Article"
    assert "Hello World" in text
    assert "real content" in text
    assert "console.log" not in text
    assert "Home | About" not in text
    assert "Copyright 2026" not in text


def test_extract_text_empty_page():
    title, text = extract_text("<html><head></head><body></body></html>")
    assert title == ""
    assert text == ""


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "0.0.0.0", "169.254.169.254"])
def test_assert_public_host_blocks_private_and_loopback(host):
    with pytest.raises(AppError):
        _assert_public_host(host)


def test_fetch_page_text_rejects_non_http_scheme():
    with pytest.raises(AppError):
        fetch_page_text("ftp://example.com/file")


def test_fetch_page_text_rejects_private_url():
    with pytest.raises(AppError, match="public address"):
        fetch_page_text("http://127.0.0.1/whatever")
