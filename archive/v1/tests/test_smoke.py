def test_package_imports() -> None:
    from earn_money import __version__

    assert __version__ == "0.0.1"
