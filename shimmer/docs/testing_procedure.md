# Testing Procedure
The best tests are the one that get done! So no fancy testing framework because I don't know how to do that.

## Connecting and Disconnecting
- [ ] Do all the clients connect?
- [ ] Will each client disconnect by itself via `relay <client> disconnect`?
- [ ] Does the server stop, and all clients disconnect, when you `halt` it?
- [ ] ctrl-c should close the clients
- [ ] all ways of disconnecting, however hard, should lead to the client disconnecting nicely from the server and not cause any crashes (may cause an exception)

## Server Commands
- [ ] list - should list all connected clients and correct addresses
- [ ] status
- [ ] relay works

## Client commands
- [ ] !echo
- [ ] !egg
- [ ] !debug - toggles debugging mode
- [ ] !reader (and no entry)

## MRShim Commands
With and without Jupiter plugged in:
- [ ] connect to Jupiter
- [ ] !shim with no arguments
- [ ] !shim with bad arguments
- [ ] !shim with 24 arguments
- [ ] !shim with less than 24 arguments
- [ ] !start and !stop
- [ ] !reset
- [ ] !status
- [ ] properly disconnect from Jupiter, however it closes.
