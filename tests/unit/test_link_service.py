import string

import pytest

from app.services.link_service import LinkService, ALPHABET


class TestGenerateShortCode:
    def test_default_length_is_6(self):
        code = LinkService._generate_short_code()
        assert len(code) == 6

    def test_custom_length(self):
        for length in (3, 8, 12):
            code = LinkService._generate_short_code(length)
            assert len(code) == length

    def test_only_uses_valid_alphabet_characters(self):
        valid = set(ALPHABET)
        for _ in range(50):
            code = LinkService._generate_short_code()
            assert all(ch in valid for ch in code), f"Invalid char in: {code}"

    def test_alphabet_contains_letters_and_digits(self):
        assert set(string.ascii_letters).issubset(set(ALPHABET))
        assert set(string.digits).issubset(set(ALPHABET))

    def test_successive_codes_are_different(self):

        codes = {LinkService._generate_short_code() for _ in range(100)}
        assert len(codes) > 1


class TestCacheKeys:
    def test_cache_key_format(self):
        assert LinkService._cache_key("abc123") == "link:abc123"

    def test_stats_cache_key_format(self):
        assert LinkService._stats_cache_key("abc123") == "stats:abc123"

    def test_cache_key_uses_short_code(self):
        code = "xYz789"
        assert code in LinkService._cache_key(code)

    def test_stats_cache_key_uses_short_code(self):
        code = "xYz789"
        assert code in LinkService._stats_cache_key(code)

    def test_cache_key_and_stats_key_are_different(self):
        code = "same"
        assert LinkService._cache_key(code) != LinkService._stats_cache_key(code)
