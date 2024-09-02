# Leaf01

# I2C addresses:
# INA3221        0x40
# ADS1015        0x48
# TMP1075        0x49  BUG: 1st rev board: 0x48, clash with ADS1015
# BMI270         0x68

# I2C bus
SDA              =  1
SCL              =  2

# Console (serial)
U0TXD            = 43
U0RXD            = 44

# GPS
GPS_RX           = 10
GPS_TX           = 11

# Canbus
CAN_RXD          = 14
CAN_TXD          = 21

# IMU BMI270
IMU_INT1         = 18
IMU_INT2         =  8

# ADS1015
ADC_ALERT        =  9

# INA3221
INA3221_CRITICAL = 12
INA3221_WARNING  = 13

# FRAM
FRAM_CS          =  7
FRAM_SCK         =  6
FRAM_MOSI        =  5
FRAM_MISO        = 15
FRAM_WP          = 16

# LED (Neopixel)
LED              =  4