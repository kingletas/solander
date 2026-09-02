"""Decompresses LZ-String base64 payloads — the encoding Excalidraw notes use.

A pure-Python port of lz-string's decompressFromBase64, decode side only; this
reader never writes the format. Malformed input returns None, never raises.
"""

_KEY = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
_REVERSE = {character: index for index, character in enumerate(_KEY)}


def decompress_base64(data: str) -> str | None:
    """Returns the decompressed text, or None when the payload is not valid."""
    if not data:
        return ""
    cleaned = "".join(data.split())
    try:
        return _decompress(len(cleaned), 32, lambda i: _REVERSE[cleaned[i]])
    except (KeyError, IndexError, OverflowError, ValueError):
        return None


def _decompress(length: int, reset_value: int, get_next) -> str | None:
    dictionary: list[str] = ["", "", ""]
    enlarge_in = 4
    num_bits = 3
    result: list[str] = []

    state = {"value": get_next(0), "position": reset_value, "index": 1}

    def read_bits(count: int) -> int:
        bits = 0
        power = 1
        maximum = 1 << count
        while power != maximum:
            resb = state["value"] & state["position"]
            state["position"] >>= 1
            if state["position"] == 0:
                state["position"] = reset_value
                state["value"] = get_next(state["index"])
                state["index"] += 1
            if resb > 0:
                bits |= power
            power <<= 1
        return bits

    first = read_bits(2)
    if first == 2:
        return ""
    character = chr(read_bits(8 if first == 0 else 16))
    dictionary.append(character)
    previous = character
    result.append(character)

    while True:
        if state["index"] > length:
            return None
        code = read_bits(num_bits)
        if code == 0:
            dictionary.append(chr(read_bits(8)))
            code = len(dictionary) - 1
            enlarge_in -= 1
        elif code == 1:
            dictionary.append(chr(read_bits(16)))
            code = len(dictionary) - 1
            enlarge_in -= 1
        elif code == 2:
            text = "".join(result)
            try:
                return text.encode("utf-16", "surrogatepass").decode("utf-16")
            except UnicodeError:
                return text
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1
        if code < len(dictionary) and dictionary[code] != "":
            entry = dictionary[code]
        elif code == 3 and len(dictionary) > 3 and dictionary[3] != "":
            entry = dictionary[3]
        elif code == len(dictionary):
            entry = previous + previous[0]
        else:
            return None
        result.append(entry)
        dictionary.append(previous + entry[0])
        enlarge_in -= 1
        previous = entry
        if enlarge_in == 0:
            enlarge_in = 1 << num_bits
            num_bits += 1
