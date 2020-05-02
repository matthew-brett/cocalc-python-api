""" Utilities for using CoCalc via the API

Refs:

* https://doc.cocalc.com/api/index.html
* https://doc.cocalc.com/api/query.html
* https://share.cocalc.com/share/65f06a34-6690-407d-b95c-f51bbd5ee810/Public/README.md
* https://github.com/sagemathinc/cocalc/blob/master/src/smc-util/db-schema/db-schema.ts

User configuration should be of form::

    # My credentials for CoCalc queries, etc.
    first_name: Matthew
    last_name:  Brett
    api_key:    ab_etcetcetc
    email: matthew.brett@gmail.com
"""

import json
import pprint
import re
import uuid
from time import sleep

import requests
from requests.auth import HTTPBasicAuth
import yaml

# Inspired by https://stackoverflow.com/a/18359032/1939576
UUID_RE = re.compile('[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z', re.I)

pp = pprint.PrettyPrinter()


class CocalcError(ValueError):
    """ Error from CoCalc """


class CCNoneFoundError(CocalcError):
    """ Error when no items found in search """


class CCManyFoundError(CocalcError):
    """ Error when more than one item found in search """


class CCResponseError(CocalcError):
    """ Error for unexpected CoCalc response """


class TimeoutError(CocalcError):
    """ Error for project timing out """


def make_uuid():
    return str(uuid.uuid1())


def strip_uuid(in_uuid):
    return in_uuid.replace('-', '')


