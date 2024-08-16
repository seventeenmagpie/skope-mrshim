import ctypes

# import the dll and tell python which Python types go to which c_types.
mrshim = ctypes.cdll.LoadLibrary(r".\libshim.dll")  
# path *from where python is ran* to libshim.dll
mrshim.ShimStart.argtypes = ctypes.c_char_p, ctypes.c_int
c_int32_p = ctypes.POINTER(ctypes.c_int32)
mrshim.ShimSetCurr.argtypes = c_int32_p, ctypes.c_int, ctypes.c_bool
mrshim.ShimSetCurr.restype = None
mrshim.ShimGetAttr.argtypes = (ctypes.c_int,)
mrshim.ShimGetAttr.restype = ctypes.POINTER(ctypes.c_int16)


def start_connection():
    jupiter_ifname = r"\Device\NPF_{58A4C8CA-56D2-4F34-8D5E-74FD1F2E60CA}"
    jupiter_ifname_unicode = jupiter_ifname.encode("utf-8")
    rc = mrshim.ShimStart(jupiter_ifname_unicode, 1)

    if rc == 0:
        print("Connected to Jupiter device!")
        channel_number = mrshim.shim_num_channels()
    else:
        print(f"Issue connecting to Jupiter devices. Error code: {rc}")
        print(f"Consult Internal Software Tools Documentation.pdf for interpretation.")
        print("Shimming will not work.")
        channel_number = 0

    return channel_number


def display_status():
    """Print some status information about Jupiter/shimming.

    It takes some time from shim being applied for the correct currents to come through.
    """

    channel_number = mrshim.shim_num_channels()

    # print temperatures
    temp = mrshim.ShimGetAttr(6)
    # NOTE: conversion is from arbitrary units, provided by Paul at MRShim
    temperatures = [((temp[i] * 0.8 - 400) / 19.5) for i in range(channel_number)]
    temperatures_string = " ".join(["{:.1f}".format(temp) for temp in temperatures])
    print(f"Amplifier circuit temperatures are ['C]: {temperatures_string}")

    # print currents
    current = mrshim.ShimGetAttr(0)
    currents = [current[i] for i in range(channel_number)]
    currents_string = " ".join([str(current) for current in currents])
    print(f"Currents being applied are [mA]: {currents_string}")

    first_diverged_channel = mrshim.ShimChannelDiverged()
    if first_diverged_channel:
        print(
            f"Channel {first_diverged_channel} did not converge (error in current > 50mA), and other channels may not have either."
        )


def set_shim_currents(currents):
    """Apply shim currents.

    Enable should be called first, otherwise this will do nothing. Currents should be a list of 24 milliamp currents.
    """
    channel_number = mrshim.shim_num_channels()

    max_current = 2000  # mA
    for idx, current in enumerate(currents):
        if abs(current) > max_current:
            print(
                f"Current exceeds safe maximum +/-{max_current}mA. Setting this current to 0mA."
            )
            currents[idx] = 0

    ctype_currents = (ctypes.c_int32 * channel_number)(*currents)
    current_pointer = ctypes.cast(ctype_currents, ctypes.POINTER(ctypes.c_int32))
    mrshim.ShimSetCurr(current_pointer, channel_number, False)
    print(f"Shims set: {currents}")


def enable_shims():
    """Enable shimming. Set currents to zero."""
    mrshim.ShimEnable()
    mrshim.ShimResetCurr()


def disable_shims():
    """Disable shimming. Set currents to zero."""
    mrshim.ShimResetCurr()
    mrshim.ShimDisable()


def soft_reset():
    """Close and re-open the connection to Jupiter without pausing shimming."""
    mrshim.shim_soft_close()
    start_connection()


def stop():
    mrshim.ShimStop()
