def coerce_on_off(value):
    """
    Coerces the given value to either "ON", "OFF" or None.

    Args:
        value: The value to be coerced.

    Returns:
        The coerced value, either "ON", "OFF", or None.
    """
    if value is not None:
        try:
            value = value.decode()
        except (UnicodeDecodeError, AttributeError):
            pass
        if isinstance(value, str):
            value = value.upper() == "ON"
        value = "ON" if value else "OFF"
    return value
