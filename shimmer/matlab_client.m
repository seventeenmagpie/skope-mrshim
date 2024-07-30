% writes packets of current to the server.
%% preparation
clear all;
clc;

% TODO: make paths hardware agnostic (windows vs linux)
addpath('./libraries/');

% adds this directory to the python path so i can use my python code again
% From: https://uk.mathworks.com/help/matlab/matlab_external/call-user-defined-custom-module.html

% ON MAGS' LAPTOP
shimmer_directory = '/home/mags/Documents/studies/uni/summer_placement/skope-mrshim/shimmer';

% ON SKOPE COMPUTER
%shimmer_directory = 0;

% ON MRSHIMS COMPUTER
%shimmer_directory = 0;

if count(py.sys.path, shimmer_directory) == 0
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