%% Preparations
clear all;
clc;

% COMMENT OUT THE INCORRECT LINES
% SET PATH TO SHIMMER DIRECTORY
% ON MAGS' LAPTOP
%shimmer_directory = '/home/mags/Documents/studies/uni/summer_placement/skope-mrshim/shimmer/';

% ON SKOPE COMPUTER
shimmer_directory = 'C:/Users/skope/Documents/shimmer-newest/';

% ON MRSHIMS COMPUTER
%shimmer_directory = N/A;

% add libraries to matlab path.
addpath([shimmer_directory, 'libraries/'])
addpath([shimmer_directory, 'libraries/methods/']);
data_folder = [shimmer_directory , 'data/'];

% adds libraries to the python path
% From: https://uk.mathworks.com/help/matlab/matlab_external/call-user-defined-custom-module.html
if count(py.sys.path, shimmer_directory) == 0
    insert(py.sys.path, int32(0), pwd);
end

NUMBER_COIL_CHANNELS = 24;
NUMBER_SKOPE_CHANNELS = 16;

%% reload python module
% use only on first run or when debugging, otherwise just adds lots of loading time
interface = py.importlib.import_module('libraries.matlab_interface');
py.importlib.reload(interface);

%% Set connection properties
PortBase = 6400;        % Default value 6400
BufferSize = 1e7;       % Buffer must be large enough to hold a data block
Host = 'localhost';     % Set remote host IP


%% Ports for data types
% PortBase+0 : Command 6400
% PortBase+1 : Phase   6401
% PortBase+2 : Raw     6402
% PortBase+3 : k       6403
% PortBase+4 : Bfit    6404
% PortBase+5 : Gfit    6405
% PortBase+6 : Log     6406


%% initialize connections

% init TCP/IP client object 'command'.
connCtrl = initTCPClient( Host, PortBase, BufferSize ); 

% init TCP/IP client object for 'Bfit'
portData = PortBase + 4;
connData = initTCPClient( Host, portData, BufferSize );

% TODO: add explanation of how to stream additional data

%% initiate python client interface
client = interface.MatlabClient('matlab');
client.start_connection()

%% get probe positions
% steps repeated from RBowtell's code
scan_id = 6;
scan_metadata=AqSysData(data_folder, scan_id);
positions=scan_metadata.probePositions;

%% produce mask from field map
[img, ~] = rec_read_sjm([data_folder, 'field_map']);
dimensions=size(img);
magnitude=squeeze(img(:, :, :, 1,1));
field_map = squeeze(img(:, :, :,2,2 ));

% make the mask
threshhold = 0.05*max(max(max(magnitude)));
mask=zeros(size(magnitude));
mask(magnitude > threshhold) = 1;

%% read in the coil effect file (from Arche)
coil = readNPY([data_folder, 'coil_tmp.npy']);
coil = reshape(coil, 24, 64, 64, 45);  % field per unit current per coordinate

%% setup various arrays
% make a coordidate grid based on the mask
mask_size = size(mask);
resolution = 3e-3;
z_resolution = 3.3e-3;

% integer index coordinates for each voxel
x=resolution*((-mask_size(1)/2):(mask_size(1)/2-1));
y=resolution*((-mask_size(2)/2):(mask_size(2)/2-1));
z=z_resolution*((-mask_size(3)/2):(mask_size(3)/2-1));

% imagespace coordinate grid
% NOTE: using meshgrid puts X and Y the other way around.
% not sure what that is about but this way is consistent with the rest of
% Richard's code.
[X, Y, Z] = ndgrid(x, y, z);

% image space coordinates inside the masked region
X1 = X(mask > 0);
Y1 = Y(mask > 0); 
Z1 = Z(mask > 0);

% takes the coil effect inside the masked region and unrolls it
% this is because lsqr only works on 2d
for i = 1:NUMBER_COIL_CHANNELS
    coil_squeezed = squeeze(coil(i, :, :, :));  % the effect of one of the 24 coils
    coil_unrolled(i, :) = coil_squeezed(mask > 0);
