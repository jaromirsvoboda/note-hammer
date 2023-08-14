from setuptools import setup, find_packages

setup(
    name='note-hammer',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
        'beautifulsoup4',
    ],
    entry_points='''
        [console_scripts]
        note-hammer=note_hammer.__main__:cli
    '''
)