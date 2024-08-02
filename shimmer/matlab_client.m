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
addpath([shimmer_directory, '/libraries/'])
addpath([shimmer_directory, '/libraries/methods/']);
data_folder = [shimmer_directory , 'data/'];
skope_temp = [shimmer_directory, 'data/skope_tmp'];

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

%% inititate python client interface
client = interface.MatlabClient('matlab');
client.start_connection()

%% get probe positions
% steps repeated from RBowtell's code
scan_id = 5;
scan_metadata=AqSysData(data_folder, scan_id);
positions=scan_metadata.probePositions;

%% produce mask from field map
[img, ~] = rec_read_sjm([data_folder, 'field_map_jul_08']);
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
resolution_z = 3.3e-3;

% TODO: rewrite using linspace/meshgrid
% this is just copied from Richard's script.
% integer index coordinates for each voxel
x=(-mask_size(1)/2):(mask_size(1)/2-1);
y=(-mask_size(2)/2):(mask_size(2)/2-1);
z=(-mask_size(3)/2):(mask_size(3)/2-1);

% image space coordinates for each voxel
X=resolution*repmat(reshape(x,[mask_size(1) 1 1]),[1 mask_size(2) mask_size(3)]);
Y=resolution*repmat(reshape(y,[1 mask_size(2) 1]),[mask_size(1) 1 mask_size(3)]);
Z=resolution_z*repmat(reshape(z,[1 1 mask_size(3)]),[mask_size(1) mask_size(2) 1]);

% image space coordinates inside the masked region
X1 = X(mask > 0);
Y1 = Y(mask > 0); 
Z1 = Z(mask > 0);

% coil effect inside the masked region
% and unwrap the coil effect matrix (not sure why)
% TODO: ask richard why
for i = 1:NUMBER_COIL_CHANNELS
    coil_squeezed = squeeze(coil(i, :, :, :));
    coil_unrolled(i, :) = coil_squeezed(mask > 0);
end

% TODO: work out what this does exactly
targets=[ones(size(X1)), Z1, X1, Y1];
idx = 0;
coil_coefficients = zeros([24, 4])';

for target = targets 
    idx = idx + 1;
    % how much of each coil we need to create a particular spharm field?
    % because we only do this once, we can afford more than 20
    % iterations to reach a low tolerance
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
shortScanDef = sendCommand(connCtrl, 'getShortScanDef' );
disp(shortScanDef)

% modify short scan definition (setShortScanDef)
shortScanDef.scanName = 'shimmer';
shortScanDef.scanDescription = 'Dynamic shimming via Shimmer (MMCT, 2024)';
shortScanDef.nrDynamics = 2;  % skope needs at least 2 dynamics to do the bfit.
shortScanDef.dynamicTR = 0.3;  % want this to be as short a possible for lowest latency
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

% set project path
disp('Setting project path. ');
sendCommand(connCtrl, 'setProjectPath', skope_temp );

% get project path
disp('Bfit scan data will be stored at:');
projectPath = sendCommand(connCtrl, 'getProjectPath' );
disp(projectPath)

%% start scan
disp('Beginning scan loop.');
keep_going=[];
count = 0;
while isempty(keep_going)
    sendCommand(connCtrl, 'startScan' );
    
    % TODO: make a nice status thing that continuously
    % updates.
    % maybe like: 
    % Acquiring Skope data: ' '/in progress/done
    % Calculating currents: ' '/in progress/done
    % Writing shim values : ' '/in progress/done
    % Count               :             1234
    % Uptime              :            10:03
    % this is probably quite difficult to do nicely.
    % should make a status_update("Status", "Value") function that does the
    % backspacing and padding and everything for us.
    % status_update("reset")

    % receive B fit data
    disp("Acquiring Skope data.")
    [data, scanHeader] = getData(connData,portData);
    
    % check we have data, if not, skip processing and acquire again
    if 1 && all(all(data == 0))
        %disp('its all for nought!')
        continue  % goes to next iteration of loop
    end
    
    % process the data
    data=squeeze(squeeze(data));
    average_field = mean(data, 2);

    %disp('Average field values: [mT]: ')
    %disp(average_field);
    
    % below taken from richard bowtell's script
    field_in_hertz = average_field*267.5e6/(2*pi);  % hydrogen hertz
    
    % TODO: compare these to what skope calculates itself, though this isnt
    % exactly intensive...
    condition_number = cond(spharms);
    disp("Calculating currents.")
    spharm_coeffs = lsqr(spharms', field_in_hertz);
    
    currents = zeros([NUMBER_COIL_CHANNELS, 1]);
    
    for i = 1:size(spharm_coeffs)
        currents = currents-(spharm_coeffs(i).*coil_coefficients(i, :))';
    end

    %disp('Currents are: [mA]')
    %disp(currents)
    
    disp("Writing currents.")
    % currents should be a ROW vector of currents in MILLIAMPS
    client.send_currents(int32(currents'))
    
    %keep_going = input('Enter anything to stop. ');
    disp("That was loop number: ", count)
    count = count +1;
end

%% close connections
% If error occours, close the connection
disp("Disconnecting from Shimmer server.")
client.close()

disp('Disconnecting from Skope server. ')
fclose(connData); clear connData;
fclose(connCtrl); clear connCtrl;