# What are the files here?
sinope_server.py : The python server that listens to the socket, recieves UDP datagrams and writes them to the temp file,
sinope_mimic.c : A C program that pretends to be sinope for development reasons, calling the function in shimplugin.dll every 10ms ish and writing the output currents to the console, if they have changed.
shimplugin.c : Source code of the shim plugin that does the real time updating.
