from setuptools import setup, find_packages

setup(
    name="price-tracker",
    version="1.0.0",
    description="Modular & Domain-Agnostic Price Tracking & Assembly Optimization Engine",
    author="Alessandro",
    packages=find_packages(),
    install_requires=[
        "requests>=2.28.0",
        "beautifulsoup4>=4.11.0",
    ],
    entry_points={
        "console_scripts": [
            "price-tracker=price_tracker.cli:main",
        ],
    },
)
