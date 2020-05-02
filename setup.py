from setuptools import setup

from cocalc_api import __version__

# Get install requirements from requirements.txt file
with open('requirements.txt', 'rt') as fobj:
    install_requires = [line.strip() for line in fobj
                        if line.strip() and not line[0] in '#-']
# Get any extra test requirements
with open('test-requirements.txt', 'rt') as fobj:
    test_requires = [line.strip() for line in fobj
                     if line.strip() and not line[0] in '#-']

setup(name='cocalc_api',
      version=__version__,
      description='Client for the CoCalc API',
      url='https://github.com/sagemathinc/cocalc-python-api',
      author_email='office@sagemath.com',
      license='Apache 2.0',
      packages=['cocalc_api', 'cocalc_api.tests'],
      package_data = {'cocalc_api': [
          'tests/data/*',
      ]},
      long_description = open('README.md', 'rt').read(),
      long_description_content_type='text/markdown',
      install_requires = install_requires,
      # For pip versions >= 9
      python_requires = '>=3.6',
      extras_require = {'test': test_requires},
      zip_safe=False)
