"""Browser form controls remain usable with localized titles and messages."""
from html.parser import HTMLParser

import pytest


class FormControls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.posts = 0
        self.names = set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and attrs.get("method") == "post":
            self.posts += 1
        if tag == "input":
            self.names.add(attrs.get("name"))


@pytest.mark.parametrize(
    "path,fields",
    [
        ("/login", {"email", "password"}),
        ("/register", {"email", "name", "password"}),
        ("/recover", {"email"}),
        ("/resend", {"email"}),
        ("/verify/unused-link", set()),
        ("/reset/unused-link", {"password"}),
    ],
)
def test_browser_pages_preserve_csrf_post_form_and_fields(client, db, path, fields):
    response = client.get(path)
    assert response.status_code == 200
    # Same-origin forms need a concrete Origin; cross-origin URLs must omit referrers.
    assert response["Referrer-Policy"] == "same-origin"
    controls = FormControls(response.content.decode())
    assert controls.posts == 1
    assert fields | {"csrfmiddlewaretoken", "next"} <= controls.names
