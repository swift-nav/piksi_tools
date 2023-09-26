#!/usr/bin/env python

from __future__ import absolute_import, print_function

import sys
import re
import subprocess

import jinja2

from piksi_tools.console.settings_list import SettingsList

settings = SettingsList("settings.yaml")
groups = settings.return_groups()

LATEX_SUBS_MIN = ((re.compile(r'([{}_#%&$])'), r'\\\1'),
                  (re.compile(r'~'), r'\~{}'),
                  (re.compile(r'_'), r'_'),
                  (re.compile(r'"'), r"''"),
                  (re.compile(r'\.\.\.+'), r'\\ldots'),
                  (re.compile(r'\n'), r'\\newline '))


# Note, these reg exps will not replace the '^' character to allow exponents in the units text field
LATEX_SUBS_ALLOW_EXPONENTS = ((re.compile(r'\\'), r'\\textbackslash'),) + LATEX_SUBS_MIN
                              
NO_UNDERSCORE = re.compile(r'_')

# We sometimes need to remove underscores.
# This will remove the latex safe underscore character and replace with a space

def no_us(value):
    newval = value
    try:
        return NO_UNDERSCORE.sub(' ', newval)
    except TypeError:
        pass
    return ''


def escape_tex_exp(value, subs=LATEX_SUBS_ALLOW_EXPONENTS):
    newval = value
    try:
        for pattern, replacement in subs:
            newval = pattern.sub(replacement, newval)
        return newval
    except TypeError:
        pass
    return ''

MAX_NAME_LENGTH = 40

def split_string(input_str, max_len=MAX_NAME_LENGTH):
    if len(input_str) <= max_len:
        return input_str, ''
    
    # Find the index to split the string
    split_index = max_len
    while split_index > 0 and input_str[split_index] not in (' ', '-', '_'):
        split_index -= 1
    
    # If no word boundary found, split at max_len
    if split_index == 0:
        split_index = max_len
    
    # Split the string at the found index
    first_half = input_str[:split_index].strip()
    second_half = input_str[split_index:].strip()
    
    return first_half, second_half

def escape_table_name(value):
    if len(value) > MAX_NAME_LENGTH:
        f, l = split_string(value)
        print((f,l))
        return escape_tex_exp(f) + "- \\newline \\hspace*{5mm} " + escape_tex_exp(l)
    else:
        return escape_tex_exp(value)

def mod(group, groups={}):
    idx = groups.get(group, 0)
    groups[group] = idx + 1
    return idx % 2 != 0

jenv = jinja2.Environment(
    block_start_string='((*',
    block_end_string='*))',
    variable_start_string='(((',
    variable_end_string=')))',
    comment_start_string='((=',
    comment_end_string='=))',
    loader=jinja2.FileSystemLoader("./"))
jenv.filters['escape_tex_exp'] = escape_tex_exp
jenv.filters['escape_table_name'] = escape_table_name
jenv.filters['no_us'] = no_us

latex_template = jenv.get_template('settings_template.tex')

VERSION = sys.argv[1]

with open("settings_out.tex", 'w') as f:
    f.write(
        latex_template.render(
            groups=sorted(groups),
            setting=sorted(settings.list_of_dicts, key=lambda x: repr(x)),
            version=VERSION,
            enumerate=enumerate,
            mod=mod))

subprocess.call(["pdflatex", "--shell-escape", "settings_out.tex"])
