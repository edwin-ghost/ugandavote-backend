def normalize_phone(phone: str) -> str:
    """
    Normalize Kenyan phone numbers to 2547XXXXXXXX
    """
    phone = phone.strip().replace(" ", "")

    if phone.startswith("+"):
        phone = phone[1:]

    if phone.startswith("0") and len(phone) == 10:
        return "254" + phone[1:]

    if phone.startswith("7") and len(phone) == 9:
        return "254" + phone

    if phone.startswith("254") and len(phone) == 12:
        return phone
    

    raise ValueError("Invalid phone number format")
