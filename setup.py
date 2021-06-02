from setuptools import find_packages, setup

with open('VERSION.txt') as ff:
    VERSION = ff.read().strip()

INSTALL_REQUIRES = [
    'flask == 1.1.2',
    'gunicorn',
    'datacube',
    'altair',
    'altair_saver',
    'python-dateutil',
    'sentry_sdk',
    'blinker',
    'prometheus-flask-exporter',
    'pywps == 4.2.4'
    'pyarrow'
]

DESCRIPTION = ("datacube-wps is an implementation of the Web Processing Service standard "
               "from the Open Geospatial Consortium.")

KEYWORDS = 'ODC WPS OGC processing'

config = {
    'description': DESCRIPTION,
    'keywords': KEYWORDS,
    'author': 'Digital Earth Australia',
    'license': 'Apache License 2.0',
    'platforms': 'all',
    'url': 'http://www.ga.gov.au/dea',
    'download_url': 'https://github.com/opendatacube/datacube-wps',
    'author_email': 'earth.observation@ga.gov.au',
    'maintainer': 'Digital Earth Australia',
    'maintainer_email': 'earth.observation@ga.gov.au',
    'classifiers': [
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: GIS'
    ],
    'version': VERSION,
    'install_requires': INSTALL_REQUIRES,
    'packages': find_packages(),
    'name': 'datacube-wps'
}

setup(**config)
