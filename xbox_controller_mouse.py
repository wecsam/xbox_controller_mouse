#!/usr/bin/env python3
import common, config, version_update
import attr, pyautogui, sys, time, typing
sys.path.insert(1, config.XINPUT_DIR)
import xinput

MOUSE_POSITION_SPEED = 8.0
MOUSE_SCROLL_SPEED = 8.0
HELP = '''
Controls:
    Left joystick:     move cursor
    Right joystick:    scroll (vertical only on Windows)
    A or left bumper:  left click
    Y or right bumper: right click
    X:                 middle click
    B:                 back button
    Menu:              Windows key
    View:              Windows+Tab
    D-pad:             arrow keys
    Left trigger:      Home
    Right trigger:     End
'''

@attr.s(auto_attribs=True)
class Vector:
    x: float = 0.0
    y: float = 0.0
    def __add__(self, other):
        cls = type(self)
        if isinstance(other, cls):
            # Simply add the vectors together.
            return cls(
                *[
                    sum(addends) for addends in zip(
                        attr.astuple(self),
                        attr.astuple(other)
                    )
                ]
            )
        raise TypeError("other must be a Vector")
@attr.s(auto_attribs=True)
class MouseButtons:
    '''
    Each property is True if the button should be pressed, False if the button
    should be released, or None if the button doesn't need to be pressed or
    released.
    '''
    left: typing.Optional[bool] = None
    middle: typing.Optional[bool] = None
    right: typing.Optional[bool] = None
    def __or__(self, other):
        cls = type(self)
        if isinstance(other, cls):
            # In the result, a button is pressed if it was pressed in either
            # MouseButtons object.
            return cls(
                *[
                    (
                        any(pressed)
                        if any(button is not None for button in pressed)
                        else None
                    )
                    for pressed in zip(
                        attr.astuple(self),
                        attr.astuple(other)
                    )
                ]
            )
        raise TypeError("other must be a MouseButtons")
@attr.s(auto_attribs=True, frozen=True)
class KeyPress:
    hold_down: typing.Iterable[str] = attr.Factory(list)
    press_and_release: typing.Iterable[str] = attr.Factory(list)
@attr.s(auto_attribs=True)
class MouseStatus:
    position_speed: Vector = attr.Factory(Vector)
    scroll_speed: Vector = attr.Factory(Vector)
    buttons: MouseButtons = attr.Factory(MouseButtons)
    keyboard_keys: typing.Iterable[KeyPress] = attr.Factory(list)
    @classmethod
    def combine(cls, statuses):
        '''
        Combines multiple joystick statuses together into one. Axes positions
        are summed. Buttons are logically disjuncted.
        '''
        result = cls()
        for status in statuses:
            result.position_speed += status.position_speed
            result.scroll_speed += status.scroll_speed
            result.buttons |= status.buttons
            result.keyboard_keys.extend(status.keyboard_keys)
        return result
    def loop_iter(self):
        '''
        Call this function at the beginning of each iteration of the main loop,
        before any events are dispatched.
        '''
        self.buttons = MouseButtons()
        self.keyboard_keys.clear()

_joysticks = []
_joystick_statuses = []
_JOYSTICK_BUTTON_TO_KEYBOARD = {
    1:  KeyPress((), ("up",)),
    2:  KeyPress((), ("down",)),
    3:  KeyPress((), ("left",)),
    4:  KeyPress((), ("right",)),
    5:  KeyPress((), ("win",)), # menu
    6:  KeyPress(("win",), ("tab",)), # view
    14: KeyPress((), ("browserback",)) # B
}
_KEYPRESS_HOME = KeyPress((), ("home",))
_KEYPRESS_END = KeyPress((), ("end",))

def axis_to_position_speed(axis_value):
    return (axis_value * MOUSE_POSITION_SPEED) ** 3
def axis_to_scroll_speed(axis_value):
    return (axis_value * MOUSE_SCROLL_SPEED) ** 3
def init_joystick(joystick):
    status = MouseStatus()
    _joysticks.append(joystick)
    _joystick_statuses.append(status)
    @joystick.event
    def on_button(button, pressed):
        pressed = bool(pressed)
        if button in (9, 13): # left bumper or A
            status.buttons.left = pressed
        elif button in (10, 16): # right bumper or Y
            status.buttons.right = pressed
        elif button == 15: # X
            status.buttons.middle = pressed
        else:
            press = _JOYSTICK_BUTTON_TO_KEYBOARD.get(button)
            if press:
                if not pressed: # trigger on release
                    status.keyboard_keys.append(press)
            else:
                print(
                    "Unsupported button",
                    button,
                    "down" if pressed else "up"
                )
    left_trigger_last = False
    right_trigger_last = False
    @joystick.event
    def on_axis(axis, value):
        nonlocal left_trigger_last, right_trigger_last
        if axis == "l_thumb_x":
            status.position_speed.x = axis_to_position_speed(value)
        elif axis == "l_thumb_y":
            status.position_speed.y = -axis_to_position_speed(value)
        elif axis == "r_thumb_x":
            status.scroll_speed.x = -axis_to_scroll_speed(value)
        elif axis == "r_thumb_y":
            status.scroll_speed.y = axis_to_scroll_speed(value)
        elif axis == "left_trigger":
            left_trigger_new = value > 0.5
            if left_trigger_last and not left_trigger_new: # trigger released
                status.keyboard_keys.append(_KEYPRESS_HOME)
            left_trigger_last = left_trigger_new
        elif axis == "right_trigger":
            right_trigger_new = value > 0.5
            if right_trigger_last and not right_trigger_new: # trigger released
                status.keyboard_keys.append(_KEYPRESS_END)
            right_trigger_last = right_trigger_new
        else:
            print("Unsupported axis", axis, value)
def init():
    pyautogui.PAUSE = 0.0
    pyautogui.FAILSAFE = False
    for joystick in xinput.XInputJoystick.enumerate_devices():
        init_joystick(joystick)
def loop():
    while True:
        for status in _joystick_statuses:
            status.loop_iter()
        # Dispatch all events.
        for joystick in _joysticks:
            joystick.dispatch_events()
        # Mix all controllers together.
        combined = MouseStatus.combine(_joystick_statuses)
        # Do the mouse movement.
        pyautogui.move(*attr.astuple(combined.position_speed))
        # Do the mouse scrolling.
        pyautogui.hscroll(int(combined.scroll_speed.x))
        pyautogui.vscroll(int(combined.scroll_speed.y))
        # Do the mouse button presses.
        for button, press_down in attr.asdict(combined.buttons).items():
            if press_down is not None:
                if press_down:
                    pyautogui.mouseDown(button=button)
                else:
                    pyautogui.mouseUp(button=button)
        # Do the keyboard key presses.
        for press in combined.keyboard_keys:
            for key in press.hold_down:
                pyautogui.keyDown(key)
            for key in press.press_and_release:
                pyautogui.press(key)
            for key in press.hold_down:
                pyautogui.keyUp(key)
        # Sleep.
        try:
            time.sleep(0.017)
        except KeyboardInterrupt:
            break
def main():
    if getattr(sys, "frozen", False):
        import version
    else:
        version_update.increment_revision()
        version = version_update.version_module()
    print(
        "{} {}.{}.{}.{}".format(
            common.PRODUCT_NAME,
            version.MAJOR,
            version.MINOR,
            version.BUILD,
            version.REVISION
        )
    )
    init()
    print("Found {} controller(s)".format(len(_joysticks)))
    print(HELP)
    loop()

if __name__ == "__main__":
    main()
