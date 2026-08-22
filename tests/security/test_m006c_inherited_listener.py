from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.security


def test_valid_inherited_listener_is_adopted_and_path_remains(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    script = r"""
import os, socket, sys
from pathlib import Path
from jarvis.core.ownership import RuntimeOwnership
runtime = Path(sys.argv[1])
path = runtime / 'core.sock'
listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
listener.bind(str(path))
os.chmod(path, 0o600)
listener.listen(8)
if listener.fileno() != 3:
    os.dup2(listener.fileno(), 3)
os.environ['LISTEN_PID'] = str(os.getpid())
os.environ['LISTEN_FDS'] = '1'
os.environ['LISTEN_FDNAMES'] = 'jarvis-core'
ownership = RuntimeOwnership.acquire(runtime, recover_socket=False)
adopted = ownership.adopt_inherited_socket()
assert adopted.fileno() != 3
assert not os.get_inheritable(adopted.fileno())
adopted.close()
ownership.close()
assert path.exists()
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-c", script, str(runtime)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (runtime / "core.sock").exists()


def test_inherited_listener_rejects_missing_activation_contract(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    script = r"""
import sys
from pathlib import Path
from jarvis.core.ownership import RuntimeOwnership
from jarvis.ipc.errors import IpcError
ownership = RuntimeOwnership.acquire(Path(sys.argv[1]), recover_socket=False)
try:
    ownership.adopt_inherited_socket(env={})
except IpcError as error:
    assert error.code == 'ipc.activation_invalid'
else:
    raise AssertionError('activation accepted')
finally:
    ownership.close()
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-c", script, str(runtime)],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "case",
    [
        "wrong-count",
        "wrong-name",
        "extra-fd",
        "regular",
        "inet",
        "not-listening",
        "wrong-address",
        "abstract",
        "wrong-mode",
        "wrong-uid",
    ],
)
def test_inherited_listener_rejection_matrix(tmp_path: Path, case: str) -> None:
    runtime = tmp_path / case
    runtime.mkdir(mode=0o700)
    script = r"""
import os, socket, sys
from pathlib import Path
from jarvis.core.ownership import RuntimeOwnership
from jarvis.ipc.errors import IpcError
runtime, case = Path(sys.argv[1]), sys.argv[2]
expected = runtime / 'core.sock'
if case == 'regular':
    descriptor = os.open(runtime / 'regular', os.O_RDWR | os.O_CREAT, 0o600)
elif case == 'inet':
    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    holder.bind(('127.0.0.1', 0)); holder.listen(1); descriptor = holder.fileno()
else:
    holder = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    address = ('\0jarvis-test' if case == 'abstract' else
               str(runtime / 'other.sock') if case == 'wrong-address' else str(expected))
    holder.bind(address)
    if case != 'not-listening': holder.listen(1)
    if case == 'wrong-mode': os.chmod(expected, 0o666)
    elif case not in {'abstract'}: os.chmod(Path(address), 0o600)
    descriptor = holder.fileno()
if descriptor != 3: os.dup2(descriptor, 3)
environment = {'LISTEN_PID': str(os.getpid()), 'LISTEN_FDS': '1',
               'LISTEN_FDNAMES': 'jarvis-core'}
if case == 'wrong-count': environment['LISTEN_FDS'] = '0'
if case == 'extra-fd': environment['LISTEN_FDS'] = '2'
if case == 'wrong-name': environment['LISTEN_FDNAMES'] = 'other'
ownership = RuntimeOwnership.acquire(runtime, recover_socket=False)
if case == 'wrong-uid': os.getuid = lambda: 2**31 - 1
try:
    ownership.adopt_inherited_socket(env=environment)
except IpcError as error:
    assert error.code == 'ipc.activation_invalid'
else:
    raise AssertionError('invalid inherited listener accepted')
finally:
    if case != 'wrong-uid': ownership.close()
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(Path.cwd() / "src")
    result = subprocess.run(
        [sys.executable, "-c", script, str(runtime), case],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
