"""gpiozero to evdev bridge for physical navigation buttons.

Wire each button between its BCM pin and ground. The bridge creates a virtual
keyboard so the kiosk UI receives the same keys as a USB keyboard.

Install the runtime packages and udev rule described in README.md, then enable
``transit-gpio-nav.service``.
"""

from __future__ import annotations

import signal
import threading
from types import FrameType

try:
    from evdev import UInput
    from evdev import ecodes as e
    from gpiozero import Button
except ImportError as exc:  # pragma: no cover - deployment dependency
    raise SystemExit(
        "Install gpiozero and python3-evdev (for example: "
        "sudo apt install python3-gpiozero python3-evdev)"
    ) from exc

# BCM pin -> Linux input key. These mirror the keys handled by navigation.ts.
BUTTON_KEYS: dict[int, int] = {
    17: e.KEY_RIGHT,
    27: e.KEY_LEFT,
    22: e.KEY_ENTER,
    23: e.KEY_PAGEDOWN,
    24: e.KEY_PAGEUP,
}

DEBOUNCE_SECONDS = 0.05


def main() -> int:
    """Create the virtual keyboard and run until SIGINT or SIGTERM."""
    stop_event = threading.Event()

    def handle_signal(signum: int, frame: FrameType | None) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        virtual_keyboard = UInput(
            {e.EV_KEY: list(BUTTON_KEYS.values())},
            name="transit-kiosk-nav",
            vendor=0x1D6B,
            product=0x0104,
            version=1,
        )
    except OSError as exc:  # pragma: no cover - hardware dependency
        raise SystemExit(
            "Cannot open /dev/uinput. Load the uinput module, add the service "
            "user to the input group, and install the udev rule from README.md."
        ) from exc

    write_lock = threading.Lock()

    def emit(key: int, value: int) -> None:
        with write_lock:
            virtual_keyboard.write(e.EV_KEY, key, value)
            virtual_keyboard.syn()

    buttons = [Button(pin, bounce_time=DEBOUNCE_SECONDS) for pin in BUTTON_KEYS]
    for button, key in zip(buttons, BUTTON_KEYS.values(), strict=True):
        button.when_pressed = lambda key=key: emit(key, 1)
        button.when_released = lambda key=key: emit(key, 0)

    print(f"GPIO navigation ready on BCM pins {sorted(BUTTON_KEYS)}", flush=True)

    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        for button in buttons:
            button.close()
        virtual_keyboard.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
