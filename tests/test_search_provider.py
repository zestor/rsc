"""Tests for search content filtering (filter_prose_blocks) and provider integration."""

from __future__ import annotations

from rsc.search_provider import (
    FirecrawlSearchProvider,
    FunctionSearchProvider,
    filter_prose_blocks,
    strip_unwanted_media_tags,
)


class TestFilterProseBlocks:
    def test_three_sentence_prose_kept(self):
        text = (
            "This is the first sentence. Here is the second one. And finally the third."
        )
        assert filter_prose_blocks(text) == text

    def test_two_sentence_block_dropped(self):
        text = "Short comment. Thanks for sharing."
        assert filter_prose_blocks(text) == ""

    def test_one_sentence_block_dropped(self):
        text = "We use cookies to improve your experience."
        assert filter_prose_blocks(text) == ""

    def test_navigation_labels_dropped(self):
        text = "Home\n\nAbout Us\n\nContact"
        assert filter_prose_blocks(text) == ""

    def test_bullet_list_kept(self):
        text = "- First item\n- Second item\n- Third item"
        result = filter_prose_blocks(text)
        assert "First item" in result

    def test_heading_kept(self):
        text = "## Section Title"
        result = filter_prose_blocks(text)
        assert "Section Title" in result

    def test_table_kept(self):
        text = "| Col1 | Col2 |\n|------|------|\n| a    | b    |"
        result = filter_prose_blocks(text)
        assert "Col1" in result

    def test_empty_blocks_dropped(self):
        text = "   \n\n\n  \n\nThree sentences are here. This is the second. And the third."
        result = filter_prose_blocks(text)
        assert "Three sentences" in result
        # The empty blocks should not appear
        assert result.count("\n\n") == 0

    def test_fenced_code_with_prose_inside_kept(self):
        text = (
            "```python\n"
            "This is not actually code. It is prose wrapped in a code block. "
            "The author used fences for formatting. This is common on some sites.\n"
            "```"
        )
        result = filter_prose_blocks(text)
        assert "This is not actually code" in result
        # Fences should be stripped
        assert "```" not in result

    def test_fenced_code_with_actual_code_dropped(self):
        text = "```python\ndef hello():\n    print('hi')\n```"
        result = filter_prose_blocks(text)
        assert result == ""

    def test_fenced_code_with_language_tag(self):
        text = "```javascript\nconst x = 1;\n```"
        result = filter_prose_blocks(text)
        assert result == ""

    def test_fenced_code_empty_fences_dropped(self):
        text = "```\n```"
        result = filter_prose_blocks(text)
        assert result == ""

    def test_mixed_prose_and_navigation(self):
        text = (
            "This is an important paragraph about the topic. "
            "It contains several sentences that provide context. "
            "The third sentence adds more detail.\n\n"
            "Home\n\nAbout Us\n\n"
            "Another paragraph with substance. "
            "This one also has multiple sentences. "
            "The third sentence completes the thought."
        )
        result = filter_prose_blocks(text)
        assert "important paragraph" in result
        assert "Another paragraph" in result
        assert "Home" not in result
        assert "About Us" not in result

    def test_input_with_only_garbage_empty_output(self):
        text = "Home\n\nContact\n\nSearch\n\nLogin"
        assert filter_prose_blocks(text) == ""

    def test_empty_input(self):
        assert filter_prose_blocks("") == ""
        assert filter_prose_blocks("   ") == ""

    def test_prose_with_inline_code_kept(self):
        text = (
            "Use the `filter_prose_blocks` function to clean markdown. "
            "It removes fragments that are too short. "
            "Blocks with three or more sentences are preserved."
        )
        result = filter_prose_blocks(text)
        assert "filter_prose_blocks" in result

    def test_multiple_blocks_mixed(self):
        text = (
            "Nav item\n\n"
            "This is a real paragraph with enough sentences. "
            "The second sentence adds context. "
            "A third sentence for completeness.\n\n"
            "Short.\n\n"
            "- Bullet one\n- Bullet two\n- Bullet three"
        )
        result = filter_prose_blocks(text)
        assert "Nav item" not in result
        assert "real paragraph" in result
        assert "Short" not in result
        assert "Bullet one" in result

    def test_fenced_code_with_prose_and_code_mixed(self):
        """Code fence with prose sentences among code lines."""
        text = (
            "```markdown\n"
            "Some code line 1\n"
            "This is a sentence in the block. "
            "Another sentence follows it. "
            "A third sentence makes it qualify.\n"
            "Some code line 2\n"
            "```"
        )
        result = filter_prose_blocks(text)
        assert "```" not in result
        assert "sentence in the block" in result

    def test_standalone_bullet_kept_even_if_short(self):
        """A single bullet line should be kept as structured content."""
        text = "- Important note"
        result = filter_prose_blocks(text)
        assert "Important note" in result

    def test_standalone_heading_kept_even_if_short(self):
        text = "## API Reference"
        result = filter_prose_blocks(text)
        assert "API Reference" in result

    def test_whitespace_only_blocks_dropped(self):
        text = "   \n\n\t\t\n\nThree sentences make this valid. Second sentence here. Third one too."
        result = filter_prose_blocks(text)
        assert "Three sentences" in result
        # Whitespace-only blocks should not appear
        assert (
            result.strip()
            == "Three sentences make this valid. Second sentence here. Third one too."
        )


class TestFilterIntegration:
    def test_firecrawl_format_response_with_garbage(self):
        """Firecrawl provider filters garbage from scraped markdown."""
        provider = FirecrawlSearchProvider(api_key=None, name="firecrawl")
        # Simulate the raw Firecrawl JSON response
        payload = {
            "success": True,
            "data": [
                {
                    "title": "Example Article",
                    "url": "https://example.com/article",
                    "description": "A helpful article about Python.",
                    "position": 1,
                    "markdown": (
                        "Home\n\nAbout Us\n\n"
                        "This article explains Python basics in detail. "
                        "Python is a versatile programming language. "
                        "It is widely used in data science and web development.\n\n"
                        "© 2026 Example Inc."
                    ),
                }
            ],
        }
        result = provider._format_response("Python basics", payload)
        # Prose should be kept
        assert "Python basics in detail" in result
        # Navigation and footer should be filtered
        assert "About Us" not in result
        assert "© 2026" not in result

    def test_firecrawl_format_response_with_code_fence(self):
        """Firecrawl provider strips code fences but evaluates content."""
        provider = FirecrawlSearchProvider(api_key=None, name="firecrawl")
        payload = {
            "success": True,
            "data": [
                {
                    "title": "Code Example",
                    "url": "https://example.com/code",
                    "description": "Code examples.",
                    "position": 1,
                    "markdown": (
                        "Here is how to use the function correctly. "
                        "You need to import the module first. "
                        "Then call the function with the right arguments.\n\n"
                        "```python\nimport os\nos.getcwd()\n```"
                    ),
                }
            ],
        }
        result = provider._format_response("python function", payload)
        assert "how to use the function" in result
        # The code block (actual code) should be stripped
        assert "os.getcwd" not in result

    def test_function_search_provider_not_filtered(self):
        """FunctionSearchProvider does not apply prose filtering."""
        calls = []

        def my_search(query, max_results):
            calls.append(query)
            return "Home\n\nAbout Us\n\nShort."

        provider = FunctionSearchProvider(search_func=my_search, name="test")
        result = provider.search("test query")
        # Function provider returns raw content without filtering
        assert "Home" in result
        assert "Short." in result
