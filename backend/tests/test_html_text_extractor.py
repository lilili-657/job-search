import unittest

from backend.app.services.html_text_extractor import extract_visible_text


class HtmlTextExtractorTests(unittest.TestCase):
    def test_extracts_text_without_interpreting_it(self):
        html = """<h1>Example role</h1><p>Build <strong>useful</strong> tools.</p>
        <ul><li>Python</li><li>Work with people</li></ul>"""
        self.assertEqual(
            extract_visible_text(html),
            "Example role Build useful tools. Python Work with people",
        )

    def test_removes_scripts_styles_and_non_visible_markup(self):
        html = """<!doctype html><html><head><title>Metadata</title>
        <style>body { color: red; }</style><script>headCode()</script></head>
        <body><p>Visible</p><SCRIPT>if (a < b) { secret(); }</SCRIPT>
        <STYLE>.example { display: none; }</STYLE><!-- private comment -->
        <template><p>Template text</p></template>
        <div hidden><span hidden>Hidden child</span>Hidden parent</div>
        <p>Still visible</p></body></html>"""
        self.assertEqual(extract_visible_text(html), "Visible Still visible")

    def test_decodes_entities_and_normalizes_whitespace(self):
        html = "<p>  Café &amp; tea&nbsp;  &#x4F60;&#x597D;\n\t today </p>"
        self.assertEqual(extract_visible_text(html), "Café & tea 你好 today")

    def test_separates_adjacent_elements_and_line_breaks(self):
        html = "<div>First</div><div>Second<br>Third</div>"
        self.assertEqual(extract_visible_text(html), "First Second Third")

    def test_empty_or_excluded_only_input(self):
        for html in ("", " \n\t ", "<script>code()</script><style>p {}</style>"):
            with self.subTest(html=html):
                self.assertEqual(extract_visible_text(html), "")

    def test_tolerates_unclosed_markup(self):
        self.assertEqual(
            extract_visible_text("<div><p>First paragraph<p>Second paragraph"),
            "First paragraph Second paragraph",
        )


if __name__ == "__main__":
    unittest.main()
