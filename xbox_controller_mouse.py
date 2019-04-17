#!/usr/bin/env python3
import common, config, version_update
import attr, collections, pyautogui, sys, time, typing
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
class MouseMovement:
    position_speed: Vector = attr.Factory(Vector)
    scroll_speed: Vector = attr.Factory(Vector)
    @classmethod
    def combine(cls, statuses):
        '''
        Combines multiple mouse movements together into one. Vectors are
        summed.
        '''
        result = cls()
        for status in statuses:
            result.position_speed += status.position_speed
            result.scroll_speed += status.scroll_speed
        return result
class Presses:
    '''
    Keeps track of which buttons or keys should be held down. If a button or
    key is queued to be pressed down multiple times, it must be queued to be
    released the same number of times for this class to consider it released.
    '''
    KeyOrButtonId: typing.ClassVar[type] = str
    Sequence: typing.ClassVar[type] = typing.Sequence[KeyOrButtonId]
    def __init__(self):
        self._queue_down = collections.deque()
        self._queue_up = collections.deque()
        self._num_presses = collections.defaultdict(lambda: 0)
    def queue_press_down(self, ids: Sequence) -> None:
        '''
        Queues a sequence of buttons or keys to be pressed down.
        '''
        self._queue_down.extend(ids)
    def queue_release(self, ids: Sequence) -> None:
        '''
        Queues a sequence of buttons or keys to be released in reverse order.
        '''
        self._queue_up.extend(reversed(ids))
    def process_queue(self) -> typing.Tuple[
            typing.Sequence[KeyOrButtonId],
            typing.Sequence[KeyOrButtonId]
        ]:
        '''
        Processes and clears the internal queues. Returns which buttons or keys
        should have been pressed or released since the last call.
        '''
        press_down_now: typing.Sequence[KeyOrButtonId] = []
        release_now: typing.Sequence[KeyOrButtonId] = []
        while self._queue_down:
            id: KeyOrButtonId = self._queue_down.popleft()
            if self._num_presses[id] <= 0:
                # The button or key is not pressed.
                self._num_presses[id] = 1
                # It should be pressed now.
                press_down_now.append(id)
            else:
                # The button or key is already pressed.
                self._num_presses[id] += 1
        while self._queue_up:
            id: KeyOrButtonId = self._queue_up.popleft()
            if self._num_presses[id] <= 1:
                # The button or key is pressed only once.
                self._num_presses[id] = 0
                # It should be released now.
                release_now.append(id)
            else:
                # The button or key is pressed more than once.
                # Don't release it right now.
                self._num_presses[id] -= 1
        return press_down_now, release_now

_JOYSTICK_BUTTON_TO_MOUSE_BUTTONS: typing.Dict[int, Presses.Sequence] = {
    9:  ("left",),        # left bumper
    13: ("left",),        # A
    10: ("right",),       # right bumper
    16: ("right",),       # Y
    15: ("middle",),      # X
}
_JOYSTICK_BUTTON_TO_KEYBOARD_KEYS: typing.Dict[int, Presses.Sequence] = {
    1:  ("up",),          # D-pad up
    2:  ("down",),        # D-pad down
    3:  ("left",),        # D-pad left
    4:  ("right",),       # D-pad right
    5:  ("win",),         # menu
    6:  ("win", "tab"),   # view
    14: ("browserback",), # B
}
_LEFT_TRIGGER_KEYS: Presses.Sequence = ("home",)
_RIGHT_TRIGGER_KEYS: Presses.Sequence = ("end",)

def axis_to_position_speed(axis_value):
    return (axis_value * MOUSE_POSITION_SPEED) ** 3
def axis_to_scroll_speed(axis_value):
    return (axis_value * MOUSE_SCROLL_SPEED) ** 3
def init_trigger(
    presses: Presses,
    keys: Presses.Sequence
) -> typing.Callable[[float], None]:
    '''
    Returns a callback function that presses or releases the given key sequence
    based on the trigger input. When the trigger is pulled, the keys are queued
    to be pressed down. When the trigger is released, the keys are queued to be
    released.
    '''
    was_pulled = False
    def handler(current_deflection: float) -> None:
        nonlocal was_pulled
        is_pulled = current_deflection > 0.5
        if was_pulled:
            if not is_pulled:
                # The trigger was released.
                # Release the keyboard keys in reverse order.
                presses.queue_release(keys)
        else:
            if is_pulled:
                # The trigger was pulled.
                # Press the keyboard keys.
                presses.queue_press_down(keys)
        was_pulled = is_pulled
    return handler
