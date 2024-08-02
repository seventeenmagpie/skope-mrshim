class ClientDisconnect(Exception):
    """Raised when a client disconnects.

    Called after the socket is closed and deregistered, so the main server process can stop keeping track of it.
    """

    pass
