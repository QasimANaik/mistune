import time

from mistune.toc import render_toc_ul


def test_render_toc_ul_ordered_single():
    """AC-FR-001-1: Given TOC items [(1, 'toc_1', 'Introduction')], when render_toc_ul(toc_items, ordered=True), then correct <ol> HTML."""
    toc_items = [(1, 'toc_1', 'Introduction')]
    result = render_toc_ul(toc_items, ordered=True)
    expected = "<ol>\n<li><a href=\"#toc_1\">Introduction</a></li>\n</ol>\n"
    assert result == expected


def test_render_toc_ul_ordered_nested():
    """AC-FR-001-2: Given nested TOC items [(1, 'toc_1', 'One'), (2, 'toc_2', 'Sub')], when render_toc_ul(toc_items, ordered=True), then correct nested <ol> HTML."""
    toc_items = [(1, 'toc_1', 'One'), (2, 'toc_2', 'Sub')]
    result = render_toc_ul(toc_items, ordered=True)
    expected = (
        "<ol>\n"
        "<li><a href=\"#toc_1\">One</a>\n"
        "<ol>\n"
        "<li><a href=\"#toc_2\">Sub</a></li>\n"
        "</ol>\n"
        "</li>\n"
        "</ol>\n"
    )
    assert result == expected


def test_render_toc_ul_performance_threshold():
    """AC-NFR-001-1: Execution time must be < 5ms for 1000 TOC items."""
    toc_items = [(1 if i % 2 == 0 else 2, f"toc_{i}", f"Title {i}") for i in range(1000)]
    
    # Warm up
    render_toc_ul(toc_items, ordered=True)
    
    start_time = time.perf_counter()
    iterations = 10
    for _ in range(iterations):
        render_toc_ul(toc_items, ordered=True)
    end_time = time.perf_counter()
    
    avg_duration_ms = ((end_time - start_time) / iterations) * 1000
    assert avg_duration_ms < 5.0, f"Average execution time {avg_duration_ms:.2f}ms exceeded 5ms threshold for 1000 TOC items"
