from __future__ import annotations

"""추가 인자 한 줄을 실제 argv 토큰으로 나눕니다.

spice2x는 ``-modules <경로>``처럼 옵션 이름과 값을 서로 다른 argv 항목으로 받습니다.
옵션 파서는 앞의 ``-``를 모두 떼어낸 뒤 이름 전체를 비교하므로
``-url example.com:8083``이 하나의 argv 항목으로 들어오면 어떤 옵션과도 일치하지 않고
경고 없이 버려집니다. 저장된 인자 한 줄을 실행 직전에 토큰으로 나눠 이 문제를 막습니다.
"""

_QUOTE = '"'
_WHITESPACE = " \t"


def split_argument_line(line: str) -> list[str]:
    """한 줄을 Windows 명령줄 규칙에 맞춰 토큰으로 나눕니다.

    큰따옴표로 묶은 구간은 공백을 포함해 하나의 토큰으로 유지하고 따옴표는 제거합니다.
    """
    tokens: list[str] = []
    current: list[str] = []
    inside_quotes = False
    has_token = False

    for character in line:
        if character == _QUOTE:
            inside_quotes = not inside_quotes
            has_token = True
            continue
        if character in _WHITESPACE and not inside_quotes:
            if has_token or current:
                tokens.append("".join(current))
                current.clear()
                has_token = False
            continue
        current.append(character)
        has_token = True

    if has_token or current:
        tokens.append("".join(current))
    return tokens


def normalize_arguments(arguments) -> tuple[str, ...]:
    """저장된 추가 인자 목록을 실행에 사용할 argv 토큰으로 바꿉니다.

    ``-``, ``/``, ``"``로 시작하는 항목만 다시 나눕니다. 그 밖의 항목은 공백이 들어 있는
    경로일 수 있으므로 입력한 그대로 하나의 인자로 전달합니다.
    """
    normalized: list[str] = []
    for argument in arguments:
        value = argument.strip()
        if not value:
            continue
        if value[0] in {"-", "/", _QUOTE}:
            normalized.extend(split_argument_line(value))
        else:
            normalized.append(value)
    return tuple(normalized)
