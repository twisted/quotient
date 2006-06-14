from epsilon import setuphelper

from xquotient import version

setuphelper.autosetup(
    name="Quotient",
    version=version.short(),
    maintainer="Divmod, Inc.",
    maintainer_email="support@divmod.org",
    url="http://divmod.org/trac/wiki/DivmodQuotient",
    license="MIT",
    platforms=["any"],
    description=
        """
        Divmod Quotient is a messaging platform developed as an Offering for
        Divmod Mantissa.
        """,
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Internet"],
    )
