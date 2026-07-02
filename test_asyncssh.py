import asyncssh
import inspect
class MyClient(asyncssh.SSHClient):
    pass
print(inspect.getsource(asyncssh.SSHClient.auth_keyboard_interactive))
