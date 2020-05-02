""" Create / fill / subscribe projects given YaML file
"""

import os.path as op
from time import sleep
from subprocess import check_call
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from glob import glob

import yaml
import pandas as pd

from cocalc.ccapi import CCAPI, NoneFoundError, CocalcError, strip_uuid

CCO = CCAPI()

HERE = op.abspath(op.dirname(__file__))
PROJECT_TEMPLATE_DIR = op.join(HERE, 'ptemplate')
MARKER_FNAME = '.initial_copy_done'
DEFAULT_EMAIL_DOMAIN = 'student.bham.ac.uk'
DEFAULT_UPGRADE = {'cores': 2,
                   'memory': 1000,
                   'mintime': 10800,
                   'network': 1,
                   'member_host': 1}
DEFAULT_DOWNGRADE = {'cores': 0,
                     'memory': 0,
                     'mintime': 0,
                     'network': 0,
                     'member_host': 0}


def read_config(fname):
    with open(fname, 'rt') as fobj:
        return yaml.load(fobj)


def make_project(title, pconfig):
    if pconfig.get('inited', False):
        print(f'Project {title} config has "inited" set')
        return
    existing = CCO.projects_by_title(title)
    if len(existing):
        print('Project already exists')
        return
    desc = f'Project for {title.capitalize()}'
    return CCO.create_project(title, desc, start=True)


def fill_project(title, pconfig):
    if pconfig.get('inited', False):
        print(f'Project {title} config has "inited" set')
        return
    proj_id = CCO.as_project_id(title)
    CCO.start_project(proj_id)
    sleep(5)
    try:
        CCO.project_exec(proj_id, 'ls', timeout=25)
    except CocalcError:
        pass
    r = CCO.project_exec(proj_id, 'ls', ['-a', '-1'])
    assert r['stderr'] == ''
    assert r['exit_code'] == 0
    listing = r['stdout'].splitlines()
    if MARKER_FNAME in listing:
        print('Copy flagged as done, aborting')
        return
    # Copy project files
    ssh_target = f"{proj_id.replace('-', '')}@ssh.cocalc.com:."
    files =glob(op.join(PROJECT_TEMPLATE_DIR, '*'), recursive=True)
    check_call(['scp', '-r'] + files + [ssh_target])
    CCO.text_file_to_project(proj_id, MARKER_FNAME, '')


def subscribe_project(title, config):
    # Collect collaborators and TAs
    listed = config.get('members', [])[:]
    if 'ta' in config:
        listed.append(config['ta'])
    # Add bham.ac.uk to those without @
    listed = [M if '@' in M else f'{M}@{DEFAULT_EMAIL_DOMAIN}' for M in listed]
    # Filter collaborators to those with CoCalc accounts
    accounted = []
    for C in listed:
        try:
            accounted.append(CCO.as_account_id(C))
        except NoneFoundError:
            pass
    # Invite non members.
    CCO.invite_collaborators(accounted,
                             title,
                             f'Invitation to collaborate on {title}',
                             f'''\
You are cordially invited to collaborate on the project {title}
over on CoCalc.com.
''')


def upgrade_project(title, pconfig):
    upgrade = {**DEFAULT_UPGRADE, **pconfig.get('upgrade', {})}
    CCO.project_upgrade(title, **upgrade)


def downgrade_project(title):
    CCO.project_upgrade(title, **DEFAULT_DOWNGRADE)


def nick2title(name):
    return f'team-{name}'


def process_project(action, name, pconfig):
    title = nick2title(name)
    if action == 'create':
        make_project(title, pconfig)
    elif action == 'upgrade':
        upgrade_project(title, pconfig)
    elif action == 'fill':
        fill_project(title, pconfig)
    elif action == 'subscribe':
        subscribe_project(title, pconfig)
    else:
        raise ValueError(f'Action "{action}" not in list')


def check_config(config, class_list=None):
    all_members = set()
    for name, pconfig in config.items():
        members = pconfig['members']
        if len(all_members.intersection(members)):
            raise ValueError(f'Students in {name} overlap with others')
        all_members.update(members)
    all_members = [m.split('@')[0].lower() for m in sorted(all_members)]
    if class_list is None:
        print('No class list; cannot check for missing students')
        return
    df = pd.read_csv(class_list)
    print('Missing students check')
    missing = []
    for i, row in df.iterrows():
        if row['SIS Login ID'] not in all_members:
            missing.append(
                f"{row['Student']} "
                f"<{row['SIS Login ID']}@{DEFAULT_EMAIL_DOMAIN}>")
    print(',\n'.join(missing))


def process_config(action, config):
    for key, value in config.items():
        print(f'Running {action} on {key}')
        process_project(action, key, value)


def echo(config, action):
    if len(config) != 1:
        raise CocalcError('Can only echo data for one project')
    project = list(config)[0]
    if action == 'ssh':
        title = nick2title(project)
        proj_id = CCO.as_project_id(title)
        CCO.start_project(proj_id)
        proj_user = strip_uuid(proj_id)
        return f'ssh {proj_user}@ssh.cocalc.com'
    elif action == 'emails':
        return ', '.join(config[project]['members'])


def get_parser():
    parser = ArgumentParser(description=__doc__,  # Usage from docstring
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('yaml_config',
                        help='YaML configuration for course')
    parser.add_argument('action',
                        help='One of create, fill, subscribe, check')
    parser.add_argument('--class-list',
                        help='Class list CSV file for "check"')
    parser.add_argument('-p', '--project',
                        help='Restrict to given project')
    return parser


def main():
    parser = get_parser()
    args = parser.parse_args()
    config = read_config(args.yaml_config)
    if args.project:
        config = {args.project: config[args.project]}
    if args.action == 'check':
        check_config(config, args.class_list)
        return
    if args.action in ('ssh', 'emails'):
        print(echo(config, args.action))
        return
    process_config(args.action, config)


if __name__ == '__main__':
    main()
