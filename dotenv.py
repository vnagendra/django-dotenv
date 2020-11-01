import os
import re
import sys
import warnings


__version__ = '1.4.3'


line_re = re.compile(r"""
    ^
    (?:export\s+)?      # optional export
    ([\w\.]+)           # key
    (?:\s*=\s*|:\s+?)   # separator
    (                   # optional value begin
        '(?:\'|[^'])*'  #   single quoted value
        |               #   or
        "(?:\"|[^"])*"  #   double quoted value
        |               #   or
        [^#\n]+         #   unquoted value
    )?                  # value end
    (?:\s*\#.*)?        # optional comment
    $
""", re.VERBOSE)

variable_re = re.compile(r"""
    (\\)?               # is it escaped with a backslash?
    (\$)                # literal $
    (                   # collect braces with var for sub
        \{?             #   allow brace wrapping
        ([A-Z0-9_]+)    #   match the variable
        \}?             #   closing brace
    )                   # braces end
""", re.IGNORECASE | re.VERBOSE)

overrides = ('source_env', 'source_up')


def read_dotenv(dotenv=None, override=False):
    """
    Read a .env file into os.environ.

    If not given a path to a dotenv path, does filthy magic stack backtracking
    to find manage.py and then find the dotenv.

    If tests rely on .env files, setting the overwrite flag to True is a safe
    way to ensure tests run consistently across all environments.

    :param override: True if values in .env should override system variables.
    """
    if dotenv is None:
        frame_filename = sys._getframe().f_back.f_code.co_filename
        dotenv = os.path.join(os.path.dirname(frame_filename), '.env')

    if os.path.isdir(dotenv) and os.path.isfile(os.path.join(dotenv, '.env')):
        dotenv = os.path.join(dotenv, '.env')

    if os.path.exists(dotenv):
        with open(dotenv) as f:
            env = parse_dotenv(f.read())
            for k, v in env.items():
                if k in overrides:
                    continue
                if override:
                    os.environ[k] = v
                else:
                    os.environ.setdefault(k, v)
            for k, v in env.items():
                if k not in overrides:
                    continue
                for fname in v:
                    read_dotenv(fname, override)
    else:
        warnings.warn("Not reading {0} - it doesn't exist.".format(dotenv),
                      stacklevel=2)


def parse_dotenv(content):
    env = {}

    def replace(variable):
        """Substitute variables in a value either from `os.environ` or
        from previously declared variable that is still in our `env`"""
        for parts in variable_re.findall(variable):
            if parts[0] == '\\':
                # Variable is escaped, don't replace it
                replaced = ''.join(parts[1:-1])
            else:
                # Replace it with the value from the environment
                replacement = os.environ.get(parts[-1])
                if not replacement:
                    replacement = env.get(parts[-1], '')
                replaced = env.get(parts[-1], replacement)
            variable = variable.replace(''.join(parts[0:-1]), replaced)
        return variable

    for line in content.splitlines():
        m1 = line_re.search(line)

        if m1:
            key, value = m1.groups()

            if value is None:
                value = ''

            # Remove leading/trailing whitespace
            value = value.strip()

            # Remove surrounding quotes
            m2 = re.match(r'^([\'"])(.*)\1$', value)

            if m2:
                quotemark, value = m2.groups()
            else:
                quotemark = None

            # Unescape all chars except $ so variables can be escaped properly
            if quotemark == '"':
                value = re.sub(r'\\([^$])', r'\1', value)

            if quotemark != "'":
                value = replace(value)

            env[key] = value

        elif not re.search(r'^\s*(?:#.*)?$', line):  # not comment or blank

            fname = None
            for prefix in overrides:
                if prefix not in line:
                    continue
                fname = line.split(prefix)[-1].strip()
                fname = replace(fname)
                if fname.startswith('~'):
                    fname = os.path.expanduser(fname)
                exists = env.get(prefix)
                if not exists:
                    exists = [fname, ]
                else:
                    exists.append(fname)
                env[prefix] = exists
                break
            if not fname:
                warnings.warn(
                    "Line {0} doesn't match format".format(repr(line)),
                    SyntaxWarning
                )

    return env
