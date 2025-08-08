from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in webshop_categories_api/__init__.py
from webshop_categories_api import __version__ as version

setup(
	name="webshop_categories_api",
	version=version,
	description="Enhanced API endpoints for webshop categories with images",
	author="Your Company",
	author_email="your.email@company.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)