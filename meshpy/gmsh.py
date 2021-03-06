import logging
logger = logging.getLogger(__name__)


class GmshError(RuntimeError):
    pass


# {{{ tools

def _erase_dir(dir):
    from os import listdir, unlink, rmdir
    from os.path import join
    for name in listdir(dir):
        unlink(join(dir, name))
    rmdir(dir)


class _TempDirManager(object):
    def __init__(self):
        from tempfile import mkdtemp
        self.path = mkdtemp()

    def sub(self, n):
        from os.path import join
        return join(self.path, n)

    def clean_up(self):
        _erase_dir(self.path)

    def error_clean_up(self):
        _erase_dir(self.path)


class LiteralSource(object):
    """
    .. versionadded:: 2014.1
    """
    def __init__(self, source, extension):
        self.source = source
        self.extension = extension


class FileSource(object):
    """
    .. versionadded:: 2014.1
    """
    def __init__(self, filename):
        self.filename = filename


class GmshRunner(object):
    def __init__(self, source, dimensions, order=None,
            incomplete_elements=None, other_options=[],
            extension="geo", gmsh_executable="gmsh"):
        if isinstance(source, str):
            from warnings import warn
            warn("passing a string as 'source' is deprecated--use "
                    "LiteralSource or FileSource",
                    DeprecationWarning)

            source = LiteralSource(source, extension)

        self.source = source
        self.dimensions = dimensions
        self.order = order
        self.incomplete_elements = incomplete_elements
        self.other_options = other_options
        self.gmsh_executable = gmsh_executable

        if dimensions not in [1, 2, 3]:
            raise RuntimeError("dimensions must be one of 1,2,3")

    def __enter__(self):
        self.temp_dir_mgr = None
        temp_dir_mgr = _TempDirManager()
        try:
            working_dir = temp_dir_mgr.path
            from os.path import join, abspath, exists

            if isinstance(self.source, LiteralSource):
                source_file_name = join(
                        working_dir, "temp."+self.source.extension)
                source_file = open(source_file_name, "w")
                try:
                    source_file.write(self.source.source)
                finally:
                    source_file.close()
            elif isinstance(self.source, FileSource):
                source_file_name = abspath(self.source.filename)
                if not exists(source_file_name):
                    raise IOError("'%s' does not exist" % source_file_name)
            else:
                raise RuntimeError("'source' type unrecognized")

            output_file_name = join(working_dir, "output.msh")
            cmdline = [
                    self.gmsh_executable,
                    "-%d" % self.dimensions,
                    "-o", output_file_name,
                    "-nopopup"]

            if self.order is not None:
                cmdline.extend(["-order", str(self.order)])

            if self.incomplete_elements is not None:
                cmdline.extend(["-string",
                    "Mesh.SecondOrderIncomplete = %d;"
                    % int(self.incomplete_elements)])

            cmdline.extend(self.other_options)
            cmdline.append(source_file_name)

            logger.info("invoking gmsh: '%s'" % " ".join(cmdline))
            from pytools.prefork import call_capture_output
            retcode, stdout, stderr = call_capture_output(
                    cmdline, working_dir)
            logger.info("return from gmsh")

            if stderr and "error" in stderr.lower():
                msg = "gmsh execution failed with message:\n\n"
                if stdout:
                    msg += stdout+"\n"
                msg += stderr+"\n"
                raise GmshError(msg)

            if stderr:
                from warnings import warn

                msg = "gmsh issued the following messages:\n\n"
                if stdout:
                    msg += stdout+"\n"
                msg += stderr+"\n"
                warn(msg)

            self.output_file = open(output_file_name, "r")

            self.temp_dir_mgr = temp_dir_mgr
            return self
        except:
            temp_dir_mgr.clean_up()
            raise

    def __exit__(self, type, value, traceback):
        self.output_file.close()
        if self.temp_dir_mgr is not None:
            self.temp_dir_mgr.clean_up()
