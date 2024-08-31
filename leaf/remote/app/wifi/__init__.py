from util import is_micropython

class WifiException(Exception):
    pass

if is_micropython():
    print("Using micropython wifi")
    from .micropython_wifi import Radio, Wifi
else:
    from .cpython_wifi import Radio, Wifi