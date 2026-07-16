import pyautogui
import evdev
import natsort

from pynput import keyboard
from reprint import output
from threading import Thread
import time
import vgamepad as vg
import logging
import signal
import sys
import re
import yaml
import time
import tkinter as tk

with open("./config.yaml") as config_file:
    config = yaml.safe_load(config_file)

logging.basicConfig(filename=f"./logs/mouse_yoke.log", format="%(asctime)s - %(message)s", level='INFO')
gamepad = vg.VX360Gamepad()

# X1, X2, Y1, Y2, TX
controller_values = {
    'primary_x': 0.0,
    'primary_y': 0.0,
    'primary_x_offset': 0.0,
    'primary_y_offset': 0.0,
    'secondary_x': 0.0,
    'secondary_y': 0.0,
    'secondary_x_offset': 0.0,
    'secondary_y_offset': 0.0,
    'throttle_x': 0,
    'throttle_x_offset': 0
}
active = config["start_active"]
update_frequency = config['update_frequency'] # Updates per second for controllers
cycletime = 1/update_frequency
calibration_file = './calibration-config.yaml'
event_timestamps = []
events_per_second = 0

# https://www.rawmeat.org/code/python-exponential-smoothing/
def exponential_moving_average(period=int):
    """ Exponential moving average. Smooths the values over the period.  Send
    in values - at first it'll return a simple average, but as soon as it's
    gathered 'period' values, it'll start to use the Exponential Moving
    Averge to smooth the values.

    period: int - how many values to smooth over (default=1000). """
    multiplier = 2 / float(1 + period)
    cumulative_value = yield None  # We are being primed

    # Start by just returning the simple average until we have enough data.
    for i in list(range(1, period + 1)):
        cumulative_value += yield cumulative_value / float(i)

    # Grab the simple average,
    ema = cumulative_value / period

    # and start calculating the exponentially smoothed average we want.
    while True:
        ema = (((yield ema) - ema) * multiplier) + ema

def init_emas():
    global primary_ema_x,primary_ema_y,secondary_ema_x,secondary_ema_y
    primary_ema_x = exponential_moving_average(config['primary_mouse']['smoothing'])
    primary_ema_y = exponential_moving_average(config['primary_mouse']['smoothing'])
    secondary_ema_x = exponential_moving_average(config['secondary_mouse']['smoothing'])
    secondary_ema_y = exponential_moving_average(config['secondary_mouse']['smoothing'])
    # Prime the generators
    next(primary_ema_x)
    next(primary_ema_y)
    next(secondary_ema_x)
    next(secondary_ema_y)

##
# Handles key input to start/stop and calibrate
##
def onKeyRelease(key=keyboard.KeyCode):
    global active
    global controller_values
    global primary_ema_x,primary_ema_y,secondary_ema_x,secondary_ema_y
    ov = controller_values

    # Alphanumeric keys get printed with single quotes
    if str.replace(f'{key}', "'", "") == config["activation_key"]:
        active = not active
        logging.info(f'Active: {active}')

    if str.replace(f'{key}', "'", "") == config["center_xy_axes_key"]:
        logging.info(f'Centering axes')
        gamepad.left_joystick_float(0,0)
        gamepad.right_joystick_float(0,0)
        gamepad.update()
        for i in range(config['primary_mouse']['smoothing']):
            primary_ema_x.send(0)
            primary_ema_y.send(0)
        for i in range(config['secondary_mouse']['smoothing']):
            secondary_ema_x.send(0)
            secondary_ema_y.send(0)
        controller_values = {
            'primary_x': 0.0,
            'primary_y': 0.0,
            'primary_x_offset': ov['primary_x']+ov['primary_x_offset'],
            'primary_y_offset': ov['primary_y']+ov['primary_y_offset'],
            'secondary_x': 0.0,
            'secondary_y': 0.0,
            'secondary_x_offset': ov['secondary_x']+ov['secondary_x_offset'],
            'secondary_y_offset': ov['secondary_y']+ov['secondary_y_offset'],
            'throttle_x': 0.0,
            'throttle_x_offset': ov['throttle_x']
        }
        calibration_config = {
            "primary_mouse_x": 0,
            "primary_mouse_y": 0,
            "secondary_mouse_x": 0,
            "secondary_mouse_y": 0
        }
        calibration_config['primary_mouse_x'] = ov['primary_x']+ov['primary_x_offset']
        calibration_config['primary_mouse_y'] = ov['primary_y']+ov['primary_y_offset']
        calibration_config['secondary_mouse_x'] = ov['secondary_x']+ov['secondary_x_offset']
        calibration_config['secondary_mouse_y'] = ov['secondary_y']+ov['secondary_y_offset']
        with open(calibration_file, 'w+') as test_config:
            test_config.truncate(0)
            test_config.write(yaml.dump(calibration_config))
        

