""" Tests for ccapi
"""

import os.path as op

import pytest

from cocalc_api.ccapi import (CCAPI, CCResponseError, CCManyFoundError,
                              CCNoneFoundError)

DATA_DIR = op.join(op.dirname(__file__), 'data')
CONFIG_FNAME = op.join(DATA_DIR, 'eguser.yaml')

cc_api = CCAPI(CONFIG_FNAME)


def test_call_api():
    with pytest.raises(CCResponseError):
        cc_api.call_api('query', {'foo': 1})


def test_invite_collaborator():
    funny_email = 'matthew.brett+cocalc@gmail.com'
    with pytest.raises(ValueError):
        cc_api.invite_collaborator('not-a-project', funny_email,
                                   'subject', 'body')
    with pytest.raises(ValueError):
        cc_api.invite_collaborator('project1', 'not-an-email',
                                   'subject', 'body')
    result = cc_api.invite_collaborator(
        funny_email,
        'project1',
        'Collaborate on project1',
        'Testing email invites')
    assert result['event'] == 'success'


def test_projects_by_title():
    assert cc_api.projects_by_title('not-a-project') == []
    assert (cc_api.projects_by_title('project1') ==
            ['0db4ac94-143c-4638-992a-0835313c73e0'])


def test_search_users():
    assert cc_api.search_users('not-a-user') == []
    ui = cc_api.uinfo
    assert (cc_api.search_users(ui['email']) ==
            [cc_api.account_id])


def test_as_account_id():
    my_id = cc_api.account_id
    assert cc_api.as_account_id(my_id) == my_id
    with pytest.raises(CCManyFoundError):
        cc_api.as_account_id("Matthew Brett")
    with pytest.raises(CCNoneFoundError):
        cc_api.as_account_id("bizarre_email_address@nodomain.baz")


def test_as_project_id():
    p1_id = '0476fa26-8044-4881-9bca-97634857c2f7'
    assert cc_api.as_project_id(p1_id) == p1_id
    with pytest.raises(CCNoneFoundError):
        cc_api.as_project_id("clearly-not-a-real-project99")


def test_get_project_users():
    owner, collabs = cc_api.get_project_users('project1')
    assert owner == cc_api.account_id
    assert set(collabs) == set(
        [cc_api.as_account_id(n) for n in (
            'matthew.brett@gmail.com',
            'matthew.brett+cocalc@gmail.com',
            'm.brett@bham.ac.uk')])
