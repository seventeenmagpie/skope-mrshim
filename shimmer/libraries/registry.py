import configparser

clients_on_registry = {}
registry = configparser.ConfigParser()
registry.read("network_description.ini")
# print(registry.sections())

# for name in registry.sections():
#    print(f"{name} @ {registry[name]['address']}:{registry[name]['port']},")


def get_socket(name: str):
    return clients_on_registry[name].socket


def get_address(name: str):
    return (registry[name]["address"], int(registry[name]["port"]))


def get_name_from_address(query_address):
    for name, _ in registry.items():
        if get_address(name) == query_address:
            return name


# placed here so can be accessed by rest of program.
# TODO: put inside a proper __init__ or whatever so this is a real module.
registry, clients_on_registry
