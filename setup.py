from setuptools import setup

setup(
    name='dath',
    version='0.1',
    install_requires=[
        'spacy==3.7.2',
    ],
    scripts=[
        'scripts/download_model.sh'
    ]
)

