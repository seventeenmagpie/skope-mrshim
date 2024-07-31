% writes packets of current to the server.
%% preparation
clc;

% TODO: make paths hardware agnostic (windows vs linux)
addpath('./libraries/');

% adds this directory to the python path so i can use my python code again
% From: https://uk.mathworks.com/help/matlab/matlab_external/call-user-defined-custom-module.html

% COMMENT OUT THE INCORRECT LINES

% ON MAGS' LAPTOP
shimmer_directory = '/home/mags/Documents/studies/uni/summer_placement/skope-mrshim/shimmer';

% ON SKOPE COMPUTER
%shimmer_directory = 0;

% ON MRSHIMS COMPUTER
%shimmer_directory = N/A;

if count(py.sys.path, shimmer_directory) == 0
    insert(py.sys.path, int32(0), pwd);
end

%% reload python parts
clear all;
interface = py.importlib.import_module('libraries.matlab_interface');
py.importlib.reload(interface);
%% create and connect client
% create the client
client = interface.MatlabClient('matlab');
client.start_connection()

%% send a shim
disp("trying shimming")
currents = [10, 20, 30];  % in milliamps!

if min(currents) < 1  % very crude, but best i can do since matlab defaults to doubles.
    disp("currents need to be in an integer number of milliamps.")
end

client.send_currents(int32(currents))
% send an integer number of milliamps to avoid datatype issues.

%% close the client(important!)
client.close()