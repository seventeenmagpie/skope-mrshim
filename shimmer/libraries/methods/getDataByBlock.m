% written by mmct
% based on getDataByAq (IE, getData) by 2017 Skope MR Tech.

function [Data, ScanHeader] = getDataByBlock(FID, PortBase, prev_header)
    %% initialise
    Data = [];
    ScanHeader = prev_header;
    %Terminate = False;

    if (FID.BytesAvailable > 0)

        Header = getBlockHeader(FID);

        switch Header.dataID
            case 'H'
                % get the scan header
                ScanHeader = char(fread(FID, double(Header.blockSize), 'char')');
                ScanHeader = jsondecode(ScanHeader);
            case 'D'
                % get just one block
                DataSize = double(Header.blockSize)*double(Header.nrChannels)*8;
                temp = fread(FID, DataSize, 'char');
                temp = reshape(temp, 8, []);
                temp = temp(end:-1:1, :, :);  % data is big-endian

                if(FID.RemotePort) == (PortBase + 2)
                    % complex raw data
                    temp = typecast(uint8(temp(:)), 'int32=>int32');
                    temp = reshape(temp, 2, double(Header.nrChannels), []);
                    temp = double(squeeze(complex(temp(1, :, :), temp(2, :, :))));
                else
                    % all other data types
                    temp = typecast(uint8(temp(:)), 'double');
                    temp = reshape(temp, double(Header.nrChannels), []);
                end

                Data = temp;

                
            case 'S'
                % Receive status
                Status = char(fread(FID,double(Header.blockSize),'char')');
                disp(Status)
            case 'T'
                disp("End of scan.")
            otherwise
                disp("Not a useful block.")
        end
    end
end
