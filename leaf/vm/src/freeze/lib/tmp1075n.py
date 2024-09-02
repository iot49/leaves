from micropython import const

# based on https://github.com/mattytrentini/micropython-tmp1075


class TMP1075N:

    '''
    MicroPython Driver for the TI TMP1075N temperature sensor.

    Example:

        i2c = I2C(sda=Pin(33), scl=Pin(32), freq=400000)
        tmp1075n = TMP1075N(i2c)
        tmp1075n.get_temperature()

    See datasheet: http://www.ti.com/lit/ds/symlink/tmp1075.pdf
    
    '''
    REG_TEMP  = const(0x00)
    REG_CFGR  = const(0x01)
    REG_LLIM  = const(0x02)
    REG_HLIM  = const(0x03)
    REG_DIEID = const(0x0F)
        
    def __init__(self, i2c, addr=0x48):
        self._i2c = i2c
        self._addr = addr			  
        self._temp2 = bytearray(2)

    def get_temperature(self):
        # temperature in degrees Celcius
        t = self._read_register(TMP1075N.REG_TEMP)
        t = t if t < 32768 else t - 65536
        return (t >> 4) * 0.0625
        
    def _read_register(self, register):
        self._i2c.readfrom_mem_into(self._addr, register, self._temp2)
        return (self._temp2[0] << 8) | self._temp2[1]

