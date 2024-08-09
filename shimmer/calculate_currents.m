%CALCULATE_CURRENTS calculate the set of currents to shim with from input
%Skope data.
%   currents should be an array of currents in mA (integers)
%   data can take any shape, is returned by the get_data() function in
%   matlab_client.m
function [currents] = calculate_currents(data, coil_coefficients, spharms)
    % DATA PROCESSING
    % process the data
    data=squeeze(squeeze(data));
    average_field = mean(data, 2);

    %disp('Average field values: [mT]: ')
    %disp(average_field);
    
    % below taken from richard bowtell's script
    field_in_hertz = average_field*267.5e6/(2*pi);  % hydrogen hertz
    
    % TODO: compare these to what skope calculates itself, though this isnt
    % exactly intensive...
    condition_number = cond(spharms);
    spharm_coeffs = lsqr(spharms', field_in_hertz);
    
    currents = zeros([24, 1]);
    
    for i = 1:size(spharm_coeffs)
        currents = currents-(spharm_coeffs(i).*coil_coefficients(i, :))';
    end
end