class CCAPI:
    base_url = 'https://cocalc.com'

    def __init__(self, uinfo, verbose=True):
        """ Initialize CCAPI object.

        Parameters
        ----------
        uuinfo : dict or str
            Dictionary containing user configuration, or filename with YaML
            file containing configuration.
        verbose : {True, False}, optional
            If True, print verbose messages.
        """
        if isinstance(uinfo, str):
            uinfo = self.load_user_info(uinfo)
        self.uinfo = uinfo
        self.verbose=verbose
        self._account_id = None

    def load_user_info(self, fname):
        r"""Load user information

        Input file should be of form

            first_name: Jane
            last_name: Doe
            api_key: sk_sda89swelekd8x0JJ83lGSwl
            email: my_email@somehost.org

        returns dict of user info settings.
        """
        with open(fname,"r") as inf:
            user_info = yaml.load(inf)
        return user_info

    @property
    def account_id(self):
        if self._account_id is not None:
            return self._account_id
        payload = {"query": {"accounts": {"account_id":None}}}
        response = self.call_api("query", payload)
        self._account_id = response['query']['accounts']['account_id']
        return self._account_id

    def call_api(self,
                 msg,
                 payload=None,
                 sk=None,
                 base_url=None,
                 max_retries=3,
                 timeout=4):
        r""" Generic API call with retries

        Parameters
        ----------
        msg : str
            String message type: "create_account", "create_project", etc.
        payload : None or dict, optional
            Dict of parameters for the call
        sk : None or str, optional
            Security key
        base_url : str or None, optional
            Base URL for query API
        max_retries: int, optional
            Maximum number of retries on post.
        timeout : int, optional
            Timeout in seconds

        Returns
        -------
        response : dict
            API response object
        """
        payload = {} if payload is None else payload
        sk = self.uinfo['api_key'] if sk is None else sk
        base_url = self.base_url if base_url is None else base_url
        s = requests.Session()
        a = requests.adapters.HTTPAdapter(max_retries=max_retries)
        s.mount('https://', a)
        url = f"{base_url}/api/v1/{msg}"
        auth = HTTPBasicAuth(sk, '')
        headers = {'content-type': 'application/json'}
        r = s.post(url, auth=auth,
                   data=json.dumps(payload),
                   headers=headers,
                   timeout=timeout)
        out = r.json()
        if r.status_code != requests.codes.ok:
            raise CCResponseError(
                f"Bad status code {r.status_code} with call:\n{payload}\n"
                f"giving result:\n{out}")
        return out

    def projects_by_title(self, title, only_recent=False):
        """ Search for projects by project `title`

        Parameters
        ----------
        title : str
            Project title
        only_recent : {False, True}, optional
            If True, make faster query to look only in 20 most recent projects.

        Returns
        -------
        project_ids : list
            UUIDs of matching projects
        """
        q_str = 'projects' if only_recent else 'projects_all'
        payload = {"query":{q_str:[
            {"project_id": None, "title": title, "description": None}]}}
        response = self.call_api("query", payload)
        return [r['project_id'] for r in response['query'][q_str]]

    def touch_project(self, projectish):
        # https://doc.cocalc.com/api/touch_project.html
        project_id = self.as_project_id(projectish)
        rid = make_uuid()
        response = self.call_api('touch_project',
                                 {'id': rid, 'project_id': project_id})
        return response['event']

    def start_project(self, projectish, wait=5, retries=10):
        project_id = self.as_project_id(projectish)
        for i in range(retries):
            try:
                self.project_exec(project_id, 'date')
            except CocalcError:
                sleep(wait)
                continue
            break
        else:
            raise TimeoutError(f'Could not wake {projectish}')
        r = self.project_exec(project_id, 'date')
        assert r['exit_code'] == 0

    def create_project(self, title, description, start=False):
        """ Create project with `title` and `description`, return `project_id`

        Return existing project_id if project with matching title already
        exists, but raise for more than one project.

        Parameters
        ----------
        title : str
            Title of project - e.g. "team-wildcard"
        description : str
            Description of project.
        start : {False, True}, optional
            Whether to start the project.

        Returns
        -------
        project_id : str
            UUID for project - e.g. ``95c42722-231c-473b-b344-6f7f4b3aff48``

        Raises
        ------
        CCManyFoundError
            If we found more than one existing project with matching title.
        """
        try:
            project_id = self.as_project_id(title)
        except CCNoneFoundError:
            pass
        else:
            if self.verbose:
                print(f'Found {project_id} with title "{title}"')
                print("Skipping project creation")
            return project_id

        # Create the project
        if self.verbose:
            print(f"Creating project {title}")
        payload = {'title': title, 'description': description,
                   'start': start}
        response = self.call_api('create_project', payload)
        if self.verbose:
            pp.pprint(response)
        return response['project_id']

    def search_users(self, user_str):
        """ Search for user with string `user_str`
        """
        # https://doc.cocalc.com/api/user_search.html
        payload = {'query': user_str}
        response = self.call_api("user_search", payload)
        return [r['account_id'] for r in response['results']]

    def likely_uuid(self, in_str):
        """ True if `in_str` is likely to be a UUID
        """
        return UUID_RE.match(in_str)

    def _check_id(self, in_id, of_type, check_func):
        if self.likely_uuid(in_id):
            return in_id
        found = check_func(in_id)
        if not found:
            raise CCNoneFoundError(f'No matching {of_type} for {in_id}')
        if len(found) > 1:
            raise CCManyFoundError(
                f'More than one matching {of_type} for {in_id}')
        return found[0]

    def as_account_id(self, accountish):
        """ Return account_id for `accountish`

        `accountish` can be a UUID, in which case we return it without further
        ado; we assume it is in fact an account_id.  Otherwise we search for
        the account, and return if we find it, raising suitable errors
        otherwise.
        """
        return self._check_id(accountish, 'user', self.search_users)

    def as_project_id(self, projectish):
        """ Return project_id for `projectish`

        `projectish` can be a UUID, in which case we return it without further
        ado; we assume it is in fact a project_id.  Otherwise we search for the
        project, and return if we find it, raising suitable errors otherwise.
        """
        return self._check_id(projectish, 'project', self.projects_by_title)

    def invite_collaborator(self,
                            collaboratorish,
                            projectish,
                            subject,
                            email_body,
                            replyto=None,
                            replyto_name=None,
                           ):
        """ Invite `collaborator` to project project `project_id`
        """
        # https://doc.cocalc.com/api/invite_collaborator.html
        collaborator_id = self.as_account_id(collaboratorish)
        project_id = self.as_project_id(projectish)
        ui = self.uinfo
        replyto = ui['email'] if replyto is None else replyto
        replyto_name = (f"{ui['first_name']} {ui['last_name']}"
                        if replyto_name is None else replyto_name)
        payload = dict(account_id=collaborator_id,
                       project_id=project_id,
                       subject=subject,
                       email=email_body,
                       replyto=replyto,
                       replyto_name=replyto_name)
        return self.call_api('invite_collaborator', payload)

    def get_project_users(self, projectish):
        project_id = self.as_project_id(projectish)
        payload = {"query": {"projects": {"project_id": project_id,
                                          "users": None}}}
        response = self.call_api('query', payload)
        collaborators = []
        owner = None
        for user_id, info_d in response['query']['projects']['users'].items():
            group = info_d['group']
            if group == 'collaborator':
                collaborators += [user_id]
            elif group == 'owner':
                assert owner is None  # Can only be one owner
                owner = user_id
            else:
                raise ValueError(f'Unknown user type {group}')
        return owner, collaborators

    def invite_collaborators(self,
                             collaborators,
                             projectish,
                             subject,
                             email_body,
                             replyto=None,
                             replyto_name=None,
                            ):
        """ Invite `collaborators` not already on project `projectish`
        """
        project_id = self.as_project_id(projectish)
        collaborator_ids = [self.as_account_id(cid) for cid in collaborators]
        p_owner, p_collaborators = self.get_project_users(project_id)
        already = set(p_collaborators + [p_owner])
        for cid in collaborator_ids:
            if cid not in already:
                self.invite_collaborator(cid, project_id,
                                         subject,
                                         email_body,
                                         replyto=replyto,
                                         replyto_name=replyto_name,
                                        )

    def project_exec(self, projectish,
                     command,
                     args = (),
                     cwd='',
                     timeout=10,
                     bash=False,
                     err_on_exit=False,
                    ):
        """ Execute command on project `projectish`

        See: https://doc.cocalc.com/api/project_exec.html
        """
        payload = {'id': make_uuid(),
                   'project_id': self.as_project_id(projectish),
                   'path': cwd,
                   'command': command,
                   'timeout': timeout,
                   'args': list(args),
                   'bash': bash,
                   'err_on_exit': err_on_exit,
                  }
        response = self.call_api('project_exec', payload)
        if response['event'] == 'error':
            raise CocalcError(
                f'{command} failed on {projectish} with response\n{response}')
        return response

    def text_file_to_project(self, projectish, path, content):
        payload = {'id': make_uuid(),
                   'project_id': self.as_project_id(projectish),
                   'path': path,
                   'content': content}
        response = self.call_api('write_text_file_to_project', payload)
        if response['event'] == 'error':
            raise CocalcError(
                f'Write to {path} failed on {projectish} with '
                f'response\n{response}')
        return response

    def project_upgrade(self,
                        projectish,
                        accountish=None,
                        **kwargs):
        r""" Upgrade project `projectish` with given settings

        Parameters
        ----------
        projectish : str
            Project ID UUID or project title.
        accountish : None or str, optional
            Account ID UUID or email or name of account giving the upgrade.  If
            None, assume account id from `self.uinfo`.
        \*\*kwargs : dict
            Settings to change in upgrade (see Notes below).

        Returns
        -------
        r : dict
            CoCalc response dict

        Raises
        ------
        CocalcError
            If error from attempt to update settings

        Notes
        -----
        Key / example values for `kwargs`::

            'cores': 1,
            'memory': 1000,
            'mintime': 10800,
            'network': 1,
            'cpu_shares': 0,
            'disk_quota': 0,
            'member_host': 1,
            'ephemeral_disk': 0,
            'memory_request': 0,
            'ephemeral_state': 0

        See: https://doc.cocalc.com/api/query.html#examples-of-set-query
        """
        proj_id = self.as_project_id(projectish)
        account_id = (self.account_id if accountish is None
                      else self.as_account_id(accountish))
        r = self.call_api('query',
                          {'query':
                           {'projects':
                            {'project_id': proj_id,
                             'users':
                             {account_id:
                              {'upgrades': kwargs}
                             }
                            }
                           }
                          })
        if r['event'] == 'error':
            raise CocalcError(
                f'Failed upgrade to {projectish} with response\n{r}')
        return r
