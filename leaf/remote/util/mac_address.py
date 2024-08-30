def mac_address():
    try:
        import network  # type: ignore

        wlan_sta = network.WLAN(network.STA_IF)
        wlan_sta.active(True)
        wlan_mac = wlan_sta.config("mac")
        mac_address = ":".join([f"{b:02x}" for b in wlan_mac])
        wlan_sta.active(False)
    except ImportError:
        from uuid import getnode as get_mac

        mac_address = ":".join(
            [f"{(get_mac() >> i) & 0xff:02x}" for i in range(0, 48, 8)]
        )

    return mac_address
