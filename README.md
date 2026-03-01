# nicett6

An asyncio based package to talk to a Nice TT6 control unit for tubular motors using the RS-232 protocol

The Nice TT6 control unit is used to control projector screens, garage doors, awnings and blinds.   It is white labelled by Screen Research as the MCS-N-12V-RS232 projector screen controller and by Beamax as the 11299 projector screen controller.

See [this document](https://www.niceforyou.com/sites/default/files/upload/manuals/IS0064A00MM.pdf) for the protocol definition

Known to work with a GANA USB to RS-232 DB9 cable on Windows 10 and on Raspbian Stretch

# Contents

* [Basic Control API](#Basic-Control-API)
* [High Level Cover API](#High-Level-Cover-API)
* [High Level CIW API](#High-Level-CIW-API) (to manage a Constant Image Width configuration with a screen and a mask)
* [Emulator](#Emulator)
* [Examples](#Examples)
* [Notes](#Notes)


# Basic Control API

## Opening a connection

`nicett6.tt6_connection.open([serial_port])` opens a connection to the TT6 controlled connected to `serial_port`

`nicett6.tt6_connection.open_connection([serial_port])` opens a connection and acts as an async context manager

If `serial_port` is not supplied or is `None` then an intelligent guess will be made as to the right parameter depending on the platform

The serial_port parameter can be anything that can be passed to `serial.serial_for_url()`.  E.g.

* `/dev/ttyUSB0` (Linux)
* `COM3` (Windows)
* `socket://192.168.0.100:50000` (if you are using a TCP/IP to serial  converter)

Returns a `TT6Connection`

Example:

```python
    async with open_connection(serial_port) as conn:
        tt_addr = TTBusDeviceAddress(0x02, 0x04)
        writer = conn.get_writer()
        await writer.send_hex_move_command(tt_addr, 0xE0)
```

## TT6Connection

A class that allows multiple readers and writers to a single serial connection.

The lifecycle of the connection is managed by the client as opposed to closing upon receipt of an EOF from the device.
If the connection is disconnected by either end then readers wait for the next message and writers will discard any messages sent.
Once the connection is re-connected then normal service resumes.  The client can terminate the connection by calling `close()`.

See [Opening a connection](#opening-a-connection) for information on opening a connection.

Property|Description
--|--
`is_connected`|Indicates whether the connection is connected

Method|Description
--|--
`connect()`|Establish or re-establish the connection.
`disconnect()`|Break the connection but do not stop any readers or writers.
`close()`|Stop and remove all readers (they will stop iterating).   Disconnect.
`add_reader()`|Returns a new reader object.<br>If the connection was created by `open_connection` then this will be a `TT6Reader` object.<br>The serial connection retains a weak reference to the reader in order to keep it updated.  A reader that is no longer needed can either be dereferenced or explicitly removed.
`remove_reader(reader)`|Stops the `reader` object from receiving any further messages
`get_writer()`|Returns a new writer object.   If the connection was created by `open_connection` then this will be a `TT6Writer` object.<br>The base class manages contention between multiple potential clients of the same connection.<br>Writer objects do not take any resources and can simply be dereferenced when finished with
`process_request(coro, [time_window])`|Send a command and collect the response messages that arrive in time_window

## TTBusDeviceAddress

A simple class that represents the address of a TTBus device - to be used for `tt_addr` paramters

Supports comparison with other objects of the same class

Can be used as a key in a mapping type

Property|Description
--|--
`address`|the address of the device on the TTBus
`node`|the device node (usually 0x04)
`as_tuple`|a tuple of `(address, node)`

<br>

Example:

```python
tt_addr = TTBusDeviceAddress(0x02, 0x04)
```

## TT6Reader

A reader that will collect all decoded messages received on the `TT6Connection` in a queue until it is removed

A `TT6Reader` is an asynchronous iterator returning [response message objects](#Response-message-classes)

Usage:

```python
    async for msg in reader:
        # Do something with msg
```

## Response message classes

### AckResponse

Sent by the controller to acknowledge receipt of a simple command

Property|Description
--|--
`tt_addr`|the `TTBusDeviceAddress` of the TTBus device
`cmd_code`|the command being acknowledged

### HexPosResponse

Sent by the controller in response to a `READ_POS` command

Property|Description
--|--
`tt_addr`|the `TTBusDeviceAddress` of the TTBus device
`cmd_code`|the command being acknowledged
`hex_pos`|the position as a value between 0x00 (fully down) and 0xFF (fully up)

### PctPosResponse

Sent by the controller in response to a "web position request"

Property|Description
--|--
`tt_addr`|the `TTBusDeviceAddress` of the TTBus device
`pos`|the position as a value between 0 (fully down) and 1000 (fully up)

### InformationalResponse

An informational response from the controller

Typically used to acknowledge a non-device-specific command such as `WEB_ON` or `WEB_OFF`

Property|Description
--|--
`info`|the informational message

### ErrorResponse

An error response from the controller

Property|Description
--|--
`error`|the error message

## TT6Writer

Method|Description
--|--
`send_web_on()`|Send the WEB_ON command to the controller to enable web commands and to instruct the controller to send the motor positions as they move
`send_web_off()`|Send the WEB_OFF command to the controller to disable web commands and to instruct the controller not to send the motor positions as they move
`send_simple_command(tt_addr, cmd_name)`|Send `cmd_name` to the TTBus device at `tt_addr`<br>See the table below for a list of all valid `cmd_name` values
`send_hex_move_command(tt_addr, hex_pos)`|Instruct the controller to move the TTBus device at `tt_addr` to `hex_pos`<br>`hex_pos` is a value between 0x00 (fully down) and 0xFF (fully up)
`send_web_move_command(tt_addr, pos)`|Instruct the controller to move the TTBus device at `tt_addr` to `pos`<br>`pos` is a value between 0 (fully down) and 1000 (fully up)<br>Out of range values for `pos` will be rounded up or down accordingly<br>Web commands must be enabled for this command to work
`send_web_pos_request(tt_addr)`|Send a request to the controller to send the position of the TTBus device at `tt_addr`<br>Web commands must be enabled for this command to work

#### Command Codes

Command codes for `send_simple_command`:

Code|Meaning
--|--
`READ_POS`|Request the current position<br>Controller will send a value between 0x00 (fully down) and 0xFF (fully up) 
`STOP`|Stop
`MOVE_DOWN`|Move down
`MOVE_UP`|Move up
`MOVE_POS_<n>`|Move to preset `n` where `n` is between 1 and 6
`STORE_POS_<n>`|Store current position to preset `n` where `n` is between 1 and 6
`DEL_POS_<n>`|Clear preset `n` where `n` is between 1 and 6
`MOVE_DOWN_STEP`|Move down the smallest possible step (web pos is not reported by controller)
`MOVE_UP_STEP`|Move up the smallest possible step (web pos is not reported by controller)

<br>Usage:

```python
    writer = conn.get_writer()
    writer.send_web_move_command(1.0)
```

Usage of `process_request()`:

```python
    coro = writer.send_simple_command(tt_addr, "READ_POS")
    messages = await writer.process_request(coro)
```

Note that there could be unrelated messages received if web commands are enabled or if another command has just been submitted

# High level Cover API

A set of components to provide a high level interface to manage a Cover.    Could be used to control a retractable projector screen or a garage door.  Designed for use with Home Assistant.

Component|Description
--|--
`CoverManager`|A class that manages the controller connection and a set of covers<br>Can be used as an async context manager
`Cover`|A sensor class that can be used to monitor the position of a cover
`TT6Cover`|Class that sends commands to a `Cover` that is connected to the TTBus
`PostMovementNotifier`|Helper class that resets a cover to idle after movement has stopped

<br>Example (also see [example3.py](#Examples) below):

```python
async def log_cover_state(cover):
    try:
        while cover.is_moving:
            _LOGGER.info(
                f"drop: {cover.drop}; "
                f"is_going_up: {cover.is_going_up}; "
                f"is_going_down: {cover.is_going_down}; "
            )
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass

async def example(serial_port):
    tt_addr = TTBusDeviceAddress(0x02, 0x04)
    max_drop = 2.0
    async with CoverManager(serial_port) as mgr:
        tt6_cover = await mgr.add_cover(tt_addr, Cover("Cover", max_drop))

        message_tracker_task = asyncio.create_task(mgr.message_tracker())
        logger_task = asyncio.create_task(log_cover_state(tt6_cover.cover))

        await tt6_cover.send_pos_command(900)
        await wait_for_motion_to_complete([tt6_cover.cover])

        await tt6_cover.send_simple_command("MOVE_UP")
        await wait_for_motion_to_complete([tt6_cover.cover])

        logger_task.cancel()
        await logger_task

    await message_tracker_task
```

## CoverManager

A class that manages the connection and a set of covers

Can be used as an async context manager

Constructor parameters:

Parameter|Description
--|--
`serial_port`|The serial port to use.  See [Opening a connection](#opening-a-connection) for the valid values.

Property|Description
--|--
`serial_port`|The serial port in use
`tt6_covers`|All of the `TT6Cover` objects that have been added (the returned object is a `ValuesView` onto the internal dict)

Method|Description
--|--
`open()`|Open the connection<br>Called automatically if the object is used as a context manager
`close()`|Close the connection<br>Called automatically if the object is used as a context manager
`message_tracker()`|A coroutine that must be running in the background for the manager to be able to track cover positions
`add_cover(tt_addr, cover)`|Add a cover to be managed<br>tt_addr is the TTBus address of the cover<br>The connection must be open so that the initial position can be requested
`remove_covers()`|Remove all covers and clean up

## Cover

A sensor class that can be used to monitor the position of a cover.  Could be used to monitor a retractable projector screen or a garage door.  Designed for use with Home Assistant.

Cover is an `AsyncObservable` and will notify any attached objects of type `AsyncObserver` if the position is changed

Constructor parameters:

Parameter|Description
--|--
`name`|name of cover (for logging purposes)
`max_drop`|maximum drop of cover in metres
`inverted_endpoints`|fully up is 0 and fully down is 1000

<br>
Example:

```python
cover = Cover("Screen", 2.0)
```

<br>
Has the following properties and methods:

Property|Description
--|--
`pos`|the cover position (0 = fully down, 1000 = fully up)
`drop`|drop in metres (0.0 = fully up, max_drop = fully down)
`is_moving`|returns True if the cover has moved recently
`is_fully_up`|returns True if the cover is fully up
`is_fully_down`|returns True if the cover is fully down
`is_going_up`|returns True if the cover is going up<br>will only be meaningful after the position has been set by the first POS message coming back from the cover for a movement
`is_going_down`|returns True if the cover is going down<br>will only be meaningful after the position has been set by the first POS message coming back from the cover for a movement


Method|Description
--|--
`set_pos`|Set the position (0 = fully down, 1000 = fully up) - async<br>Will notify observers of the state change
`moved()`|Called to indicate movement<br>When initiating movement, call `moved()` so that `is_moving` will be meaningful in the interval before the first POS message comes back from the cover<br>Will notify observers of the state change
`set_idle()`|Called to indicate that the cover is idle<br>After detecting that the cover is idle, call `set_idle()` so that the next movement direction will be correctly inferred<br>Will notify observers of the state change

Helper|Description
--|--
`wait_for_motion_to_complete(covers)`|Waits for motion of a list of covers to complete<br>Has side effect of notifying observers of the cover when it goes idle


## TT6Cover

Class that sends commands to a `Cover` that is connected to the TTBus

Intended to be constructed by `CoverManager.add_cover()`

Property|Description
--|--
`tt_addr`|the TTBus address of the Cover
`cover`|the `Cover` helper
`writer`|the low level `TT6Writer`

Method|Description
--|--
`send_pos_request()`|Send a POS request to the controller
`send_pos_command(pos)`|Send a POS command to the controller to set the position of the Cover to `pos`<br>`pos` should be between 0 (fully down) and 1000 (fully up)<br>Out of range values for `pos` will be rounded up/down accordingly
`send_hex_move_command()`|Send a POS command to the controller to set the position of the Cover to `hex_pos`<br>`hex_pos` is a value between 0x00 (fully down) and 0xFF (fully up)
`send_simple_command(cmd_name)`|Send a [simple command](#command-codes) to the controller for the Cover

## PostMovementNotifier

Helper class that resets a cover to idle after movement has stopped

Documented here for completeness but intended to be constructed by and internal to the `Cover`

Most state changes of a `Cover` will be triggered by the receipt of a POS message.  The `Cover` infers that there is movement when a message is received and infers the direction from the current and previous message.   However, there is no notification that the `Cover` is idle so the `PostMovementNotifier` class detects that there has been no movement for a period and then calls `Cover.set_idle()`.  The `Cover` will then notify its observers that it is idle.

Whenever the `Cover` moves, there is a call to `Cover.moved()` which calls `PostMovementNotifier.moved()`.  A task is created that will wait for a period and then set the `Cover` to idle.   If a task was already running when the movement notification is received then the task will be cancelled and restarted.

The task must sleep for `Cover.MOVEMENT_THRESHOLD_INTERVAL + PostMovementNotifier.POST_MOVEMENT_ALLOWANCE` seconds without being cancelled for the `Cover` to be considered idle.


# Projector Screen Helpers

Helper classes to manage a projector screen composed of multiple covers such as a screen with a mask

Component|Description
--|--
`ImageDef`|A class that describes where the image area is located on a cover that is a screen
`CIWHelper`|A sensor class that tracks the positions of a screen and mask<br>Has properties to represent the visible image area

## ImageDef

A class that describes where the image area is located on a cover that is a screen

Constructor parameters:

Parameter|Description
--|--
`bottom_border_height`|gap in metres between bottom of image and bottom of cover
`height`|height of image
`aspect_ratio`|aspect ratio of image

<br>
Example:

```python
image_def = ImageDef(0.05, 2.0, 16 / 9)
```

<br>Has the following properties and methods:

Property|Description
--|--
`width`|implied image width


Method|Description
--|--
`implied_image_height(target_aspect_ratio)`|implied height for `target_aspect_ratio` if the width is held constant
<br>

## CIWHelper

A sensor class that represents the positions of a screen and mask

Constructor parameters:

Parameter|Description
--|--
`screen`|A `Cover` sensor object representing the screen
`mask`|A `Cover` sensor object representing the mask
`image_def`|An `ImageDef` object describing where the image area on the screen cover is

Properties:

Property|Description
--|--
`image_width`|the width of the visible image in metres
`image_height`|the height of the visible image in metres or `None` if the image is not visible
`image_diagonal`|the diagonal of the visible image in metres or `None` if the image is not visible
`image_area`|the area of the visible image in square metres or `None` if the image is not visible
`image_is_visible`|True if the image area is visible or `None` if the image is not visible
`aspect_ratio`|The aspect ratio of the visible image or `None` if the image is not visible

# Emulator

The package also includes an emulator that can be used for demonstration or testing purposes

Example:

```
python -m nicett6.emulator
```

Usage:

```
usage: python -m nicett6.emulator [-h] [-f FILENAME] [-p PORT] [-w] [-W]
                   [-i cover_name initial_pos]

optional arguments:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        config filename
  -p PORT, --port PORT  port to serve on
  -w, --web_on          emulator starts up in web_on mode
  -W, --web_off         emulator starts up in web_off mode
  -i cover_name initial_pos, --initial_pos cover_name initial_pos
                        override the initial position for cover
```

A sample `config.json` file is provided in the `emulator/config` folder

Sample config:

```json
{
    "web_on": false,
    "covers": [
        {
            "address": 2,
            "node": 4,
            "name": "screen",
            "step_len": 0.01,
            "max_drop": 1.77,
            "speed": 0.08
        },
        {
            "address": 3,
            "node": 4,
            "name": "mask",
            "step_len": 0.01,
            "max_drop": 0.6,
            "speed": 0.08
        },
        {
            "address": 10,
            "node": 4,
            "name": "blind",
            "step_len": 0.01,
            "max_drop": 2.0,
            "speed": 0.08
        },
        {
            "address": 11,
            "node": 4,
            "name": "inverse blind",
            "step_len": 0.01,
            "max_drop": 2.0,
            "speed": 0.08,
            "inverted_endpoints": true
        }
    ]
}
```

# Examples

The following examples can be used in conjunction with the [Emulator](#Emulator)

* `example2.py` - shows how to use the [Basic Control API](#Basic-Control-API)
* `example3.py` - shows how to use the [High Level Cover API](#High-Level-Cover-API)

# Utilities

## Movement Timing Logger

The script `movement_timing_logger.py` can be used to see how often the controller publishes POS messages as it moves.   It will move the specified Cover down and then back up and log the time between messages.   This can be used to tune `Cover.MOVEMENT_THRESHOLD_INTERVAL` so that `Cover.is_moving` is accurate.

```
usage: movement_timing_logger.py [-h] [-s SERIAL_PORT] [-a {2,3}]

optional arguments:
  -h, --help            show this help message and exit
  -s SERIAL_PORT, --serial_port SERIAL_PORT
                        serial port
  -a {2,3}, --address {2,3}
                        device address
```

# Notes

## End of Line (EOL) characters

The protocol definition specifies that all messages end in a carriage return character but in practice the controller seems to use carriage return plus line feed.

For convenience the API can handle either.

* The API will write to the controller with messages ending in carriage return
* The API will handle messages from the controller with either line ending
* The emulator will handle inbound commands with either line ending
* The emulator will send responses ending in carriage return and line feed

## Measurement units

This document refers to metres as the unit of measurement for all absolute measurements but you can use mm, cm, inches or feet as long as you are consistent
