classdef StatusPrinter < handle
    properties
        status
        status_string
    end
    methods
        function obj = StatusPrinter()
            obj.status.starttime = datetime('now');
            obj.status.skope = '';
            obj.status.currents = '';
            obj.status.write = '';
            obj.status.count = '';
            obj.status.uptime = '';

            obj.status_string = '';
        end

        function [] = update_status(obj, key, value)
            switch key
                case 'skope'
                    obj.status.skope = value;
                case 'currents'
                    obj.status.currents = value;
                case 'write'
                    obj.status.write = value;
                case 'count'
                    obj.status.count = value;
                case 'time'
                    obj.status.uptime = obj.status.starttime - value;
            end
            % delete the old data
            fprintf([repmat('\b',1,numel(obj.status_string))])

            % then set the new one (we need the length of the old string)
            obj.status_string = sprintf(['\nAcquiring Skope data: %s' ...
                '\nCalculating currents: %s' ...
                '\nWriting shim values : %s' ...
                '\nCount               : %d' ...
                '\nUptime              : %s\n'], ...
                obj.status.skope, ...
                obj.status.currents, ...
                obj.status.write, ...
                obj.status.count, ...
                obj.status.uptime);

            fprintf('%s',obj.status_string);
            pause(1)
        end
    end
end