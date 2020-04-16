import os.path
import re
import subprocess

from pytest import UsageError

from pytest_check_mk import MissingFileError
from pytest_check_mk.file_loader import check_module_from_source


def create_check_file_wrapper(name):
    path = os.path.join('checks', name)

    module = check_module_from_source(name, path)
    return CheckFileWrapper(name, module)


class CheckFileWrapper(object):

    def __init__(self, name, module):
        self.name = name
        self.module = module

    @property
    def check_info(self):
        return self.module.check_info

    def __getitem__(self, key):
        return CheckWrapper(self, key)

class CheckWrapper(object):

    def __init__(self, check_file, name):
        __tracebackhide__ = True
        section = name.split('.')[0]

        if not section == check_file.name:
            raise UsageError('Cannot create CheckWrapper for section {} with CheckFileWrapper for section {}'
                             .format(section, check_file.name))

        self.check_file = check_file
        self.name = name
        self.section = section

    @property
    def check_info(self):
        return self.check_file.check_info[self.name]

    @property
    def has_perfdata(self):
        return self.check_info.get('has_perfdata', False)

    @property
    def service_description(self):
        return self.check_info['service_description']

    def parse(self, info):
        __tracebackhide__ = True
        parse_function = self.check_info['parse_function']
        return parse_function(info)

    # inventory / check function ---------------------------------------------
    # Normally, you can't feed the plugin output directly into a check, because
    # the check expects the data as a list of lists + without the fist line (section).
    # This transformation does CheckMK for you.
    # Use this functions to test the inventory/check isolated from a monitoring core.

    def inventory(self, plugin_output):
        __tracebackhide__ = True
        section, info = parse_info(plugin_output.strip())
        if section != self.section:
            raise ValueError('Wrong section name in test data: expected "{}", got "{}"'.format(self.section, section))

        inventory_function = self.check_info['inventory_function']
        return inventory_function(info)

    def check(self, item, params, plugin_output):
        __tracebackhide__ = True
        section, info = parse_info(plugin_output.strip())
        if section != self.section:
            raise ValueError('Wrong section name in test data: expected "{}", got "{}"'.format(self.section, section))

        check_function = self.check_info['check_function']
        result = check_function(item, params, info)
        return self._convert_check_result(result)

    # inventory_mk / check_mk function ---------------------------------------
    # "_mk" = Data are coming from MK
    # Use this functions to test the inventory/check with exactly the same data
    # format which CheckMK hands over to the check (=list of lists).
    # A parse_function is respected, if existing.

    def inventory_mk(self, mk_output):
        '''Use this function to test the inventory with exactly the data which
        are handed over by the CheckMK system.'''
        __tracebackhide__ = True
        if "parse_function" in self.check_info:
            parse_function = self.check_info['parse_function']
            parsed = parse_function(mk_output)
        else:
            parsed = mk_output 
        inventory_function = self.check_info['inventory_function']
        return inventory_function(parsed)

    def check_mk(self, item, params, mk_output):
        __tracebackhide__ = True
        if "parse_function" in self.check_info: 
            parse_function = self.check_info['parse_function']
            parsed = parse_function(mk_output)
        else: 
            parsed = mk_output
        check_function = self.check_info['check_function']
        result = check_function(item, params, parsed)
        return self._convert_check_result(result)

    def _convert_check_result(self, result):
        __tracebackhide__ = True
        # Most of this function is taken from check_mk_base.convert_check_result,
        # minus the snmp support (as this is not supported anyway as of now)
        if type(result) == tuple:
            return result
        else:
            subresults = list(result)
            if len(subresults) == 1:
                return subresults[0]

            perfdata = []
            infotexts = []
            status = 0

            for subresult in subresults:
                st, text = subresult[:2]
                if text is not None:
                    infotexts.append(text + ["", "(!)", "(!!)", "(?)"][st])
                    if st == 2 or status == 2:
                        status = 2
                    else:
                        status = max(status, st)
                if len(subresult) == 3:
                    perfdata += subresult[2]

            return status, ", ".join(infotexts), perfdata


def parse_info(plugin_output):
    __tracebackhide__ = True
    lines = plugin_output.splitlines(True)

    section_name, section_options = parse_header(lines[0].strip())

    try:
        separator = chr(int(section_options['sep']))
    except:
        separator = None

    output = []
    for line in lines[1:]:
        if is_header(line.strip()):
            raise ValueError('Test data contains a second section header: {}'.format(line.strip()))
        if 'nostrip' not in section_options:
            line = line.strip()
        output.append(line.split(separator))

    return section_name, output


def parse_header(header):
    __tracebackhide__ = True

    if not is_header(header):
        raise ValueError('Invalid header in test data: {}'.format(header))

    header_items = header[3:-3].split(':')
    name = header_items[0]
    section_options = {}
    for option in header_items[1:]:
        match = re.match('^([^\(]+)(?:\((.*)\))$', option)
        if match:
            key, value = match.groups()
            section_options[key] = value
        else:
            raise ValueError('Invalid section option {}'.format(option))

    return name, section_options


def is_header(line):
    __tracebackhide__ = True
    return line.strip()[:3] == '<<<' and line.strip()[-3:] == '>>>'


class AgentDirectoryWrapper(object):

    def __getitem__(self, key):
        return AgentWrapper(key)


class AgentWrapper(object):

    def __init__(self, relpath):
        path = os.path.join('agents', relpath)

        if not os.path.exists(path):
            raise MissingFileError(path)

        self.path = path

    def run(self, *extra_args):

        cmd = [self.path] + list(extra_args)

        return subprocess.check_output(cmd)
