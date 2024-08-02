% 2017 Skope Magnetic Resonance Technologies

function TCP = initTCPClient(RHOST, Port, BufferSize )
%INITTCPCLIENT Construct and open an TCPIP client

TCP = tcpip(RHOST, Port); 
TCP.Timeout = 0.1;
TCP.NetworkRole = 'client';

% Set size of receiving and sending buffer
set(TCP, 'InputBufferSize', BufferSize);
set(TCP, 'OutputBufferSize', BufferSize);

% Open connection to the server
fopen(TCP); 

end