end

targets=[ones(size(X1)), Z1, X1, Y1];  % the low dimensional spherical harmonics
idx = 0;  % a counter
coil_coefficients = zeros([24, 4])';  % to store the coefficients

for target = targets 
    idx = idx + 1;
    % how much of each coil we need to create a particular spharm field
    coil_coefficients(idx, :) = lsqr(coil_unrolled', target, [], 50);
end

% find spherical harmonics values at probe positions
probe_x = positions(:, 1);
probe_y = positions(:, 2);
probe_z = positions(:, 3);
    
spharms(1, :) = ones(size(probe_x));
spharms(2, :) = probe_z;
spharms(3, :) = probe_x;
spharms(4, :) = probe_y;

%% get scan def and edit parameters

% retrieve JSON Scan Definition (getShortScanDef)
%shortScanDef = sendCommand(connCtrl, 'getShortScanDef' );
%disp(shortScanDef)

% modify short scan definition (setShortScanDef)
shortScanDef.scanName = 'shimmer';
shortScanDef.scanDescription = 'Dynamic shimming via Shimmer (MMCT, 2024)';
shortScanDef.nrDynamics = 100;  % skope needs at least 2 dynamics to do the bfit.
shortScanDef.dynamicTR = 0.5;  % want this to be as short a possible for lowest latency
% another parameter to look at is interleaving.
% all paramters are described in the manual and the names in shortScanDef
% are in the TCP_control_client.m example.
shortScanDef.fitStart = 0;
shortScanDef.fitDuration = 0.005;
shortScanDef.extTrigger = false;
shortScanDef.raw = false;
shortScanDef.k = false;
shortScanDef.Bfit = true;
disp('Setting short scan paramaters.');
sendCommand(connCtrl, 'setShortScanDef', shortScanDef );

% retrieve JSON Scan Definition (getShortScanDef)
shortScanDef = sendCommand(connCtrl, 'getShortScanDef' );
disp(shortScanDef)

% get project path
disp('Bfit scan data will be stored at:');
projectPath = sendCommand(connCtrl, 'getProjectPath' );
disp(projectPath)
%% create figure 
figure(1)
hold on  % so we can append data.
sendCommand(connCtrl, 'startScan' );

%% start scan
disp('Beginning scan loop.');
keep_going = [];
count = 1;
previous_data = zeros(16, 1);
scanHeader = [];
while isempty(keep_going)
    % receive B fit data
    [data, scanHeader] = getDataByBlock(connData, PortBase, scanHeader);
    data = squeeze(squeeze(data));
    previous_data = [previous_data, data];
    plot(previous_data')

    % check we have data, if not, skip the processing and acquire it again
    if 1 && all(all(data == 0))
        %disp("No data recieved. Trying again.")
        continue  % goes to next iteration of loop
    else
        disp("Recieved data.")
        disp(count)
    end
    
    disp("Calculating currents.")

    currents = calculate_currents(data, coil_coefficients, spharms);

    disp("Currents are: [mA]")
    %disp(currents')  % currents are also displayed by python so this is
    %redundant

    if (rms(currents) > 2000)
        disp("rms of currents exceeds 2000mA, setting currents to zero.")
        currents = zeros(24, 1);
    elseif (rms(currents) > 1500)
        disp("Warning! rms of currents exceeds 1700mA.")
    end

    % SENDING THE CURRENTS
    % currents should be a ROW vector of currents in MILLIAMPS
    client.send_currents(int32(currents'));
    disp("Currents sent.")

    %keep_going = input('Enter anything to stop. ');
    count = count +1;
end

%% disconnect from python server
% If error occours, close the connection
disp("Disconnecting from Shimmer server.")
client.close()
%% disconnect from skope server
disp('Disconnecting from Skope server. ')
fclose(connData); clear connData;
fclose(connCtrl); clear connCtrl;
