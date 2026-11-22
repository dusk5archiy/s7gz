import signal
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from subprocess import Popen, TimeoutExpired

from lib.type_emitters.protocol import EmitterProtocol
from src_common.subprocess_launchers.models import SubprocessCommand
from src_common.subprocess_launchers.protocol import SubprocessLauncherProtocol


@dataclass(kw_only=True, frozen=True)
class Context:
    proc: Popen[bytes]

    @property
    def current_thread_is_main_thread(self):
        return threading.current_thread() is threading.main_thread()

    @property
    def wait_for_program(self):
        return self.proc.wait

    @property
    def program_is_running(self):
        return self.proc.poll() is None

    def forward_signal_to_program(self, *, signum: signal._SIGNUM):
        self.proc.send_signal(signum)

    def shutdown_program(self, *, terminate_timeout_s: float):
        if not self.program_is_running:
            return

        self.proc.terminate()
        try:
            self.wait_for_program(timeout=terminate_timeout_s)
        except TimeoutExpired:
            self.proc.kill()
            self.wait_for_program()


class HandlerReplacementManager:
    def __init__(self) -> None:
        self.original_handlers: dict[signal._SIGNUM, signal._HANDLER] = {}

    def _replace(
        self, *, new_handler: signal._HANDLER, for_signum: int
    ) -> signal._HANDLER:
        previous_handler = signal.signal(for_signum, new_handler)
        return previous_handler

    def register(self, *, new_handler: signal._HANDLER, for_signum: int) -> None:
        previous_handler = self._replace(new_handler=new_handler, for_signum=for_signum)
        if for_signum not in self.original_handlers:
            self.original_handlers[for_signum] = previous_handler

    def revert(self):
        for sig, originaL_handler in self.original_handlers.items():
            self._replace(new_handler=originaL_handler, for_signum=sig)


@dataclass(kw_only=True, frozen=True)
class StandardSubprocessLauncher(SubprocessLauncherProtocol):
    terminate_timeout_s: float = 5.0
    supported_signums: Sequence[signal._SIGNUM] = (signal.SIGINT, signal.SIGTERM)
    command_emitter: EmitterProtocol[SubprocessCommand]

    def __call__(self):
        command = self.command_emitter()
        context = Context(proc=Popen(args=command.cmd, env=command.env))
        manager = HandlerReplacementManager()

        if context.current_thread_is_main_thread:

            def signal_forwarder(signum: signal._SIGNUM, _):
                if context.program_is_running:
                    context.forward_signal_to_program(signum=signum)

            for sig in self.supported_signums:
                manager.register(new_handler=signal_forwarder, for_signum=sig)

        try:
            return context.wait_for_program()
        finally:
            # Order matters, avoid forwarding signals to the dying program
            manager.revert()
            context.shutdown_program(terminate_timeout_s=self.terminate_timeout_s)
