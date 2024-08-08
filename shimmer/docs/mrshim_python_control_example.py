import ctypes  # ctypes library necessary for interfacing with .dll

# this is very verbose because if you know what you're doing, you can skim - if you don't (like me) you can't!
# email ppyrt4@nottingham.ac.uk if something doesn't make sense

# this script should be executed from a directory on the mrshim laptop that contains the libshim.dll file (e.g., C:\mrshim\). that file is portable, you can copy it anywhere.

mrshim = ctypes.cdll.LoadLibrary(r".\libshim.dll")  # path to libshim.dll
# now mrshim acts like a python module

# we need to tell python what c types to convert its python types into
# these types came from the docs
mrshim.ShimStart.argtypes = ctypes.c_char_p, ctypes.c_int
c_int32_p = ctypes.POINTER(ctypes.c_int32)
mrshim.ShimSetCurr.argtypes = c_int32_p, ctypes.c_int, ctypes.c_bool

jupiter_ifname = r"\Device\NPF_{58A4C8CA-56D2-4F34-8D5E-74FD1F2E60CA}"
jupiter_ifname_unicode = self.jupiter_ifname.encode('utf-8')

rc = mrshim.ShimStart(self.jupiter_ifname_unicode, 1)

if rc == 0:
    print("Connected to Jupiter device!")
else:
    print(f"Issue connecting to Jupiter devices. Error code: {rc}")
    print(f"Consult Internal Software Tools Documentation.pdf for interpretation.")

# enable shimming
mrshim.ShimEnable()
# the docs say there's a ShimEnableWithRamp function but i checked by looking at what the .dll exposes and there isn't.

# currents is a list of milliamp values.
# we then convert it to a c_type array, and then get a pointer to it.
currents = [50 for _ in range(24)]  # this is just 24 50s.
ctype_currents = (ctypes.c_int32 * 24)(*self.currents)
current_pointer = ctypes.cast(ctype_currents, ctypes.POINTER(ctypes.c_int32))
mrshim.ShimSetCurr(current_pointer, 24, False)

# reset currents
mrshim.ShimResetCurr()

# disable shimming
mrshim.ShimDisable()

# disconnect
mrshim.ShimStop()

# TODO: do the get attr for the current things
