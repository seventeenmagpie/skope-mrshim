%*****************       Image Export Tool V4.X!!!        *******************
%   Reads 16-bit integer data from specified filename (without extensiton)
%   that is in the Philips rec format.  The type is set in:
%   Scan Utilities>Enter Service Mode>Control Parameters>Reconstruction 
%   Control Parameters.
%   The options are actually 8 or 12 bit but when 12 bit is specified, it
%   is stored in the rec file as 16-bit.  The 3T is set to force 12 bit so
%   that is what is used here.  1.5T data is also 16-bit.
%
%   The par and rec scaling is corrected for in the reconstruction to allow
%   the data to be used for quantitation.
%
%   MFC - 22.05.06;
%
%   **N.B.** This reader works for V4 of the export tool which assigns
%   resolution on an image by image basis, i.e. for each slice, echo etc.
%   In V3 this is given as global info at top of header file.  (V3 data can
%   be read by rec_read_V3 but only separates data into series of images,
%   i.e. does not separate slices, echoes, dynamics etc.)  For V4 separates
%   echoes, slices, phases, dynamics & gradient orientations.  Averages are
%   already combined at this point.
%   Gyroscan release: 9, 10 - V3; 1.2, 1.5, 1.7 - V4; 2.0 - V4.1.
%
%   In Export Tool V4.1 diffusion data is no longer handled within dynamics
%   but using tags of gradient orientation.  Hence V4.1 has more tags to
%   read in from the header_info.  DTI data contains directions; b0 and
%   an average image so will have (directions + 1)*b values + b0 images in
%   total (assuming average image for each b value).
%
%   Extended code for these changes and to handle arbitrary "dyn" ordering
%   - otherwise matrices are artificially big.  
%   
%   MFC - 20.10.06;
%
%   Added support for version 4.2, which has an extra column in the end
%   with ASL labelling information (1: tag, 2: control).
%
%   MV - 25.04.08
%
%   SJM 9-10-08:    Hacked to also include type and seq. This is needed for AFI. 
%   SJM 23-2-09:    output voxel size information
%**************************************************************************

function [rec_image,info] = rec_read(filename)


% GETTING FILENAMES:

if exist('filename','var')
    headername = [filename '.PAR'];
    dataname = [filename '.REC'];
else
    [file, path] = uigetfile('*.PAR');
    headername = [path file];
    [path, filename, ext] = fileparts(headername);
    dataname = [path filesep filename '.REC'];
end



% READING DATA FROM REC FILE:

tempfid = fopen(dataname, 'r', 'ieee-le');
if tempfid == -1
    error('Problem opening .REC file.  Check filename.')
    return
end
[data count] = fread(tempfid,'short');
fclose(tempfid);



% OPENING PAR FILE AND READING INFO:

tempfid = fopen(headername, 'r', 'ieee-le');
if tempfid == -1
    error('Problem opening .PAR file.  Check filename.')
    return
end

% Store as: {echoes, slices, phases, dynamics, GR orientations, b_val_nr}:
% Include Labelling
dims = cell(1,7);
dims{1,1} = 'echoes; '; dims{1,2} = 'slices; '; dims{1,3} = 'phases; ';
dims{1,4} = 'dynamics; '; dims{1,5} = 'GR orientations; '; dims{1,6} = 'b Value #';
dims{1,7} = 'label type';
% SJM add type and seq
dims{1,8} = 'type (Mag/Ph?); ';dims{1,9} = 'seq (extra?); ';
dim_chk = [1,1,1,1,1,1,1,1,1];  %Assume basic image first then modify when > 1 (below)

% Initialisation for reading non-sequential dynamics with arbitrary start:
dynamic_nrs = []; dynamic = [];

% similar to above for type and sequence
tynums=[];seqnums=[];

%% -------------------------------------------------------------------------
% SJM 23-2-09: before getting into the slice specific information, record
% some of the other header information
start_idx=45; %beginning of entry in line
for ii=1:50, % look at first 50 lines
    header_info = fgetl(tempfid);

    if strfind(header_info, 'FOV (ap,fh,rl) [mm]')
        tmp = header_info(start_idx:end);
        info.fov = sscanf(tmp,'%f %f %f');
        continue;
    end

    if strfind(header_info, 'Angulation midslice(ap,fh,rl)[degr]')
        tmp = header_info(start_idx:end);
        info.ang = sscanf(tmp,'%f %f %f');
        continue;
    end

    if strfind(header_info, 'Off Centre midslice(ap,fh,rl) [mm]')
        tmp = header_info(start_idx:end);
        info.offc = sscanf(tmp,'%f %f %f');
        continue;
    end
    
     if strfind(header_info, 'Repetition time [ms] ')
        tmp = header_info(start_idx:end);
        info.TR = sscanf(tmp,'%f %f');
        continue;
     end
    
     if strfind(header_info, 'Scan mode')
         tmp = header_info(start_idx:end);
         info.mode = sscanf(tmp,'%s');
         continue;
     end
     
     if strfind(header_info, 'Water Fat shift [pixels]')
         tmp = header_info(start_idx:end);
         info.wfs = sscanf(tmp,'%f');
         continue;
     end
     
     if strfind(header_info, 'Scan Duration [sec]')
         tmp = header_info(start_idx:end);
         info.dur = sscanf(tmp,'%f');
         continue;
     end
     
     if strfind(header_info, 'Max. number of slices/locations')
         tmp = header_info(start_idx:end);
         info.slices = sscanf(tmp,'%f');
         continue;
     end