##
# Draws the simple terminal interface
## 
def userInterface():
    with output(initial_len=11, interval=0) as output_lines:
        while True:
            global controller_values
            px = controller_values['primary_x']
            py = controller_values['primary_y']
            sx = controller_values['secondary_x']
            sy = controller_values['secondary_y']
            tx = controller_values['throttle_x']
            output_lines[0] = f"+{' Status: ' + ('ACTIVE' if active else 'INACTIVE') + ' ':—^40}+"
            output_lines[1] = f"|{'':^40}|"
            output_lines[2] = f"|{'Axis':^20}{'Position':^20}|"
            output_lines[3] = f"+{'':—^40}+"
            output_lines[4] = f"|{'X1':^20}{'{:.2f}'.format((px + 1) * 50) + '%':^20}|"
            output_lines[5] = f"|{'Y1':^20}{'{:.2f}'.format((py + 1) * 50) + '%':^20}|"
            output_lines[6] = f"|{'X2':^20}{'{:.2f}'.format((sx + 1) * 50) + '%':^20}|"
            output_lines[7] = f"|{'Y2':^20}{'{:.2f}'.format((sy + 1) * 50) + '%':^20}|"
            output_lines[8] = f"|{'THROTTLE':^20}{'{:.2f}'.format((tx / config['throttle_segments']) * 100) + '%':^20}|"
            output_lines[9] = f"|{'EVENTS PER SECOND':^20}{'{:.2f}'.format(events_per_second):^20}|"
            output_lines[10] = f"+{'':—^40}+"

            time.sleep(0.1)


class ColorDisplayApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Mouse Yoke")
        self.master.geometry("100x50")

        self.namelabel = tk.Label(self.master, text="Mouse Yoke", font=('Consolas', 8) , anchor="center", justify="center")
        self.label = tk.Label(self.master, text="", font=('Consolas', 16), anchor="center", justify="center")
        self.namelabel.pack(pady=0)
        self.label.pack(pady=0)

        self.master.after(100, self.update_display)
        
        self.master.attributes('-topmost', True)
        self.master.overrideredirect(True)


    def update_display(self):
        if active:
            self.label.config(bg="red")
            self.master.configure(bg="red")

            self.label.config(text = "ACTIVE")
            self.master.attributes('-alpha', 1)
        else:
            
            self.label.config(bg="gray")
            self.master.configure(bg="gray")

            self.label.config(text = "")
            self.master.attributes('-alpha', 0.5)
        self.master.after(100, self.update_display)


