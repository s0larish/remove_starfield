from collections.abc import Iterable

from astropy.io import fits
from astropy.wcs import WCS
import numpy as np

def find_collective_bounds(hdrs, wcs_target, trim=(0, 0, 0, 0), key=' '):
    """
    Finds the bounding coordinates for a set of input images.
    
    Calls `find_bounds` for each provided header, and finds the bounding box in
    the output coordinate system that will contain all of the input images.
    
    Parameters
    ----------
    hdrs : Iterable
        Either a list of Headers, or a list of lists of Headers. If the latter,
        ``trim`` can be a list of trim values, one for each of the lists of
        Headers. Instead of Headers, each instance can be the path to a FITS
        file.
    wcs_target : ``astropy.wcs.WCS``
        A WCS object describing an output coordinate system.
    trim : ``tuple`` or ``list``
        How many rows/columns to ignore from the input image. In order,
        (left, right, bottom, top). If ``hdrs`` is a list of lists of Headers,
        this can be (but does not have to be) be a list of tuples of trim
        values, one for each list of Headers.
    hdr_key : ``str``
        The key argument passed to WCS, to select which of a header's
        coordinate systems to use.
    
    Returns
    -------
    bounds : tuple
        The bounding coordinates. In order, (left, right, bottom, top).
    """
    
    if isinstance(hdrs, (fits.header.Header, str)):
        hdrs = [[hdrs]]
    if isinstance(hdrs[0], (fits.header.Header, str)):
        hdrs = [hdrs]
    if not isinstance(trim[0], Iterable):
        trim = [trim] * len(hdrs)
    
    bounds = []
    for h, t in zip(hdrs, trim):
        bounds += [find_bounds(hdr, wcs_target, trim=t, key=key) for hdr in h]
    bounds = np.array(bounds).T
    return (np.min(bounds[0]), np.max(bounds[1]),
            np.min(bounds[2]), np.max(bounds[3]))


def find_bounds(hdr, wcs_target, trim=(0, 0, 0, 0), key=' ',
                world_coord_bounds=None):
    """Finds the pixel bounds of a FITS header in an output WCS.
    
    The edges of the input image are transformed to the coordinate system of
    ``wcs_target``, and the extrema of these transformed coordinates are found.
    In other words, this finds the size of the output image that is required to
    bound the reprojected input image.
    
    Optionally, handles the case that the x axis of the output WCS is periodic
    and the input WCS straddles the wrap point. Two sets of bounds are
    returned, for the two halves of the input WCS.
    
    Parameters
    ----------
    hdr : ``astropy.io.fits.header.Header`` or ``str`` or ``WCS``
        A FITS header describing an input image's size and coordinate system,
        or the path to a FITS file whose header will be loaded, or a WCS
        produced from the FITS header.
    wcs_target : ``astropy.io.fits.header.Header`` or ``astropy.wcs.WCS``
        A WCS object describing an output coordinate system.
    trim : ``tuple``
        How many rows/columns to ignore from the input image. In order,
        ``(left, right, bottom, top)``.
    hdr_key : ``str``
        The key argument passed to WCS, to select which of a header's
        coordinate systems to use.
    world_coord_bounds : ``list``
        Edge pixels of the image that fall outside these world coordinates are
        ignored. Must be a list of four values ``[xmin, xmax, ymin, ymax]``.
        Any value can be ``None`` to not provide a bound.
    
    Returns
    -------
    bounds : list of tuples
        The bounding coordinates. In order, (left, right, bottom, top). One or
        two such tuples are returned, depending on whether the input WCS
        straddles the output's wrap point.
    """
    # Parse inputs
    if isinstance(hdr, WCS):
        wcs = hdr
    elif isinstance(hdr, str):
        with fits.open(hdr) as hdul:
            if hdul[0].data is None:
                hdr = hdul[1].header
            else:
                hdr = hdul[0].header
            wcs = WCS(hdr, hdul, key=key)
    else:
        wcs = WCS(hdr, key=key)
    if not isinstance(wcs_target, WCS):
        wcs_target = WCS(wcs_target)
    
    # Generate pixel coordinates along the edges, accounting for the trim
    # values
    left = 0 + trim[0]
    right = wcs.pixel_shape[0] - trim[1]
    bottom = 0 + trim[2]
    top = wcs.pixel_shape[1] - trim[3]
    xs = np.concatenate((
        np.arange(left, right),
        np.full(top-bottom, right - 1),
        np.arange(right - 1, left - 1, -1),
        np.full(top-bottom, left)))
    ys = np.concatenate((
        np.full(right - left, bottom),
        np.arange(bottom, top),
        np.full(right - left, top - 1),
        np.arange(top - 1, bottom - 1, -1)))
    
    lon, lat = wcs.all_pix2world(xs, ys, 0)
    assert not np.any(np.isnan(lon)) and not np.any(np.isnan(lat))
    
    if world_coord_bounds is not None:
        assert len(world_coord_bounds) == 4
        if world_coord_bounds[0] is None:
            world_coord_bounds[0] = -np.inf
        if world_coord_bounds[2] is None:
            world_coord_bounds[2] = -np.inf
        if world_coord_bounds[1] is None:
            world_coord_bounds[1] = np.inf
        if world_coord_bounds[3] is None:
            world_coord_bounds[3] = np.inf
        f = ( (world_coord_bounds[0] <= lon)
            * (lon <= world_coord_bounds[1])
            * (world_coord_bounds[2] <= lat)
            * (lat <= world_coord_bounds[3]))
        if not np.any(f):
            return None
        lon = lon[f]
        lat = lat[f]
    
    cx, cy = wcs_target.all_world2pix(lon, lat, 0)
    
    return (int(np.floor(np.min(cx))),
            int(np.ceil(np.max(cx))),
            int(np.floor(np.min(cy))),
            int(np.ceil(np.max(cy))))