% 2017 Skope Magnetic Resonance Technologies

function Header = getBlockHeader(FID)
%GETBLOCKHEADER Get the header preceding the data block

%% Get header string
BytesHeader = 42;
S = fread(FID,BytesHeader,'char')';

%% Received header
Header.version      = char(S(1:11));
Header.dataID       = char(S(12));
Header.sendTime     = typecast(uint8(fliplr(S(13:20))),'double'); % LabView uses big-endian
Header.aqTime       = typecast(uint8(fliplr(S(21:28))),'double'); % LabView uses big-endian
Header.procLatency  = typecast(uint8(fliplr(S(29:36))),'double'); % LabView uses big-endian
Header.nrChannels   = typecast(uint8(fliplr(S(37:38))),'uint16'); % LabView uses big-endian
Header.blockSize    = typecast(uint8(fliplr(S(39:42))),'uint32'); % LabView uses big-endian

end

