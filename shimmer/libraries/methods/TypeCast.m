% 2017 Skope Magnetic Resonance Technologies

function S = TypeCast(X)
%TYPECAST Convert number bytewise to a string
%   Each byte of X is converted to a char value and concatenated into one
%   string. See also the LabView documentation for the 'Type Cast' Function

% Get bytes
N = typecast(X,'uint8');

% Convert to char array
S = char(N(end:-1:1)); % Note: LabView uses big-endian
