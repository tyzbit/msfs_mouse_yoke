# Device Transmogrifier

This was forked from https://github.com/matiaspedelhez/msfs_mouse_yoke to 
customize a little for Linux and was developed a bit further. The work that was
previously done is greatly appreciated.

This script lets you take any Linux input device that emits relative or absolute
axis values (such as a mouse, PS4 controller or Nintendo Switch joycon) and
emulate them as a more compatible Xbox 360 controller while also allowing for
calibration, input scaling and smoothing input values via 

## How does it work?

The script is always listening for the inputs of a device you pick and 
it transforms that into an xbox controller input. It can do this for two devices
at once (each device is the X and Y of the left or right thumbstick). It also
listens for click events and reads the scroll wheel position from the first
mouse, that way you can use it as a throttle.

## Installation

1. Download and install [Python](https://www.python.org/).
2. Download and install [git](https://git-scm.com/install/).
3. Clone this repo (`git clone https://github.com/tyzbit/msfs_mouse_yoke`)
4. Configure the script as you like! 
  > You can modify the text file 'config.json'
5. sudo apt-get install python3-tk python3-dev
6. pip3 -r requirements.txt

```yaml
# config.yaml
activation_key: Key.shift_r # RIGHT Shift key (near Enter)
center_xy_axes_key: Key.alt_r # RIGHT Alt key (near period)
display_gui: false
start_active: true # If false, the virtual controller won't update until activated
update_frequency: 95 # 95 updates per second or about 10ms
drop_delay_ms: 500 # Drop events that have a timestamp this many ms behind now
skip_old_events: false # If an event happens to arrive after a more recent event, drop it
primary_mouse:
  smoothing: 30 # Delay depends on update_frequency.
  swap_axes: true # Move mouse up -> Y axis increases
  swap_x_for_z: true # Use Z axis instead. To swap for Y, enable swap_axes also.
  absolute: false # Mice don't send absolute values, but controllers might.
  sensitivity: # Multiplier for each axis.
    x: 1
    y: 1
secondary_mouse:
  smoothing: 30
  swap_axes: true
  swap_x_for_z: true
  absolute: true
  sensitivity:
    x: 1
    y: 1
throttle_segments: 10 # 10%, 20%, 30% etc.  20 -> 5%, 10%, 15%, 20%

```

## Usage

It's recommended to start this script before launching Microsoft Flight
Simulator.

 1. python3 mouse_yoke.py [event device ID - optional]
 2. Pick the device to read from if the ID wasn't provided.
 3. To activate the script, press the **master_key**. Default key is comma ",".
 4. If possible, disable the mouse in KDE so you can still use your cursor normally.

Instead of the event device ID you can also provide a string (regex allowed) to
look for a device with that name. This is useful because event device IDs are not
deterministic.

![disable_mouse](disable_mouse.png)
    
![inactive_state](inactive_state.png)


## Keep in mind that...
- When you are setting up the bindings in the game, I recommend removing ALL bindings that are set by default for xbox controllers, and leaving only the axis that you need (which are only two).\
![bindings](bindings.png)

- Clear all the "filters" that the game adds to the xbox controller. Leave it as raw as you can.\
![sensitivity](sensitivity.png)

- If you can disable the mouse in your OS, that's highly recommended (and the
reason this was forked and rewritten in the first place, so the real mouse
wouldn't be manipulated)

- If the map constantly spins, deactivate and then calibrate. Make sure to 
reactivate when you load in.

Happy flying!
