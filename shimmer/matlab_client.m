% writes packets of current to the server.
%% preparation
clear all;
clc;

% TODO: make paths hardware agnostic (windows vs linux)
addpath('./libraries/');

% adds this directory to the path so i can use my python code again
% From: https://uk.mathworks.com/help/matlab/matlab_external/call-user-defined-custom-module.html
if count(py.sys.path, pwd) == 0
    insert(py.sys.path, int32(0), pwd);
end

%% reload python parts

interface = py.importlib.import_module('libraries.matlab_interface');
py.importlib.reload(interface);
%% python setup
% create the client
client = interface.MatlabClient('matlab');
client.start_connection()

%% send a shim
disp("trying shimming")
client.send_currents(0.1234)
