from __future__ import annotations

import random
import string

from recoverx.core.query.parser import QueryParser


def _random_string(max_len: int = 20) -> str:
    return "".join(random.choice(string.ascii_letters) for _ in range(random.randint(0, max_len)))


class TestFuzzQuery:
    def test_fuzz_random_queries(self):
        fields = ["event", "filename", "name", "source", "timestamp", "confidence", "size", "mft"]
        ops = ["==", "!=", ">", "<", ">=", "<=", "contains", "!contains", "starts", "ends", "~"]

        for _ in range(100):
            field = random.choice(fields)
            op = random.choice(ops)
            value = random.choice(
                [
                    f'"{_random_string()}"',
                    f"'{_random_string()}'",
                    str(random.randint(0, 1000)),
                    "true",
                    "false",
                    "null",
                    "FILE_CREATED",
                    "FILE_DELETED",
                    "MFT",
                    "USN",
                ]
            )
            query = f"{field} {op} {value}"
            try:
                parser = QueryParser(query)
                ast = parser.parse()
                assert ast is not None
            except (ValueError, IndexError):
                pass

    def test_fuzz_complex_expressions(self):
        for _ in range(50):
            parts = []
            for _ in range(random.randint(1, 5)):
                field = random.choice(["event", "name", "source"])
                op = random.choice(["==", "contains"])
                value = random.choice(['"test"', '"FILE_DELETED"', "'MFT'"])
                parts.append(f"{field} {op} {value}")

            if random.random() < 0.3:
                query = "NOT " + parts[0]
            elif len(parts) > 1:
                joiner = random.choice(["AND", "OR"])
                query = (
                    f" ({parts[0]}) {joiner} ({parts[1]}) "
                    if random.random() < 0.3
                    else f"{parts[0]} {joiner} {parts[1]}"
                )
            else:
                query = parts[0]

            try:
                parser = QueryParser(query)
                ast = parser.parse()
                assert ast is not None
            except (ValueError, IndexError):
                pass

    def test_fuzz_empty_and_special(self):
        special_cases = [
            "",
            " " * 10,
            "AND",
            "OR",
            "NOT",
            "==",
            "event ==",
            'filename contains ""',
            "()",
            "(event == FILE_DELETED",
            "event == FILE_DELETED)",
            "a == b == c",
            "1 2 3",
            "event contains 'test' AND OR name == 'x'",
        ]
        for query in special_cases:
            try:
                parser = QueryParser(query)
                ast = parser.parse()
                assert ast is not None
            except (ValueError, IndexError):
                pass

    def test_fuzz_deeply_nested(self):
        for _ in range(20):
            nesting = random.randint(1, 10)
            query = "event == FILE_CREATED"
            for _ in range(nesting):
                side = random.choice(["left", "right"])
                extra = f'name contains "{_random_string()}"'
                if side == "left":
                    query = f"({extra} AND {query})"
                else:
                    query = f"({query} AND {extra})"
            try:
                parser = QueryParser(query)
                ast = parser.parse()
                assert ast is not None
            except (ValueError, RecursionError, IndexError):
                pass

    def test_fuzz_unicode_paths(self):
        unicode_names = [
            "caf\u00e9.txt",
            "\u00fcber.txt",
            "\u4e2d\u6587.txt",
            "\ud83d\udcc4.txt",
            "\u0000test.txt",
            "a" * 1000,
        ]
        for name in unicode_names:
            try:
                parser = QueryParser(f'name contains "{name}"')
                ast = parser.parse()
                assert ast is not None
            except (ValueError, IndexError):
                pass
