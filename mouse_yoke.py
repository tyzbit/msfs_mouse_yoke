from pyautogui import size, moveTo
import pyautogui
import evdev
import natsort

from pynput import keyboard
from reprint import output
from threading import Thread
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

joystickFloatX = 0.0
joystickFloatY = 0.0
throttleFloat = 0.0
throttleX = 0
active = False

if len(sys.argv) > 1:
    device_number = sys.argv[1]
else:
    devices = [evdev.InputDevice(fn) for fn in evdev.list_devices()]
    for device in natsort.natsorted(devices, key=lambda d: d.path):
        print(device.path, device.name)
    device_number = input(f'Enter the number of the event device to read from: ')

device = evdev.InputDevice('/dev/input/event'+device_number)
print(f'Using {device.name} at {device.path}')

def onKeyRelease(key):
    global active
    global joystickFloatX, joystickFloatY

    if key == keyboard.KeyCode.from_char(configs["master_key"]):
        active = not active
        gamepad.reset()

    if key == keyboard.KeyCode.from_char(configs["center_xy_axes_key"]):
        joystickFloatX = 0
        joystickFloatY = 0

def userInterface():
    with output(initial_len=8, interval=0) as output_lines:
        while True:

            output_lines[0] = f"+{' Status: ' + ('ACTIVE' if active else 'INACTIVE') + ' ':—^40}+"
            output_lines[1] = f"|{'':^40}|"
            output_lines[2] = f"|{'Axis':^20}{'Position':^20}|"
            output_lines[3] = f"+{'':—^40}+"
            output_lines[4] = f"|{'X':^20}{'{:.2f}'.format((joystickFloatX + 1) * 50) + '%':^20}|"
            output_lines[5] = f"|{'Y':^20}{'{:.2f}'.format((joystickFloatY + 1) * 50) + '%':^20}|"
            output_lines[6] = f"|{'THROTTLE':^20}{'{:.2f}'.format((throttleFloat + 1) * 50) + '%':^20}|"
            output_lines[7] = f"+{'':—^40}+"

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

def mouseLoop():
    global joystickFloatX, joystickFloatY, throttleX, throttleFloat
    for event in device.read_loop():
        match event.type:
            case evdev.ecodes.EV_REL:
                match event.code:
                    case evdev.ecodes.REL_X:
                        joystickFloatX = joystickFloatX + (event.value * configs['mouse_sensitivity_x'])
                    case evdev.ecodes.REL_Y:
                        joystickFloatY = joystickFloatY + (event.value * configs['mouse_sensitivity_y'])
                    case evdev.ecodes.REL_WHEEL:
                        # ensure between -1.0 and 1.0
                        throttleX = max(-configs['throttle_segments']/2, min(throttleX + event.value, configs['throttle_segments']/2))
                        throttleFloat = throttleX / (configs['throttle_segments']/2)
                        gamepad.right_joystick_float(x_value_float=throttleFloat, y_value_float=0)
                # ensure between -1.0 and 1.0
                joystickFloatY = max(-1, min(joystickFloatY, 1))
                joystickFloatX = max(-1, min(joystickFloatX, 1))
                gamepad.left_joystick_float(x_value_float=joystickFloatX, y_value_float=joystickFloatY)
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
        if active:
            gamepad.update()


def runTK():
    if(not configs['display_gui']):
        return
    root = tk.Tk()
    app = ColorDisplayApp(root)
    root.mainloop()

if __name__ == "__main__":
    logging.warning("mouse_yoke.py is now running\n\n")

    try:
        pyautogui.FAILSAFE = False
        ui = Thread(target=userInterface)
        ms = Thread(target=mouseLoop)
        kb = keyboard.Listener(on_release=onKeyRelease)
        tl = Thread(target=runTK)
        
        ms.start()
        kb.start()
        ui.start()
        tl.start()
        # Explicitly wait for SIGINT, once caught exit
        signal.signal(signal.SIGINT, sys.exit(0))
        signal.pause

    except Exception as e:
        logging.critical("Exception occurred", exc_info=True)
