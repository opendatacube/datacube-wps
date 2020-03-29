"""
"""
def resolve_nodata(src, band, fallback=None, override=None):
    """Figure out what value to use for nodata given a band and fallback/override
    settings
    """
    if override is not None:
        return override

    band0 = band if isinstance(band, int) else band[0]
    nodata = src.nodatavals[band0 - 1]

    if nodata is None:
        return fallback

    return nodata
