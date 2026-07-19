from random import sample
from string import ascii_letters, digits


def _has_chinese_char(chars: str) -> bool:
    return any(["\u4e00" <= char <= "\u9fa5" for char in chars])


def _all_alpha_or_dights(chars: str) -> bool:
    return all([char in ascii_letters+digits for char in chars])


def _starts_with_unseen(chars: str) -> bool:
    if len(chars) == 0:
        return True
    return not chars[0].isprintable()


def split_text(text: str, size: int) -> list[str]:
    """Split a string

    Args:
        text (str): The string
        size (int): How many words in a group

    Returns:
        list[str]: The splited group
    """
    ret: list[str] = []
    for i in range(0, len(text), size):
        ret.append(text[i:i+size])
    return ret


def is_valid_answer(answer: str) -> bool:
    """Check if it is a valid answer string

    Args:
        answer (str): The string to check

    Returns:
        bool: The result
    """
    # Answers may legitimately contain punctuation or symbols, for example
    # ``3.14``, ``50%``, ``1/3`` and ``A+B``. This validator is used while
    # reading page hints, so restricting it to Chinese/alphanumeric text drops
    # valid answers before the matching stage even gets a chance to use them.
    if not answer or _starts_with_unseen(answer):
        return False
    return all(char.isprintable() for char in answer)


def gen_random_string(length: int = 4) -> str:
    """Generate a random string with specified length

    Args:
        length (int, optional): The length of string. Defaults to 4.

    Returns:
        str: The generated string
    """
    return "".join(sample(ascii_letters+digits, length))
