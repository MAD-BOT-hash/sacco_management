from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="sacco_management",
    version="1.0.0",
    description="Complete SACCO Management System for ERPNext",
    author="SACCO Developer",
    author_email="developer@sacco.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires
)
