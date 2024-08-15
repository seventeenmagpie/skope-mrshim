# ensure this file is in the same directory as jupiter_interface.py and libshim.dll or this import will fail!
import jupiter_interface as jupiter

# start the connection
channel_count = jupiter.start_connection()

# display status information
jupiter.display_status()

# start shimming and set currents to zero
jupiter.enable_shims()

# set some shim currents
# must be done after enable_shims() otherwise no currents are set!
jupiter.set_shim_currents([100] * channel_count)

for i in range(2, 10):
    jupiter.set_shim_currents([i*100] * channel_count)
    jupiter.display_status()

# set currents to zero and stop shimming
jupiter.disable_shims()

# reset the connection without stopping shimming, in case the ethernet drops
jupiter.soft_reset()

# disconnect and stop
jupiter.stop()
