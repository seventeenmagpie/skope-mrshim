% 2017 Skope Magnetic Resonance Technologies

function [Data, ScanHeader,Prova,TimeString] = getData_C(FID,PortBase,projectPath,varargin)
%GETDATA Get data from the TCP server
% Alartm
% time string
% The conversion does keep the fractional seconds. However, by default datetime arrays
% do not display fractional seconds.
% To display them, specify either the 'Format' name-value pair or the Format property.

%% Initialise
Data         = [];  	% Received data
ScanHeader   = [];      % Received scan header
cBlock       = 1;    	% Current data block
Terminate    = false;   % Termination variable
progress_str = '';      % Progress info


disp('                      ')

if nargin>3
    colorAlarm =[1 0 0; 0 1 0];
    RefLevel = varargin{1,1};
    fig = figure('name','Allarm','Visible','on',...
         'Colormap',colorAlarm,...
         'Color','w','Units','centimeters',...
         'Position',[1 1 35 13.5]); %[1 1 0.2*scrsz(3) 0.5*scrsz(4)]
     Limit = 5;
     ax(1) = axes('Parent',fig, 'FontName','Calibri','FontSize', 15,...
    'Position',[0.1 0.1 0.15 0.8]); % B
    hold(ax(1),'on');
end

%% Receive data
n = 1;
while ~Terminate

    % Check if data if available
    if(FID.BytesAvailable>0)

        % Get the header preceding the data block
        Header = getBlockHeader(FID);

        disp(['n: ' num2str(n) ', Header.dataID = ' Header.dataID]);
        n = n+1;       

        switch Header.dataID
            case 'H' % Header
                % Get the scan header
                disp('Receiving scan header')
                ScanHeader = char(fread(FID,double(Header.blockSize),'char')');
                ScanHeader = jsondecode(ScanHeader);
                Dy = ScanHeader.nrDynamics;
                Int = ScanHeader.nrInterleaves;
                Counter = [1:Int:Dy*Int]; C = 2;
                Prova = zeros(ScanHeader.nrChannels,Dy);
                % ScanHeader.nrChannels, ScanHeader.channels, ScanHeader.channelNames
                
            case 'D' % Data = Data Blocks
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
                    % Dimension of the final data
                   Data = zeros([size(temp),ScanHeader.nrDynamics*ScanHeader.nrInterleaves]);
                   Data(:,:,cBlock) = temp;
%                    TimeString(cBlock,:) = datestr(now,'HH:MM:SS.FFF');
%                    TimeString(cBlock,:) =datetime(datestr(now,'dd-mmm-yyyy HH:MM:SS.FFF'));
                    TimeString(cBlock,:) = datetime(datestr(now,'dd-mmm-yyyy HH:MM:SS.FFF'),'InputFormat','dd-MM-yyyy HH:mm:ss.SSS');
                else
                   % Save data
                   Data(:,:,cBlock) = temp;
                   TimeString(cBlock,:) =datetime(datestr(now,'dd-mmm-yyyy HH:MM:SS.FFF'),'InputFormat','dd-MM-yyyy HH:mm:ss.SSS');
                end
                
                % ----------Evaluate data:
                if cBlock == Counter(1,C)
                    From = Counter(1,C-1);
                    To = Counter(1,C)-1;
                    Prova(:,C) = var(Data(:,:,From:To),[],3);
                    
                    if exist('RefLevel')
                        Eval = (10^cBlock)*Prova(:,C)./RefLevel;
                        Alarm = zeros(size(Eval));
                        Alarm(find(Eval<=Limit),1) = 1;
                        % Represent results:
                          subplot(ax(1),'Parent',fig);
                            imagesc(Alarm,'Parent',ax(1)); %colormap (colorAllarm);
                            box(ax(1),'off');
                            colorbar('FontSize',15,'Ticks',[0 1],'TickLabels',{'Non Valid','Valid'});
                            xlim(ax(1),[0.5 1.5]);
                            ylim(ax(1),[0.5 16.5]);
                            % Get axis handle ax = gca;
                            ax(1).YTick = [1:16];% Set where ticks will be
                            ax(1).YTickLabel = {'B1';'B2';'B3';'B4';'B5';'B6';'B7';'B8';...
                                'B9';'B10';'B11';'B12';'B13'; 'B14';'B15';'B16'};% Set TickLabels;
                            ax(1).XTick = [];
                           drawnow
                           % clf;
                           clear Alarm Eval
                    end
                    
                    if C< Dy
                        C = C+1;
                    end
                    clear From To
                    
                end
                % ----------
                
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
                

            case 'S' % Status =  Receive status
                Status = char(fread(FID,double(Header.blockSize),'char')');
                if(FID.BytesAvailable==0)
                    Terminate = true;
                end
                disp(Status)

            case 'T' % Terminate = End of measurements
                disp('All data received')
                Terminate = true;  
                
            otherwise
                disp('Unknown data ID')
        end
    end
    
end

save([projectPath '\' ScanHeader.scanID '.mat'],'TimeString');
disp(['Time saved in' projectPath '\' ScanHeader.scanID '.mat']);
end

