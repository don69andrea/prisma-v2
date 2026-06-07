"""CH-ISIN-Validator nach ISO 6166 mit Luhn-Mod-10-Prüfziffer."""


def validate_ch_isin(isin: str) -> bool:
    """Prüft ob isin ein gültiges Schweizer ISIN-Format hat.

    Format: CH + 9 Ziffern + 1 Luhn-Prüfziffer = 12 Zeichen.
    Luhn wird auf die vollständig numerische Expansion angewendet:
    C→12, H→17, dann die verbleibenden 10 Ziffern.
    """
    if not isinstance(isin, str) or len(isin) != 12:
        return False
    if not isin.startswith("CH"):
        return False
    numeric_part = isin[2:]
    if not numeric_part.isdigit():
        return False
    # "CH" → C=12, H=17 → "1217" (2-digit codes per ISO 6166)
    full_numeric = "1217" + numeric_part  # 4 + 10 = 14 digits
    total = 0
    for i, ch in enumerate(reversed(full_numeric)):
        n = int(ch)
        if i % 2 == 1:  # double every second digit from the right
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0
