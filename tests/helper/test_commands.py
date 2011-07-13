try:
    import unittest2 as unittest
except ImportError:
    import unittest
import tempfile
import shutil
import os
import errno

from kitero.helper.commands import Commands, CommandError

class TestCommandsBasic(unittest.TestCase):
    def test_run_one_command(self):
        """Run one command"""
        Commands.run("echo hello")

    def test_output_one_command(self):
        """Run one command and check its output"""
        self.assertEqual(Commands.run("echo hello"), "hello\n")

    def test_run_several_commands(self):
        """Run several commands"""
        Commands.run("echo hello", "echo hi", "echo good bye")

    def test_output_several_commands(self):
        """Run several commands and check their outputs"""
        self.assertEqual(Commands.run("echo hello", "echo hi"),
                         ["hello\n", "hi\n"])

    def test_no_commands(self):
        """Run no command"""
        self.assertEqual(Commands.run(), None)

class TestCommandsExceptions(unittest.TestCase):
    def test_inexistant_command(self):
        """Run an inexistant command"""
        with self.assertRaises(CommandError) as ce:
            Commands.run("i_do_not_exist")
        self.assertEqual(ce.exception.command, "i_do_not_exist")
        self.assertEqual(ce.exception.retcode, errno.ENOENT)
        # Also check that we can build the exception description
        str(ce.exception)

    def test_several_inexistant_commands(self):
        """Run several inexistant command"""
        with self.assertRaises(CommandError) as ce:
            Commands.run("i_do_not_exist", "unknown_command")
        self.assertEqual(ce.exception.command, "i_do_not_exist")
        self.assertEqual(ce.exception.retcode, errno.ENOENT)
        self.assertEqual(ce.exception.index, 0)

    def test_mix_inexistant_commands(self):
        """Run one inexistant command and one regular command"""
        with self.assertRaises(CommandError) as ce:
            Commands.run("echo hello", "unknown_command")
        self.assertEqual(ce.exception.command, "unknown_command")
        self.assertEqual(ce.exception.retcode, errno.ENOENT)
        self.assertEqual(ce.exception.index, 1)
        with self.assertRaises(CommandError) as ce:
            Commands.run("unknown_command", "echo hello")
        self.assertEqual(ce.exception.command, "unknown_command")
        self.assertEqual(ce.exception.retcode, errno.ENOENT)
        self.assertEqual(ce.exception.index, 0)

    def test_command_error(self):
        """Run a regular command returning an error"""
        Commands.run("true")
        with self.assertRaises(CommandError) as ce:
            Commands.run("false")
        self.assertEqual(ce.exception.command, "false")
        self.assertEqual(ce.exception.retcode, 1)

class TestCommandsOrder(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.testfile = os.path.join(self.temp, "testfile.txt")
        f = file(self.testfile, "w")
        f.write("1\n")
        f.close()
        self.commands = []
        for i in range(2, 100):
            self.commands.append("sed -i $a%d %s" % (i, self.testfile))

    def tearDown(self):
        shutil.rmtree(self.temp)
        
    def test_command_orders(self):
        """Run commands in a specific order"""
        Commands.run(*self.commands)
        self.assertEqual(file(self.testfile).read(),
                         "".join("%d\n" % i for i in range(1, 100)))

    def test_command_orders_with_errors(self):
        """Run commands in a specific order with one command return an error"""
        self.commands.insert(30, "false")
        with self.assertRaises(CommandError):
            Commands.run(*self.commands)
        self.assertEqual(file(self.testfile).read(),
                         "".join("%d\n" % i for i in range(1, 32)))

class TestCommandsWithVariables(unittest.TestCase):
    def test_one_variable(self):
        """Test a command using one variable"""
        self.assertEqual(Commands.run("echo %(var)s", var="hello"), "hello\n")

    def test_several_variables(self):
        """Test a command using several variables"""
        self.assertEqual(Commands.run("echo %(var1)s %(var2)s",
                                      var1="hello1", var2="hello2"),
                         "hello1 hello2\n")

    def test_several_commands(self):
        """Test several commands using variables"""
        self.assertEqual(Commands.run("echo %(var1)s %(var2)s",
                                      "echo %(var1)s %(var3)s",
                                      "echo bye",
                                      var1="hello1", var2="hello2", var3="hello3"),
                         ["hello1 hello2\n", "hello1 hello3\n", "bye\n"])
