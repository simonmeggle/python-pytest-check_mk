import imp
import os
from string import Template
from pytest_check_mk import MissingFileError


_HEADER = '''
import sys, os, time, socket

def regex(r):
    __tracebackhide__ = True
    import re

    try:
        rx = re.compile(r)
    except Exception as e:
        raise AssertionError("Invalid regular expression '%s': %s" % (r, e))
    return rx


# The following data structures will be filled by the checks
check_info                         = {} # all known checks
checkgroup_of                      = {} # groups of checks with compatible parametration
check_includes                     = {} # library files needed by checks
precompile_params                  = {} # optional functions for parameter precompilation, look at df for an example
check_default_levels               = {} # dictionary-configured checks declare their default level variables here
factory_settings                   = {} # factory settings for dictionary-configured checks
check_config_variables             = [] # variables (names) in checks/* needed for check itself
snmp_info                          = {} # whichs OIDs to fetch for which check (for tabular information)
snmp_scan_functions                = {} # SNMP autodetection
active_check_info                  = {} # definitions of active "legacy" checks
special_agent_info                 = {}

'''

# E.g. host_extra_conf_merged is a WATO function which is only available when the 
# check is run in MK's context. The same applies to the inventory rules etc. 
# We can monkeypatch these data in our test file only when they are present; monkey-
# patch cannot create new data. 

# The following code gets appended to the module. All runtime relevant data and 
# functions must be initialised here.
# Example (file: test_foobar.py): 
# mock_inventory_foobar_rules = [ ...(rules) ...]
# monkeypatch.setattr(checks.module, "inventory_foobar_rules", mock_inventory_foobar_rules)

WATO_DATA = Template('''
# function to retrieve host relevant config
def host_extra_conf_merged(self):
    pass

# WATO rules
inventory_${name}_rules = { }

def host_name():
    return "localhost"
''')


def check_module_from_source(name, path):
    __tracebackhide__ = True

    if not os.path.exists(path):
        raise MissingFileError(path)

    source = open(path, 'r').read() + WATO_DATA.substitute({
        'name': name
    })
    code = compile(source, path, 'exec')
    module = imp.new_module(name)

    exec(_HEADER, module.__dict__)
    exec(code, module.__dict__)

    return module
