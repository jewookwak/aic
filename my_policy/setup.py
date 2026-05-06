from setuptools import find_packages, setup

package_name = "my_policy"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Your Name",
    maintainer_email="your@email.com",
    description="My custom policy for the AIC challenge",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "train_tqc = my_policy.train_tqc:main",
        ],
    },
)
