import subprocess
import shlex

import logging
logger = logging.getLogger("kitero.helper.commands")

class Commands(object):
    """Helper class to run a set of commands"""

    @classmethod
    def run(cls, *args, **kwargs):
        """Run one or several commands.

        Several commands may be provided. If named arguments are
        provided, they will be used for string formatting each
        command. The commands are **not** run inside a shell.

        If a command fails, :exception:`CommandError` is raised.

        :returns: commands outputs
        :rtype: string or a list of strings
        :raises: :exception:`CommandError`
        """
        if not args:
            return None
        index = 0
        results = []
        for command in args:
            arguments = [x % kwargs for x in shlex.split(command)]
            logger.info("%s: run (%r)" % (arguments[0], " ".join(arguments)))
            try:
                process = subprocess.Popen(arguments,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
            except OSError as err:
                raise CommandError(command, err.errno, index)
            output, _ = process.communicate()
            retcode = process.poll()
            logger.info("%s: finished with code %d (%r)" % (arguments[0], retcode,
                                                             " ".join(arguments)))
            if retcode:
                raise CommandError(command, retcode, index)
            results.append(output)
            index = index + 1
        if len(results) == 1:
            return results[0]
        return results

class CommandError(Exception):
    """Exception describing an error in a command."""

    def __init__(self, command, retcode, index=None):
        """Build a new exception.

        :param command: the command being executed
        :type command: string
        :param retcode: the error received
        :type retcode: integer
        :param index: the index of the command
        :type index: integer
        """
        self.command = command
        self.retcode = retcode
        self.index = index

    def __str__(self):
        return 'command %r failed with error %d' % (self.command, self.retcode)
