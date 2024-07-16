class ClientDisconnect(Exception):
    """Raised when a client disconnects.

    Called after the socket is closed and deregistered, so the main server process can stop keeping track of it.
    """

    pass


class CommandRecieved(Exception):
    """Raised when a server command needs executing.

    Takes execution back to the main loop when a command is executed that affects server state.
    """

    pass
