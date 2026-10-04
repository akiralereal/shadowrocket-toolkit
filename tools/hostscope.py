from __future__ import annotations

import fnmatch
import re

from modulelib import ModuleError


class _HostParser:
    """Expand finite alternatives and conservatively widen variable labels.

    This intentionally supports a small hostname grammar rather than arbitrary
    regular expressions. Unsupported forms fail validation instead of silently
    bypassing the MITM check. A '*' scope can include nested subdomains.
    """

    def __init__(self, expression: str):
        self.expression = expression
        self.position = 0

    def parse(self, grouped: bool = False) -> list[str]:
        branches: list[str] = []
        current = [""]
        while self.position < len(self.expression):
            character = self.expression[self.position]
            if character in "|)":
                branches.extend(current)
                self.position += 1
                if character == ")":
                    if not grouped:
                        raise ModuleError("unexpected closing hostname group")
                    return branches
                current = [""]
                continue

            atom = self.atom()
            if self.position < len(self.expression):
                quantifier = self.expression[self.position]
                if quantifier == "?":
                    atom = ["", *atom]
                    self.position += 1
                elif quantifier in "+*":
                    # Repeated variable labels, with or without their dot.
                    if atom not in (["*"], ["*."]):
                        raise ModuleError("unsupported repeated hostname group")
                    if quantifier == "*":
                        atom = ["", *atom]
                    self.position += 1
            current = list(dict.fromkeys(left + right for left in current for right in atom))
            if len(current) + len(branches) > 128:
                raise ModuleError("too many hostname alternatives")

        if grouped:
            raise ModuleError("unclosed hostname group")
        return [*branches, *current]

    def atom(self) -> list[str]:
        character = self.expression[self.position]
        self.position += 1
        if character == "(":
            if self.expression.startswith("?:", self.position):
                self.position += 2
            elif self.expression.startswith("?", self.position):
                raise ModuleError("unsupported hostname group")
            return self.parse(grouped=True)
        if character == "[":
            # The original regex has already been compiled by the caller.
            end = self.position
            escaped = False
            while end < len(self.expression):
                value = self.expression[end]
                if value == "]" and not escaped:
                    character_class = self.expression[self.position - 1:end + 1]
                    if re.fullmatch(character_class, "/"):
                        raise ModuleError("hostname character class must not match a slash")
                    self.position = end + 1
                    return ["*"]
                escaped = value == "\\" and not escaped
                end += 1
            raise ModuleError("unclosed hostname character class")
        if character == "\\":
            if self.position >= len(self.expression):
                raise ModuleError("incomplete hostname escape")
            escaped = self.expression[self.position]
            self.position += 1
            if escaped == ".":
                return ["."]
            if escaped in "dw":
                return ["*"]
            raise ModuleError("unsupported hostname escape")
        if re.fullmatch(r"[A-Za-z0-9-]", character):
            return [character.lower()]
        raise ModuleError(f"unsupported hostname token {character!r}")


def https_host_patterns(pattern: str) -> tuple[str, ...]:
    normalized = pattern.replace(r"\/", "/")
    depth = 0
    in_class = False
    escaped = False
    for character in normalized:
        if not escaped:
            if character == "[":
                in_class = True
            elif character == "]":
                in_class = False
            elif not in_class:
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                elif character == "|" and depth <= int(normalized.startswith("(^")):
                    raise ModuleError(f"unscoped URL alternative: {pattern}")
        escaped = character == "\\" and not escaped
    if normalized.count("://") != 1:
        raise ModuleError(f"cannot verify URL scheme: {pattern}")
    if normalized.startswith("^http://"):
        return ()
    scheme = re.match(r"^\(?\^https\??://", normalized)
    if not scheme:
        raise ModuleError(f"cannot verify HTTPS hostname scope: {pattern}")

    start = scheme.end()
    position = start
    in_class = False
    escaped = False
    while position < len(normalized):
        character = normalized[position]
        if not in_class and not escaped and (
            character == "/" or normalized.startswith("(?:/", position)
        ):
            break
        if character == "[" and not escaped:
            in_class = True
        elif character == "]" and not escaped:
            in_class = False
        escaped = character == "\\" and not escaped
        position += 1
    expression = normalized[start:position].removesuffix("$")
    # A port is not part of a MITM hostname. Support literal and optional ports.
    expression = re.sub(r"\(\?::[0-9]+\)\?", "", expression)
    expression = re.sub(r"(?<!\?):[0-9]+(?=\)|\||$)", "", expression)
    try:
        scopes = _HostParser(expression).parse()
    except ModuleError as error:
        raise ModuleError(f"cannot verify HTTPS hostname scope {pattern!r}: {error}") from error
    scopes = sorted({re.sub(r"\*+", "*", scope) for scope in scopes})
    if not scopes or any(
        not re.fullmatch(r"[a-z0-9*-]+(?:\.[a-z0-9*-]+)+", scope)
        for scope in scopes
    ):
        raise ModuleError(f"invalid HTTPS hostname scope: {pattern}")
    return tuple(scopes)


def hostname_is_covered(hostname: str, configured: set[str]) -> bool:
    hostname = hostname.lower()
    if any(fnmatch.fnmatchcase(hostname, item[1:]) for item in configured if item.startswith("-")):
        return False
    return any(fnmatch.fnmatchcase(hostname, item) for item in configured if not item.startswith("-"))


def _glob_covers(cover: str, scope: str) -> bool:
    if "*" not in scope:
        return fnmatch.fnmatchcase(scope, cover)
    if "*" not in cover:
        return False
    prefix, suffix = cover.split("*", 1)
    return scope.split("*", 1)[0].startswith(prefix) and scope.rsplit("*", 1)[-1].endswith(suffix)


def host_pattern_is_covered(scope: str, configured: set[str]) -> bool:
    if "*" not in scope:
        return hostname_is_covered(scope, configured)
    # Partial exclusions are deliberate opt-outs (e.g. YouTube redirectors).
    # A scope that is entirely excluded must never pass the coverage check.
    if any(_glob_covers(item[1:], scope) for item in configured if item.startswith("-")):
        return False
    return any(_glob_covers(item, scope) for item in configured if not item.startswith("-"))
