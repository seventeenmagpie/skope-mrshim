# a minimal client must implement at least .init() and .close()

# note, this won't import from inside /docs/, move to the root of shimmer for this import to work.
from libraries.generic_client import Client

class MinimalClient(Client):
    def __init__(self, name):
        super().__init__(name)
        # specific initiation goes here
        # self.start_connection() starts the connection using the address and port in the .ini

    def close(self):
        # specific closing steps go here
        super().close()        

client = MinimalClient("mini")
# you will need to add a [mini] heading to the .ini file and give an address and port.

try:
    while self.running:
        client.main_loop()
except KeyboardInterrupt:
    print("Exiting program!")
finally:
    client.close()
    sys.exit(0)
