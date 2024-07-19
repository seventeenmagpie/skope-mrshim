% writes packets of current to the server.

% packet content should be:
% - two bytes of protoheader containing the length of the encoded jsonheader,
% - a jsonheader containing:
%   - "content-type": relay
%   - "to": "sinope"
%   - "from": "matlab"
%   - "content-encoding": utf-8
%   - "byteorder": "little"
%   - "content-length": length of the content.
% - the content which should be:
% "!shims <shim currents here>"

% example of the bytes to send: b'\x00\x87{"byteorder": "little", "content-type": "relay", "content-encoding": "utf-8", "content-length": 13, "to": "sinope", "from": "console1"}"!shim 0.025"'
%% preparation
clear;
clc;

addpath('./libraries/');


%% set connection properties
% read from network_description.toml
server_address = "127.0.0.1";
server_port = 25000;

%% initiate the tcp client
tcp = tcpclient(server_address, server_port);

%% construct a table for the request
request = table;
jsonheader = table;

request.content_string = "!shim 0.5";
request.content = unicode2native(request.content_string, "UTF-8");

jsonheader.content_type = "relay";
jsonheader.to = "server";
jsonheader.from = "matlab";
jsonheader.content_encoding = "utf-8";
jsonheader.byteorder = "little";

% this is painful. how can i python it?
% matlab will let me use python functions because its just c under the
% hood,
% i can also run python scripts from matlab
% i could calculate the shim currents and pass them as an argument
% down the python function.
% which would then have to send them... but i can't run a whole script each
% time
% ooooo
% if the interpreter session is preserved, i could do the socket prep
% stuff at the top and then just call a 'send' function each time?

% matlab documentation seems to suggest i can use py.__ and just use python
% everything from within matlab, which seems unilkely will work for me
% but could try?