def init_joystick(
    joystick: xinput.XInputJoystick,
    mouse_presses: Presses,
    keyboard_presses: Presses
) -> MouseMovement:
    mouse_movement = MouseMovement()
    @joystick.event
    def on_button(button, pressed):
        # Check for a mapping from the joystick button to a mouse button or
        # to a sequence of multiple mouse buttons.
        mouse_buttons = _JOYSTICK_BUTTON_TO_MOUSE_BUTTONS.get(button)
        if mouse_buttons is not None:
            if pressed:
                # Push the buttons down.
                mouse_presses.queue_press_down(mouse_buttons)
            else:
                # Release the buttons in reverse order.
                mouse_presses.queue_release(mouse_buttons)
            return
        # Check for a mapping from the joystick button to a sequence of
        # keyboard keys.
        keys = _JOYSTICK_BUTTON_TO_KEYBOARD_KEYS.get(button)
        if keys is not None:
            if pressed:
                # Push the keys down.
                keyboard_presses.queue_press_down(keys)
            else:
                # Release the keys in reverse order.
                keyboard_presses.queue_release(keys)
            return
        # This button is not mapped to anything.
        print("Unmapped button", button, "down" if pressed else "up")
    left_trigger_handler = init_trigger(keyboard_presses, _LEFT_TRIGGER_KEYS)
    right_trigger_handler = init_trigger(keyboard_presses, _RIGHT_TRIGGER_KEYS)
    @joystick.event
    def on_axis(axis, value):
        if axis == "l_thumb_x":
            mouse_movement.position_speed.x = axis_to_position_speed(value)
        elif axis == "l_thumb_y":
            mouse_movement.position_speed.y = -axis_to_position_speed(value)
        elif axis == "r_thumb_x":
            mouse_movement.scroll_speed.x = -axis_to_scroll_speed(value)
        elif axis == "r_thumb_y":
            mouse_movement.scroll_speed.y = axis_to_scroll_speed(value)
        elif axis == "left_trigger":
            left_trigger_handler(value)
        elif axis == "right_trigger":
            right_trigger_handler(value)
        else:
            print("Unmapped axis", axis, value)
    return mouse_movement
def init() -> typing.Tuple[
    typing.Iterable[xinput.XInputJoystick],
    typing.Iterable[MouseMovement],
    Presses,
    Presses
]:
    pyautogui.PAUSE = 0.0
    pyautogui.FAILSAFE = False
    mouse_presses = Presses()
    keyboard_presses = Presses()
    joysticks = xinput.XInputJoystick.enumerate_devices()
    mouse_movements = [
        init_joystick(joystick, mouse_presses, keyboard_presses)
        for joystick in joysticks
    ]
    return joysticks, mouse_movements, mouse_presses, keyboard_presses
def loop(
    joysticks: typing.Iterable[xinput.XInputJoystick],
    mouse_movements: typing.Iterable[MouseMovement],
    mouse_presses: Presses,
    keyboard_presses: Presses
) -> None:
    while True:
        # Dispatch all events.
        for joystick in joysticks:
            joystick.dispatch_events()
        # Mix all controllers together.
        combined = MouseMovement.combine(mouse_movements)
        # Do the mouse movement.
        pyautogui.move(*attr.astuple(combined.position_speed))
        # Do the mouse scrolling.
        pyautogui.hscroll(int(combined.scroll_speed.x))
        pyautogui.vscroll(int(combined.scroll_speed.y))
        # Do the mouse button presses.
        down, up = mouse_presses.process_queue()
        for button in down:
            pyautogui.mouseDown(button=button)
        for button in up:
            pyautogui.mouseUp(button=button)
        # Do the keyboard key presses.
        down, up = keyboard_presses.process_queue()
        for key in down:
            pyautogui.keyDown(key)
        for key in up:
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
    joysticks, *loop_args = init()
    print("Found {} controller(s)".format(len(joysticks)))
    print(HELP)
    loop(joysticks, *loop_args)

if __name__ == "__main__":
    main()
