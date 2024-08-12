# a minimal client must implement at least .init() and .close()

# note, this won't import from inside /docs/, move to the root of shimmer for this import to work.
from libraries.generic_client import Client

class MinimalClient(Client):
    def __init__(self, name):
        super().__init__(name)
        # specific initiation goes here

    def close(self):
        # specific closing steps go here
        super()._close()

client = MinimalClient("mini")

try:
    while self.running:
        client.main_loop()
except KeyboardInterrupt:
    print("Exiting program!")
finally:
    client.close()
    sys.exit(0)
