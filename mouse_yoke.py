from pyautogui import size, moveTo
import pyautogui
import evdev
import natsort

from pynput import keyboard
from reprint import output
from threading import Thread
from datetime import timezone 
import datetime
import time
import vgamepad as vg
import logging
import signal
import sys
import json
import time
import tkinter as tk


with open("./config.json") as config_file:
    configs = json.load(config_file)

logging.basicConfig(filename=f"./logs/mouse_yoke.log", format="%(asctime)s - %(message)s")
gamepad = vg.VX360Gamepad()

# X1, X2, Y1, Y2, TX
controller_values = {
    'primary_x': 0.0,
    'primary_y': 0.0,
    'secondary_x': 0.0,
    'secondary_y': 0.0,
    'throttle_x': 0
}
active = False
update_frequency = 100
cycletime = 1/update_frequency

##
# Handles key input to start/stop and calibrate
##
def onKeyRelease(key):
    global active
    global primary_JoystickFloatX, primary_JoystickFloatY, secondary_JoystickFloatX, secondary_JoystickFloatY

    if key == keyboard.KeyCode.from_char(configs["master_key"]):
        active = not active
        logging.info(f'Active: {active}')

    if key == keyboard.KeyCode.from_char(configs["center_xy_axes_key"]):
        logging.info(f'Centering axes')
        global controller_values
        controller_values = {
            'primary_x': 0.0,
            'primary_y': 0.0,
            'secondary_x': 0.0,
            'secondary_y': 0.0,
            # Throttle is not zeroed
            'throttle_x': controller_values['throttle_x']
        }

##
# Draws the simple terminal interface
## 
def userInterface():
    global primary_JoystickFloatX, primary_JoystickFloatY, secondary_JoystickFloatX, secondary_JoystickFloatY
    with output(initial_len=10, interval=0) as output_lines:
        while True:
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
            output_lines[8] = f"|{'THROTTLE':^20}{'{:.2f}'.format((tx / configs['throttle_segments']) * 100) + '%':^20}|"
            output_lines[9] = f"+{'':—^40}+"

            time.sleep(0.05)


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
# Reads mouse input and updates gamepad values. The actual gamepad update happens elsewhere
##
def mouseLoop(device_name=str, device_fd=int, throttle=bool):
    x = f'{device_name}_x'
    y = f'{device_name}_y'
    tx = 'throttle_x'
    sens = f'{device_name}_mouse_sensitivity'
    global controller_values

    try:
        device = evdev.InputDevice(f'/dev/input/event{device_fd}')
    except Exception as e:
        logging.critical(f'Event device {device_name} (/dev/input/event{device_fd}) could not be opened: {e}', exec_info=True)
        return
    for event in device.read_loop():
        match event.type:
            case evdev.ecodes.EV_REL:
                match event.code:
                    case evdev.ecodes.REL_X:
                        controller_values[x] = controller_values[x] + (event.value * configs[f'{sens}_x'])
                    case evdev.ecodes.REL_Y:
                        controller_values[y] = controller_values[y] + (event.value * configs[f'{sens}_y'])
                    case evdev.ecodes.REL_WHEEL:
                        if throttle:
                            controller_values[tx] = max(0, min(controller_values[tx] + event.value, configs['throttle_segments']))
                            # ensure between 0.0 and 1.0
                            gamepad.left_trigger_float(value_float=(controller_values[tx] / configs['throttle_segments']))

            case evdev.ecodes.EV_ABS:
                match event.code:
                    case evdev.ecodes.ABS_X:
                        controller_values[x] = (event.value / configs[f'{sens}_x']) / (32768 / 4)
                    case evdev.ecodes.ABS_Z:
                        controller_values[y] = (event.value / configs[f'{sens}_y']) / (32768 / 4)

            case evdev.ecodes.EV_KEY:
                match event.code:
                    case evdev.ecodes.BTN_LEFT:
                        if event.value == 1:
                            gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                        else:
                            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    case evdev.ecodes.BTN_RIGHT:
                        if event.value == 1:
                            gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                        else:
                            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)

        # ensure between -1.0 and 1.0a
        controller_values[x] = max(-1.0, min(controller_values[x], 1.0))
        controller_values[y] = max(-1.0, min(controller_values[y], 1.0))
        if device_name == 'primary':
            gamepad.left_joystick_float(x_value_float=controller_values[x], y_value_float=controller_values[y])
        else:
            gamepad.right_joystick_float(x_value_float=controller_values[x], y_value_float=controller_values[y])
        
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
    if(not configs['display_gui']):
        return
    root = tk.Tk()
    app = ColorDisplayApp(root)
    root.mainloop()

if __name__ == "__main__":
    logging.warning("mouse_yoke.py is now running\n\n")

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