##
# Reads mouse input and updates gamepad values. The actual gamepad update happens elsewhere.
# device_name: primary/secondary
# device_descriptor: number of event device or partial device name to be regexed
# throttle: enable/disable use of scroll wheel for throttle
##
def mouseLoop(device_name=str, device_descriptor=str, throttle=bool):
    global controller_values, config, event_timestamps, events_per_second
    global primary_ema_x,primary_ema_y,secondary_ema_x,secondary_ema_y
    x = f'{device_name}_x'
    y = f'{device_name}_y'
    if config[f'{device_name}_mouse']['swap_axes']:
        x,y = y,x
        logging.warning('swapping axes')
    if config[f'{device_name}_mouse']['swap_x_for_z']:
        logging.warning('swapping X for Z')
    if config[f'{device_name}_mouse']['absolute']:
        logging.warning('absolute mode in use')
    tx = 'throttle_x'
    
    while True:
        if not device_descriptor.isdigit():
            devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
            for device in devices:
                if re.search(device_descriptor, device.name, re.IGNORECASE):
                    logging.info(f'{device.name} matches {device_descriptor}, selecting')
                    device = evdev.InputDevice(device.path)
                    break
        else:
            logging.info(f'Device selected manually: {device_descriptor}')
            device = evdev.InputDevice(f'/dev/input/event{device_descriptor}')
        
        # Test that the device works
        if not device.info.vendor:
            time.sleep(1)
            continue
        absolute_degrees = device.absinfo(evdev.ecodes.ABS_X).max - device.absinfo(evdev.ecodes.ABS_X).min
        logging.info(f'{device_name} device initialized')
        try:
            for event in device.read_loop():
                match event.type:
                    case evdev.ecodes.EV_REL:
                        if not config[f'{device_name}_mouse']['absolute']:
                            match event.code:
                                case evdev.ecodes.REL_X:
                                    sensitivity = config[f'{device_name}_mouse']['sensitivity']['x']
                                    controller_values[x] = controller_values[x] + (event.value * sensitivity)
                                    # The offset for relative controllers should always be zero
                                    controller_values[f'{x}_offset'] = 0
                                case evdev.ecodes.REL_Y:
                                    sensitivity = config[f'{device_name}_mouse']['sensitivity']['y']
                                    controller_values[y] = controller_values[y] + (event.value * sensitivity)
                                    # The offset for relative controllers should always be zero
                                    controller_values[f'{y}_offset'] = 0
                                case evdev.ecodes.REL_WHEEL:
                                    if throttle:
                                        controller_values[tx] = max(0, min(controller_values[tx] + event.value, config['throttle_segments']))
                                        # ensure between 0.0 and 1.0
                                        gamepad.left_trigger_float(value_float=(controller_values[tx] / config['throttle_segments']))

                    case evdev.ecodes.EV_ABS:
                        if config[f'{device_name}_mouse']['absolute']:
                            match event.code:
                                case evdev.ecodes.ABS_X:
                                    if not config[f'{device_name}_mouse']['swap_x_for_z']:
                                        sensitivity = config[f'{device_name}_mouse']['sensitivity']['x']
                                        raw_x = (event.value * sensitivity + (absolute_degrees/2)) / absolute_degrees/2
                                        controller_values[x] = raw_x - 1 - controller_values[f'{x}_offset']
                                case evdev.ecodes.ABS_Y:
                                    sensitivity = config[f'{device_name}_mouse']['sensitivity']['y']
                                    raw_y = (event.value * sensitivity + (absolute_degrees/2)) / absolute_degrees/2
                                    controller_values[y] = raw_y - 1 - controller_values[f'{y}_offset']
                                case evdev.ecodes.ABS_Z:
                                    if config[f'{device_name}_mouse']['swap_x_for_z']:
                                        sensitivity = config[f'{device_name}_mouse']['sensitivity']['x']
                                        raw_x = (event.value * sensitivity + (absolute_degrees/2)) / absolute_degrees/2
                                        controller_values[x] = raw_x - 1 - controller_values[f'{x}_offset']
                        else:
                            match event.code:
                                case evdev.ecodes.ABS_RX:
                                    sensitivity = config[f'{device_name}_mouse']['sensitivity']['x']
                                    controller_values[x] = controller_values[x] + (event.value * sensitivity)
                                    # The offset for relative controllers should always be zero
                                    controller_values[f'{x}_offset'] = 0
                                case evdev.ecodes.ABS_RY:
                                    sensitivity = config[f'{device_name}_mouse']['sensitivity']['y']
                                    controller_values[y] = controller_values[y] + (event.value * sensitivity)
                                    # The offset for relative controllers should always be zero
                                    controller_values[f'{y}_offset'] = 0

                    case evdev.ecodes.EV_KEY:
                        match event.code:
                            case evdev.ecodes.BTN_LEFT | evdev.ecodes.BTN_EAST:
                                if event.value == 1:
                                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                                else:
                                    gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                            case evdev.ecodes.BTN_RIGHT | evdev.ecodes.BTN_WEST:
                                if event.value == 1:
                                    gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                                else:
                                    gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)

                event_timestamps.append(event.timestamp())
                now = time.time()
                events_per_second = 0
                new_events = []
                for ts in event_timestamps:
                    if ts > now - 1:
                        events_per_second += 1
                        new_events.append(ts)
                event_timestamps = new_events

                # ensure between -1.0 and 1.0a
                controller_values[x] = max(-1.0, min(controller_values[x], 1.0))
                controller_values[y] = max(-1.0, min(controller_values[y], 1.0))
                if device_name == 'primary':
                    controller_values[x] = primary_ema_x.send(controller_values[x])
                    controller_values[y] = primary_ema_y.send(controller_values[y])
                    gamepad.left_joystick_float(x_value_float=controller_values[x], y_value_float=controller_values[y])
                else:
                    controller_values[x] = secondary_ema_x.send(controller_values[x])
                    controller_values[y] = secondary_ema_y.send(controller_values[y])
                    gamepad.right_joystick_float(x_value_float=controller_values[x], y_value_float=controller_values[y])
        except Exception as e:
            logging.warning(f'Error with {device_name}, attempting to reacquire: {e}')
            continue

