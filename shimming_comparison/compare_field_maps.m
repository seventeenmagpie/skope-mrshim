% compares two field maps, shimmed and unshimmed.
% written by mmct in August 2024
% based on code by Prof. Richard Bowtell

close all;  % close all figures
% clear;  % ONLY IF NOT CURRENTLY SHIMMING
clc;

% COMMENT OUT THE INCORRECT LINES
% SET PATH TO SHIMMER DIRECTORY
% ON MAGS' LAPTOP
shimmer_directory = '/home/mags/Documents/studies/uni/summer_placement/skope-mrshim/shimmer/';

% ON SKOPE COMPUTER
%shimmer_directory = 'C:/Users/skope/Documents/shimmer/';

% ON MRSHIMS COMPUTER
%shimmer_directory = N/A;

addpath([shimmer_directory, 'libraries/'])
addpath([shimmer_directory, 'libraries/methods/']);

% PLEASE PUT THE FIELD MAPS TO BE COMPARED IN THE SHIMMING_COMPARISON FOLDER
% enter file names here:
before_movement = '';
without_shimming = '';
with_shimming = '';
%% read in the first image to form a mask
% BEFORE MOVING PHANTOM
[jmg, ~] = rec_read_sjm([before_movement]); % read in first image data set 
mag1=squeeze(jmg(:,:,:,1,1));  %magnitude data
field1=squeeze(jmg(:,:,:,2,2)); %field data 

thresh=0.04*max(max(max(mag1)));
mask=zeros(size(mag1));
mask(mag1>thresh)=1; % make a mask 

figure
out=imtile(mag1,'GridSize', [2 11]); %tile the 22 slices
%clim=[-500 500];
imagesc(out)
axis off
axis equal
title('Magnitude data') 

%% unshimmed data
mims=size(mask);
% WITH NO SHIMS
[jmg, ~] = rec_read_sjm([without_shimming]); % read in first image data set 
field2=squeeze(jmg(:,:,:,2,2)); %field data 

fielddiff1=(field2-field1).*mask;

figure
out=imtile(fielddiff1,'GridSize', [2 11]); %tile the 22 slices
%clim=[-10 10];
imagesc(out)
axis off
axis equal
title('Difference in field before and after movement') 
colorbar
datacursormode on

figure (77)
subplot(1,2,2)
vals=fielddiff1(mask>0);
histogram(vals,100)
title ('Unshimmed') 

disp(["Standard deviation of unshimmed data is", std(vals)])
disp(["Mean of unshimmed data is", mean(vals)])

%% shimmed data
[jmg, ~] = rec_read_sjm([with_shimming]); % read in first image data set 
field2=squeeze(jmg(:,:,:,2,2)); %field data 

fielddiff2=(field2-field1).*mask;

clear vals
figure (77)
subplot(1,2,1)
vals=fielddiff2(mask>0);
histogram(vals,100)
title ('Shimmed') 

disp(["Standard deviation of shimmed data is", std(vals)])
disp(["Mean of shimmed data is", mean(vals)])

figure
out=imtile(fielddiff2,'GridSize', [2 11]); %tile the 22 slices
%clim=[-10 10];
imagesc(out)
axis off
axis equal
title('SHIMMED Difference in field before and after movement') 
colorbar
datacursormode on