% 2017 Skope Magnetic Resonance Technologies

function Data = sendCommand(FID, command, value )
%SENDCOMMAND Send a command to the TCP server

%% Create command structure
switch nargin
	case 2
		CommandStruct.command = command;
        CommandToBeSent = jsonencode(CommandStruct);
	case 3
		CommandStruct.command = command;
		CommandStruct.value = value;
		CommandToBeSent = jsonencode(CommandStruct);
	otherwise
		error('The function requires two or three input arguments (depending on command)');
end

%% Create header
Version   = '2017.0.0000';
DataID    = 'C';
sendtime  = datenum(datetime(('now')) - datetime(1904,0,0,0,0,0,0)) * 24 * 60 * 60;
size      = uint32(length(CommandToBeSent));

% Convert to string
HeaderToBeSent = [Version,DataID,TypeCast(sendtime),TypeCast(double(0)),TypeCast(double(0)),TypeCast(uint16(0)),TypeCast(size)];

%% Execute command
% Send header
fwrite(FID,HeaderToBeSent)

% Send command
fwrite(FID,CommandToBeSent)

%%
Terminate   = false;  % Termination variable
Data        = [];

%% Receive data
while ~Terminate
    
   %% Check if data if available
    if(FID.BytesAvailable>0)     

        %% Get header
        Header = getBlockHeader(FID);
        
        switch Header.dataID
           case 'D'             
                % Receive data
                Data = char(fread(FID,double(Header.blockSize),'char')');
				Data = jsondecode(Data);
                Terminate = true;
                
            case 'S'
                % Receive status
                Status = char(fread(FID,double(Header.blockSize),'char')');
                if(FID.BytesAvailable==0)
                    Terminate = true;
                end
                disp(Status)
                
            case 'E'
                disp('Unknown error occurred')
                Error = char(fread(FID,double(Header.blockSize),'char')');
                disp(Error)
                Terminate = true;
            case 'A'
                disp('Command acknowledged')
                Terminate = true;
        end
    end
end
end