end
%%
% Go straight to reading label data from info at file end by looking for
% line containing "sl " then read on two further lines to the actual info.
id = [];
while size(id) == 0
    header_info = fgetl(tempfid);
    id = strfind(header_info, 'sl ');
end
header_info = fgetl(tempfid);
header_info = str2num(fgetl(tempfid));
te_idx=1;
while ~isempty(header_info)
    
    % header_info stores up to 49 attributes (48 for V4.1, 49 for V4.2) to 
    % define the image: [slice echo dyn phase type seq idx pix scan x y 
    % intercept slope scale wc ww ang_ap ang_fh ang_rl off_ap off_hf off_rl
    % thk gap disp_ori sl_ori fmri es_r_ed delta_x delta_y TE t_dyn t_trig 
    % b_val av FA bpm minRR maxRR turbo TI // b_val_nr gr_ori cont diff_ani 
    % diff_ap diff_fh diff_rl label].  Only read in what is needed:
    slice = header_info(1);
    echo = header_info(2);
    dyn = header_info(3);
    phase = header_info(4);
    ty = header_info(5);  % SJM 27-7-09 changed from +1 
    seq = header_info(6); % SJM 27-7-09 changed from +1 
    idx = header_info(7);
    x = header_info(10);
    y = header_info(11);
    RI = header_info(12);
    RS = header_info(13);
    SS = header_info(14);
    
    %4-3-09
    TE(te_idx)=header_info(31);
    % 10-9-09
    FLIP(te_idx)=header_info(36);
    te_idx=te_idx+1;
    
    % Par file contains more header info for diffusion scans on release 2!
    % This is export tool V4.1!!!
    if length(header_info) > 41
        version = 'V4.1';
        b_val_nr = header_info(42);
        label=1;
        gr_ori = header_info(43);   %This increments for diff gradient directions
        if length(header_info) > 48
           version = 'V4.2';
           label=header_info(49);
        end
    else
        version = 'V4';
        b_val_nr = 1;
        gr_ori = 1;
    end
    
    % For each new dynamic number increase the number of dynamics:
    if ~ismember(dyn, dynamic_nrs)
        if isempty(dynamic)
            dynamic = 1;
            dynamic_nrs = dyn;
        else
            dynamic = [dynamic dynamic(end)+1];
            dynamic_nrs = [dynamic_nrs dyn];
        end
    end
    
    % keep track of which type and seq #s actually hold images
    if ~ismember(ty,tynums)
        tynums = [tynums ty];
    end
    if ~ismember(seq,seqnums)
        seqnums = [seqnums seq];
    end
    % EXTRACT IMAGE AND ASSIGN TO MATRIX:
    image = reshape(data(1+idx.*(x.*y):(idx+1).*x.*y),x,y);
          
    % Correct Scaling (should return data to raw value for quantitation):
%     rec_image(:,:,echo,slice,phase,dynamic(dynamic_nrs == dyn),gr_ori,b_val_nr,label) = (image.*RS +RI)./(RS.*SS);
    rec_image(:,:,echo,slice,phase,find(tynums==ty),find(seqnums==seq),dynamic(dynamic_nrs == dyn),gr_ori,b_val_nr,label) = (image.*RS +RI)./(RS.*SS);
 
    % See which dims are active:
%     dim_chk = [max(dim_chk(1),echo),max(dim_chk(2),slice),max(dim_chk(3),phase),...
%         max(dim_chk(4),dynamic(dynamic_nrs == dyn)),max(dim_chk(5),gr_ori),max(dim_chk(6),b_val_nr),max(dim_chk(6),label)];
    % SJM
    dim_chk = [max(dim_chk(1),echo),max(dim_chk(2),slice),max(dim_chk(3),phase),...
        max(dim_chk(4),dynamic(dynamic_nrs == dyn)),max(dim_chk(5),gr_ori),max(dim_chk(6),b_val_nr),max(dim_chk(6),label)...
                  max(dim_chk(8),ty) max(dim_chk(9),seq)  ]; % might not be best way

    
    header_info = str2num(fgetl(tempfid));
    
end
fclose(tempfid);

% TIDY UP AND EXPLAIN:
rec_image = squeeze(rec_image);
%rec_image = squeeze(rec_image(:,:,:,:,:,tynums,seqnums,:,:,:,:)); % only save type and seq that contain images
info.te=TE;
info.flip=FLIP;
disp(' ')
disp(['Data read as Export Tool: ', version]);
disp(['Output contais ',num2str(length(size(rec_image))),' dimensions: x; y; ',dims{1,dim_chk > 1}]);
if b_val_nr > 1
    disp(['Note: Last Image under GR orientation for a given b value is the average diffusion image.'])
    disp(['And b=0 will have only one non-zero GR orientation!'])
end
disp(' ')

return