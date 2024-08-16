% written by mmct
% based on that by 2017 Skope MR Tech.

% TODO: on monday, test this downstairs and see if it streams in a sensible way
% first test it out at the command line
% and then integrate it into a copy of matlab_client.m
% and then put it into the actual matlab_client.m

function [Data] = get_single_block(FID, PortBase, ScanHeader)
    %% initialise
    Data = [];
    Terminate = False;

    if (FID.BytesAvailable > 0)

        Header = getBlockHeader(FID);

        switch Header.dataID
            case 'D'
                % get just one block
                DataSize = double(Header.blockSize)*double(Header.nrChannels)*8;
                temp = fread(FID, DataSize, 'char');
                temp = reshape(temp, 8, []);
                temp = temp(end:-1:1, :, :);  % data is big-endian

                if(FID.RemotePort) == 2
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
