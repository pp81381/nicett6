import argparse
import json
from pathlib import PurePath

from nicett6.emulator.controller.line_handler import (
    PRESET_POS_1,
    PRESET_POS_2,
    PRESET_POS_3,
    PRESET_POS_4,
    PRESET_POS_5,
    PRESET_POS_6,
)
from nicett6.emulator.cover_emulator import TT6CoverEmulator
from nicett6.ttbus_device import TTBusDeviceAddress


def tt6cover_from_dict(d):
    inverted_endpoints = d.get("inverted_endpoints", False)
    default_initial_pos = 0 if inverted_endpoints else 1000
    cover = TT6CoverEmulator(
        d["name"],
        TTBusDeviceAddress(d["address"], d["node"]),
        d["step_len"],
        d["max_drop"],
        d["speed"],
        d.get("initial_pos", default_initial_pos),
        inverted_endpoints,
    )
    if "preset_pos_1" in d:
        cover.init_preset(PRESET_POS_1, d["preset_pos_1"])
    if "preset_pos_2" in d:
        cover.init_preset(PRESET_POS_2, d["preset_pos_2"])
    if "preset_pos_3" in d:
        cover.init_preset(PRESET_POS_3, d["preset_pos_3"])
    if "preset_pos_4" in d:
        cover.init_preset(PRESET_POS_4, d["preset_pos_4"])
    if "preset_pos_5" in d:
        cover.init_preset(PRESET_POS_5, d["preset_pos_5"])
    if "preset_pos_6" in d:
        cover.init_preset(PRESET_POS_6, d["preset_pos_6"])
    return cover


def default_config_file():
    return str(PurePath(__file__).parent / "config" / "config.json")


def build_config(args=None):
    parser = argparse.ArgumentParser(prog="python -m nicett6.emulator")
    parser.add_argument(
        "-f",
        "--filename",
        type=str,
        default=default_config_file(),
        help="config filename",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=50200, help="port to serve on"
    )
    parser.add_argument(
        "-w",
        "--web_on",
        action="store_const",
        const=True,
        help="emulator starts up in web_on mode",
    )
    parser.add_argument(
        "-W",
        "--web_off",
        action="store_const",
        dest="web_on",
        const=False,
        help="emulator starts up in web_off mode",
    )
    parser.add_argument(
        "-i",
        "--initial_pos",
        action="append",
        nargs=2,
        metavar=("cover_name", "initial_pos"),
        help="override the initial position for cover",
    )
    args = parser.parse_args(args=args)

    with open(args.filename) as fp:
        json_config = json.load(fp)

    web_on = json_config.get("web_on", False) if args.web_on is None else args.web_on

    cover_config_by_name = {}
    if "covers" in json_config:
        for item in json_config["covers"]:
            cover_config_by_name[item["name"]] = item

    if args.initial_pos:
        for cover_name, initial_pos_str in args.initial_pos:
            if cover_name not in cover_config_by_name:
                parser.error(f"Invalid cover_name: {cover_name}")
            cover_config = cover_config_by_name[cover_name]
            try:
                initial_pos = int(initial_pos_str)
            except ValueError:
                parser.error(
                    f"Invalid value specified for {cover_name}: {initial_pos_str}"
                )
            if initial_pos < 0 or initial_pos > 1000:
                parser.error(
                    f"Invalid initial_pos specified for {cover_name} (range is 0 for fully down to 1000 for fully up)"
                )
            cover_config["initial_pos"] = initial_pos

    covers = []
    for c in cover_config_by_name.values():
        covers.append(tt6cover_from_dict(c))

    return {"port": args.port, "web_on": web_on, "covers": covers}
