from libraries.registry import get_name_from_address


def selector_printer(selector, events):
    """Print the contents of the selector nicely, and highlight which ones are currently selected."""
    # print("Selector contents (+: selected, -: not selected):")
    for fileobj, key in selector.get_map().items():
        for event_key, event in events:
            if event_key == key:
                print(
                    f" s: {get_name_from_address(event_key.data.addr)} selected in mode {event}"
                )
            else:
                print(
                    f" w: {get_name_from_address(event_key.data.addr)} waiting for mode {event}"
                )