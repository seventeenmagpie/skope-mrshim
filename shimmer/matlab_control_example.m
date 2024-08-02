%% Preparations
clear all;
clc;

% COMMENT OUT THE INCORRECT LINES
% SET PATH TO SHIMMER DIRECTORY
% ON MAGS' LAPTOP
shimmer_directory = '/home/mags/Documents/studies/uni/summer_placement/skope-mrshim/shimmer';

% ON SKOPE COMPUTER
%shimmer_directory = 'C:/Users/skope/Documents/shimmer/';

% ON MRSHIMS COMPUTER
%shimmer_directory = N/A;

% add libraries to matlab path.
% contains the python interface file
addpath([shimmer_directory, '/libraries/'])

% adds libraries to the python path
% From: https://uk.mathworks.com/help/matlab/matlab_external/call-user-defined-custom-module.html
if count(py.sys.path, shimmer_directory) == 0
    insert(py.sys.path, int32(0), pwd);
end

%% inititate python client interface
client = interface.MatlabClient('matlab');
client.start_connection()

% currents should be a ROW vector of currents in MILLIAMPS
currents=[10, 20, 30]
client.send_currents(int32(currents))

%% close connectio
client.close()
