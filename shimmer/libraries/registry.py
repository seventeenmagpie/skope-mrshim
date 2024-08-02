import configparser

clients_on_registry = {}
registry = configparser.ConfigParser()
registry.read("network_description.ini")

def get_socket(name: str):
    return clients_on_registry[name].socket


def get_address(name: str):
    return (registry[name]["address"], int(registry[name]["port"]))


def get_name_from_address(query_address):
    for name in registry.sections():
        if get_address(name) == query_address:
            return name

# placed here so can be used by rest of program, as i understand it.
registry, clients_on_registry
