# Python Client for the CoCalc API

## Configuration file

To get started you will need your CoCalc *account id* and an API key.

See [the API documentation](https://doc.cocalc.com/api/index.html).

Go to your "Account" tab, "Preferences", and look for "API key"

Put the API into a file in [YaML format](https://yaml.org), like this:

```yaml
# Account settings for CoCalc
first_name: Jane
last_name: Dunne
api_key: an_api_key
email: jane.dunne@yourmail.com
```

## Getting started

```python
from cocalc_api.ccapi import CCAPI

cca = CCAPI('/path/to/config/file.yaml')
print(cca.projects_by_title('my_project)
```

## Installation

```
pip install git+https://github.com/sagemathinc/cocalc-python-api
```

## Running tests

```
git clone https://github.com/sagemathinc/cocalc-python-api
cd cocalc-python-api
pip install -e .
pip install -r test-requirements
pytest cocalc_api
```

