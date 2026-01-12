from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

from nicett6.command_code import CommandCode
from nicett6.ttbus_device import TTBusDeviceAddress
from nicett6.utils import hex_arg_to_int, pct_arg_to_int


class InvalidResponseError(Exception):
    pass


@dataclass
class AckResponse:
    tt_addr: TTBusDeviceAddress
    cmd_code: CommandCode

    def __repr__(self):
        return f"{type(self).__name__}({self.tt_addr}, {self.cmd_code})"


@dataclass
class HexPosResponse:
    tt_addr: TTBusDeviceAddress
    cmd_code: CommandCode
    hex_pos: int

    def __repr__(self):
        return f"{type(self).__name__}({self.tt_addr}, {self.cmd_code}, {self.hex_pos:02X})"


@dataclass
class PctPosResponse:
    tt_addr: TTBusDeviceAddress
    pos: int

    def __repr__(self):
        return f"{type(self).__name__}({self.tt_addr}, {self.pos})"


@dataclass
class PctAckResponse:
    tt_addr: TTBusDeviceAddress
    pos: int

    def __repr__(self):
        return f"{type(self).__name__}({self.tt_addr}, {self.pos})"


@dataclass
class InformationalResponse:
    info: str

    def __repr__(self):
        return f"{type(self).__name__}({self.info})"


@dataclass
class ErrorResponse:
    error: str

    def __repr__(self):
        return f"{type(self).__name__}({self.error})"


ResponseMessageType = Union[
    AckResponse,
    HexPosResponse,
    PctPosResponse,
    PctAckResponse,
    InformationalResponse,
    ErrorResponse,
]


def _decode_cmd_response(args: list[str]) -> ResponseMessageType:
    if len(args) < 3:
        raise InvalidResponseError()
    tt_addr = TTBusDeviceAddress(
        hex_arg_to_int(args[0], False), hex_arg_to_int(args[1], False)
    )
    cmd_code: CommandCode = CommandCode(hex_arg_to_int(args[2], False))
    if len(args) == 3:
        return AckResponse(tt_addr, cmd_code)
    elif len(args) == 4 and cmd_code in {CommandCode.READ_POS, CommandCode.MOVE_POS}:
        hex_pos = hex_arg_to_int(args[3], False)
        return HexPosResponse(tt_addr, cmd_code, hex_pos)
    else:
        raise InvalidResponseError()


def _decode_web_pos_or_ack_response(
    args: list[str],
    factory: Callable[[TTBusDeviceAddress, int], Union[PctAckResponse, PctPosResponse]],
) -> ResponseMessageType:
    if len(args) != 6:
        raise InvalidResponseError()
    if args[4] != "FFFF" or args[5] != "FF":
        raise InvalidResponseError()
    tt_addr = TTBusDeviceAddress(
        hex_arg_to_int(args[1], False), hex_arg_to_int(args[2])
    )
    pos = pct_arg_to_int(args[3])
    return factory(tt_addr, pos)


def _decode_web_response(args: list[str], line: str) -> ResponseMessageType:
    if len(args) < 1:
        raise InvalidResponseError()
    cmd_char = args[0]
    if cmd_char == "*":
        return _decode_web_pos_or_ack_response(args, PctPosResponse)
    elif cmd_char == "#":
        return _decode_web_pos_or_ack_response(args, PctAckResponse)
    elif cmd_char == "!":
        # TODO: Attach to specific cover if possible
        return ErrorResponse(line)
    else:
        raise InvalidResponseError()


class Decode:
    EOL = b"\r"

    @classmethod
    def decode_line_bytes(cls, line_bytes: bytes) -> ResponseMessageType:
        if line_bytes.find(cls.EOL) != len(line_bytes) - len(cls.EOL):
            raise InvalidResponseError()

        line: str = line_bytes.decode("utf-8")
        args: list[str] = line.split()
        if len(args) < 1:
            raise InvalidResponseError()
        response_code = args.pop(0)
        if response_code == "RSP":
            return _decode_cmd_response(args)
        elif response_code == "POS":
            return _decode_web_response(args, line)
        elif response_code == "WEB":
            return InformationalResponse(line)
        elif response_code == "ERROR":
            return ErrorResponse(line)
        else:
            raise InvalidResponseError()
