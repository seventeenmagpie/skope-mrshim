% 2017 Skope Magnetic Resonance Technologies

function [Data, ScanHeader] = getData(FID,PortBase)
%GETDATA Get data from the TCP server

%% Initialise
Data         = [];  	% Received data
ScanHeader   = [];      % Received scan header
cBlock       = 1;    	% Current data block
Terminate    = false;   % Termination variable
progress_str = '';      % Progress info

disp('                      ')

%% Receive data
while ~Terminate
    
    % Check if data if available
    if(FID.BytesAvailable>0)
        
        % Get the header preceding the data block
        Header = getBlockHeader(FID);

        switch Header.dataID
            case 'H'
                % Get the scan header
                disp('Receiving scan header')
                ScanHeader = char(fread(FID,double(Header.blockSize),'char')');
                ScanHeader = jsondecode(ScanHeader);
                
            case 'D'
                % Report progress
                percentFinished = floor((100*cBlock)/(ScanHeader.nrDynamics*ScanHeader.nrInterleaves));
                progress_str    = sprintf('\nReceiving data block #%d | Progress = %3.0f%%\n',cBlock,percentFinished );
                fprintf([repmat('\b',1,numel(progress_str)) '%s'],progress_str);
                
                % Get the data
                DataSize = double(Header.blockSize)*double(Header.nrChannels)*8;
                temp = fread(FID,DataSize,'char');
                temp = reshape(temp,8,[]);
                temp = temp(end:-1:1,:,:); % LabView uses big-endian

                % Cast to correct format
                if(FID.RemotePort == PortBase+2) 
                    % Complex raw data
                    temp = typecast(uint8(temp(:)),'int32=>int32');
                    temp = reshape(temp,2,double(Header.nrChannels),[]);
                    temp = double(squeeze(complex(temp(1,:,:),temp(2,:,:))));  
                else
                    % All other data types
                    temp = typecast(uint8(temp(:)),'double');
                    temp = reshape(temp,double(Header.nrChannels),[]);
                end
                                
                % Initialise data matrix when first data block is received
                if(isempty(Data))
                   Data = zeros([size(temp),ScanHeader.nrDynamics*ScanHeader.nrInterleaves]);
                   Data(:,:,cBlock) = temp;
                else
                   Data(:,:,cBlock) = temp;
                end
                
                % Display
                switch (FID.RemotePort-PortBase)
                    case 1
                        plot(temp.'), xlabel('Samples'),ylabel('Phase [rad]')
                    case 2
                        plot(abs(temp).'), xlabel('Samples'),ylabel('Magntiude [a.u.]')   
                    case 3
                        plot(temp.'), xlabel('Samples'),ylabel('k-space')
                    case 4
                        stairs(squeeze(Data).'), xlabel('Dynamics and interleaves'),ylabel('Bfit')
                    case 5
                        stairs(squeeze(Data).'), xlabel('Dynamics and interleaves'),ylabel('Gfit')   
                end
                drawnow
                
                % Increment for next reception
                cBlock = cBlock+1;
                

            case 'S'
                % Receive status
                Status = char(fread(FID,double(Header.blockSize),'char')');
                if(FID.BytesAvailable==0)
                    Terminate = true;
                end
                disp(Status)

            case 'T'
                disp('All data received')
                Terminate = true;  
                
            otherwise
                disp('Unknown data ID')
        end
    end
    
end
end

