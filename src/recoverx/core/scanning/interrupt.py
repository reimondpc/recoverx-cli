from __future__ import annotations

import signal
import threading
from typing import Any


class ScanInterrupted(Exception):
    """Raised when a scan is interrupted by the user."""


class InterruptHandler:
    """Handles CTRL+C / KeyboardInterrupt for safe scan interruption.

    Registers a signal handler that sets a flag. Workers and the main
    loop check ``interrupted`` periodically and stop gracefully.

    Usage:
        handler = InterruptHandler()
        handler.install()
        while not handler.interrupted:
            ...
        handler.restore()
    """

    def __init__(self) -> None:
        self.interrupted = False
        self._old_handler: Any = None
        self._lock = threading.Lock()

    def install(self) -> None:
        self._old_handler = signal.signal(signal.SIGINT, self._signal_handler)

    def restore(self) -> None:
        if self._old_handler is not None:
            signal.signal(signal.SIGINT, self._old_handler)
            self._old_handler = None

    def _signal_handler(self, signum: int, frame: object) -> None:
        with self._lock:
            if self.interrupted:
                print("\n[red]Force exit.[/red]")
                self.restore()
                signal.raise_signal(signal.SIGINT)
                return
            self.interrupted = True
            print(
                "\n[yellow]Interrupt received — stopping safely...[/yellow] "
                "(press Ctrl+C again to force exit)"
            )

    def __enter__(self) -> InterruptHandler:
        self.install()
        return self

    def __exit__(self, *args: object) -> None:
        self.restore()
