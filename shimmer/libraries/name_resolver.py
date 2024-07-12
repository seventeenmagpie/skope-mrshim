import tomli

clients_on_registry = {}

try:
    with open("network_description.toml", "rb") as f:
        registry = tomli.load(f)
except tomli.TOMLDecodeError:
    print("Invalid config file.")
    sys.exit(1)

def get_socket(name):
    print(clients_on_registry)
    pass

registry, clients_on_registry
