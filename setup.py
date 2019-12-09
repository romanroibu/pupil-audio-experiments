from setuptools import setup, find_packages


requirements = [
    "numpy",
    "av>=0.4.3",
    "pyaudio",
]


packages = find_packages(".")


if __name__ == "__main__":
    setup(
        name="pupil_audio",
        version="0.1",
        packages=packages,
        install_requires=requirements,
        license="GNU",
        author="Pupil Labs",
        author_email="info@pupil-labs.com",
        url="https://github.com/pupil-labs/pupil-audio",
    )
