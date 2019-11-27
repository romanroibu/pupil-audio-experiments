from setuptools import setup


requirements = [
    "numpy",
    "av>=0.4.3",
    "pyaudio",
]


package = "pupil_audio"


if __name__ == "__main__":
    setup(
        name="pupil_audio",
        version="0.1",
        packages=[package],
        install_requires=requirements,
        license="GNU",
        author="Pupil Labs",
        author_email="info@pupil-labs.com",
        url="https://github.com/pupil-labs/pupil-audio"
    )