##
# Updates the gamepad on an accurate, consistent frequency.
# https://github.com/yannbouteiller/vgamepad/issues/39#issuecomment-3100989230
##
def gamepadloop():
    t0 = time.perf_counter()    # Time ref point in ms
    time_counter = t0           # Will be incremented with cycletime for each iteration

    while 1:
        ### Code that will read message bytes from a port

        now = time.perf_counter()
        elapsed_time = now - time_counter
        if elapsed_time < cycletime:
            target_time =  cycletime - elapsed_time
            time.sleep(target_time)
        
        # It's time to update the game pad
        if active:
            gamepad.update()

        time_counter += cycletime

##
# Handles the graphical GUI for showing active status
##
def runTK():
    if(not config['display_gui']):
        return
    root = tk.Tk()
    app = ColorDisplayApp(root)
    root.mainloop()

if __name__ == "__main__":
    logging.warning("mouse_yoke.py is now running\n\n")
    init_emas()

    try:
        primary_device = evdev.InputDevice
        secondary_device = evdev.InputDevice
        secondary_device_enabled = False

        if len(sys.argv) == 3:
            logging.info('Using two devices')
            primary_device_number = sys.argv[1]
            secondary_device_number = sys.argv[2]
            secondary_device_enabled = True
        elif len(sys.argv) == 2:
            logging.info('Using one device')
            primary_device_number = sys.argv[1]
        else:
            logging.info('Letting the user choose the devices')
            devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
            for device in natsort.natsorted(devices, key=lambda d: d.path):
                print(device.path, device.name)
            primary_device_number = input(f'Enter the number of the first mouse to read from: ')
            secondary_device_number = input(f'Enter the number of the second mouse to read from (Enter to skip): ')
            if secondary_device_number:
                logging.info('Secondary device enabled')
                secondary_device_enabled = True

        pyautogui.FAILSAFE = False
        ui = Thread(target=userInterface)
        # offsets only matter for absolute devices
        with open(calibration_file) as calibration:
            calibration_config = yaml.safe_load(calibration)
            controller_values['primary_x_offset'] = calibration_config['primary_mouse_x']
            controller_values['primary_y_offset'] = calibration_config['primary_mouse_y']
            controller_values['secondary_x_offset'] = calibration_config['secondary_mouse_x']
            controller_values['secondary_y_offset'] = calibration_config['secondary_mouse_y']
        pm = Thread(target=mouseLoop, args=['primary',primary_device_number,True])
        gl = Thread(target=gamepadloop)
        if secondary_device_enabled:
            sm = Thread(target=mouseLoop, args=['secondary',secondary_device_number,False])
        kb = keyboard.Listener(on_release=onKeyRelease)
        tl = Thread(target=runTK)
        
        pm.start()
        if secondary_device_enabled:
            sm.start()
        ui.start()
        kb.start()
        tl.start()
        gl.start()
        # Explicitly wait for SIGINT, once caught exit
        signal.signal(signal.SIGINT, sys.exit(0))
        signal.pause

    except Exception as e:
        logging.critical(f'Exception occurred: {e}', exc_info=True)
