def parse(command: str):
        """Parse the command string into a list of command tokens.

        The rules of the parser are simple. Command tokens are either separated by spaces or grouped by double quotes. There is no escape.
        
        e.g.: Turns 'import "first name" "second filename' into ['import', 'first filename', 'second filename']
        """
        command_elements: list[str] = command.split(
            " "
        )  # a list of all the elements of the command
        command_tokens: list[
            str
        ] = []  # the tokens the rest of the program will operate on

        in_group: bool = False
        group: list[str] = []
        token: str = ""

        for element in command_elements:
            if element == "":
                continue

            group.append(element)

            if element[0] == '"':  # start of group
                in_group = True

            if element[-1] == '"':  # end of group
                in_group = False

            if not in_group:
                token = " ".join(group)  # form the group into a nice string
                token = token.strip('"')  # remove quote marks around it.
                command_tokens.append(token)  # add it to the tokens
                group = []  # reset the group

        return command_tokens
