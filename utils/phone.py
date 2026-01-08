def normalize_phone(phone: str) -> str:
    """
    Normalize phone numbers to 7XXXXXXXX (Kenya local format)
    """
    phone = phone.strip().replace(" ", "")

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("254") and len(phone) == 12:
        return phone[3:]   # 2547XXXXXXXX → 7XXXXXXXX

    if phone.startswith("0") and len(phone) == 10:
        return phone[1:]   # 07XXXXXXXX → 7XXXXXXXX

    if phone.startswith("7") and len(phone) == 9:
        return phone

    raise ValueError("Invalid phone number format")

