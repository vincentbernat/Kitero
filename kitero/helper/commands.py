import subprocess
import shlex

import logging
logger = logging.getLogger("kitero.helper.commands")

class Commands(object):
    """Helper class to run a set of commands."""

    @classmethod
    def run(cls, *args, **kwargs):
        """Run one or several commands.

        Several commands may be provided. If named arguments are
        provided, they will be used for string formatting each
        command. The commands are **not** run inside a shell.

        If a command fails, :exc:`CommandError` is raised.

        :returns: commands outputs
        :rtype: string or a list of strings
        :raises: :exc:`CommandError`
        """
        return cls._run(args, kwargs)

    @classmethod
    def run_noerr(cls, *args, **kwargs):
        """Run one or several commands event if their status is not 0.

        If one command does not exist, we still get an error.

        :returns: commands outputs
        :rtype: string or a list of strings
        :raises: :exc:`CommandError`
        """
        return cls._run(args, kwargs, ignore_errors=True)

    @classmethod
    def _run(cls, commands, substitutions, ignore_errors=False):
        """Run a set of commands, apply substitutions and return  results.

        :param commands: a list of commands
        :type commands: list of strings
        :param substitutions: substitutions to be applied to commands
        :type substitutions: dictionary
        :return: results
        :rtype: a string if one command, an array otherwise
        """
        if not commands:
            return None
        index = 0
        results = []
        for command in commands:
            command = (command % substitutions).encode('ascii')
            arguments = shlex.split(command)
            logger.debug("%s: run (%r)" % (arguments[0], " ".join(arguments)))
            try:
                process = subprocess.Popen(arguments,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
            except OSError as err:
                raise CommandError(command, err.errno, index)
            output, _ = process.communicate()
            retcode = process.poll()
            logger.debug("%s: finished with code %d (%r: %r)" % (
                    arguments[0], retcode,
                    " ".join(arguments),
                    len(output)>40 and (output[:40] + '...') or output))
            if retcode and not ignore_errors:
                raise CommandError(command, retcode, index, output=output)
            results.append(output)
            index = index + 1
        if len(results) == 1:
            return results[0]
        return results

class CommandError(Exception):
    """Exception describing an error in a command."""

    def __init__(self, command, retcode, index=None, output=None):
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
