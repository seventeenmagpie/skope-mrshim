% by mmct
% based on that by 2017 Skope MR Tech.

function [ScanHeader] = get_just_scan_header(FID, PortBase)
    % this gets just the 'H' part of the Skope data packet.
    Data = [];
    ScanHeader = [];
        
    if(FID.BytesAvailable>0)
        Header = getBlockHeader(FID);

        switch Header.dataID
            case 'H'
                % get the scan header
                ScanHeader = char(fread(FID, double(Header.blockSize), 'char')');
                ScanHeader = jsondecode(ScanHeader);
            otherwise
                disp('Not the scan header.')
                ScanHeader = [];
        end
    end
end
