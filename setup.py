try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

with open('VERSION.txt') as ff:
    VERSION = ff.read().strip()

with open('requirements.txt') as f:
    INSTALL_REQUIRES = f.read().splitlines()[:-1]
    INSTALL_REQUIRES.append('pywps=='+VERSION)

DESCRIPTION = (
'''PyWPS is an implementation of the Web Processing Service standard from the
Open Geospatial Consortium. PyWPS is written in Python.
PyWPS-Flask is an example service using the PyWPS server, distributed along 
with a basic set of sample processes and sample configuration file. It's 
usually used for testing and development purposes.
''')

KEYWORDS = 'PyWPS WPS OGC processing'

config = {
    'description': DESCRIPTION,
    'keywords': KEYWORDS,
    'author': 'PyWPS PSC',
    'license': 'MIT',
    'platforms': 'all',
    'url': 'http://pywps.org',
    'download_url': 'https://github.com/lazaa32/pywps-flask',
    'author_email': 'luis.a.de.sousa@gmail.com',
    'maintainer': 'Luis de Sousa',
    'maintainer_email': 'luis.de.sousa@protonmail.ch',
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    'version': VERSION,
    'install_requires': INSTALL_REQUIRES,
    'dependency_links': [
        'git+https://github.com/geopython/pywps.git@pywps-'+VERSION+'#egg=pywps-'+VERSION
     ],
    'packages': ['processes', 'tests'],
    'scripts': ['demo.py'],
    'name': 'pywps-flask'
}

setup(**config)
