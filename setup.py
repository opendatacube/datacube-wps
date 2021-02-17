from setuptools import setup, find_packages

with open('VERSION.txt') as ff:
    VERSION = ff.read().strip()

INSTALL_REQUIRES = [
    'automat >= 0.3.0',
    'flask',
    'scikit-image',
    'gunicorn',
    'rasterio >= 1.0.9',
    'rasterio[s3]',
    'altair',
    'selenium',
    'python-dateutil',
    'sentry_sdk',
    'blinker',
    'pywps == 4.2.4'
]

DESCRIPTION = ("datacube-wps is an implementation of the Web Processing Service standard "
               "from the Open Geospatial Consortium.")

KEYWORDS = 'ODC WPS OGC processing'

config = {
    'description': DESCRIPTION,
    'keywords': KEYWORDS,
    'author': 'Digital Earth Australia',
    'license': 'MIT',
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
        'License :: OSI Approved :: MIT License',
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
