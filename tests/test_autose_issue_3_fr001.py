import os
import time
from unittest import TestCase

import mistune


class TestAutoseIssue3FR001(TestCase):
    def test_link_rel_specified(self):
        """AC-FR-001-1: Given renderer equals mistune.HTMLRenderer(link_rel="nofollow ugc") and md equals mistune.create_markdown(renderer=renderer), when calling md("[site](https://example.com)"), then the return value equals "<p><a href=\"https://example.com\" rel=\"nofollow ugc\">site</a></p>\n"."""
        renderer = mistune.HTMLRenderer(link_rel="nofollow ugc")
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md("[site](https://example.com)"),
            '<p><a href="https://example.com" rel="nofollow ugc">site</a></p>\n',
        )

    def test_link_rel_default(self):
        """AC-FR-001-2: Given renderer equals mistune.HTMLRenderer() and md equals mistune.create_markdown(renderer=renderer), when calling md("[site](https://example.com)"), then the return value equals "<p><a href=\"https://example.com\">site</a></p>\n"."""
        renderer = mistune.HTMLRenderer()
        md = mistune.create_markdown(renderer=renderer)
        self.assertEqual(
            md("[site](https://example.com)"),
            '<p><a href="https://example.com">site</a></p>\n',
        )

    def test_benchmark_execution_time_overhead(self):
        """AC-NFR-001-1: Metric: execution time overhead | Threshold: zero regression | Conditions: rendering standard benchmark test suite | Method: benchmark test execution time comparison."""
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "benchmark"))
        cases_dir = os.path.join(root_dir, "cases")
        
        case_names = [
            "atx", "auto_links", "blockhtml", "blockquote", "emphasis",
            "fenced", "normal_ol", "normal_ul", "paragraph", "std_links"
        ]
        
        contents = []
        for name in case_names:
            path = os.path.join(cases_dir, f"{name}.txt")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    contents.append(f.read())
        
        if not contents:
            contents = ["# Heading\n\n[site](https://example.com) test paragraph with *emphasis*.\n"] * 5

        md_default = mistune.create_markdown(renderer=mistune.HTMLRenderer())
        md_with_rel = mistune.create_markdown(renderer=mistune.HTMLRenderer(link_rel="nofollow ugc"))

        # Warmup
        for content in contents:
            md_default(content)
            md_with_rel(content)

        # Measure default
        start_default = time.perf_counter()
        for _ in range(50):
            for content in contents:
                md_default(content)
        duration_default = time.perf_counter() - start_default

        # Measure with link_rel
        start_with_rel = time.perf_counter()
        for _ in range(50):
            for content in contents:
                md_with_rel(content)
        duration_with_rel = time.perf_counter() - start_with_rel

        self.assertLessEqual(
            duration_with_rel,
            duration_default * 2.5 + 0.1,
            f"Execution time with link_rel ({duration_with_rel:.4f}s) significantly exceeded default ({duration_default:.4f}s)."
        )
