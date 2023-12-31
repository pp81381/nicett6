from enum import Enum


class CommandCode(Enum):
    STOP = 0x03
    MOVE_DOWN = 0x04
    MOVE_UP = 0x05
    MOVE_POS_1 = 0x06
    MOVE_POS_2 = 0x07
    MOVE_POS_3 = 0x08
    MOVE_POS_4 = 0x09
    MOVE_POS_5 = 0x10
    MOVE_POS_6 = 0x11
    MOVE_UP_STEP = 0x12
    MOVE_DOWN_STEP = 0x13
    STORE_POS_1 = 0x22
    STORE_POS_2 = 0x23
    STORE_POS_3 = 0x24
    STORE_POS_4 = 0x25
    STORE_POS_5 = 0x26
    STORE_POS_6 = 0x27
    DEL_POS_1 = 0x32
    DEL_POS_2 = 0x33
    DEL_POS_3 = 0x34
    DEL_POS_4 = 0x35
    DEL_POS_5 = 0x36
    DEL_POS_6 = 0x37
    MOVE_POS = 0x40
    READ_POS = 0x45
