# DevIL

Prebuilt MSVC Windows binaries for DevIL 1.8.0 (core `IL` API only - `ILU`/`ILUT`
are not vendored since Falcor's Bitmap loader only needs raw decode), fetched from
the DevIL Windows SDK on SourceForge:
https://sourceforge.net/projects/openil/files/DevIL%20Windows%20SDK/

License: LGPL v2.1 (https://openil.sourceforge.net/download.php).

Used as a faster alternative to FreeImage for decoding Radiance HDR (.hdr) and
OpenEXR (.exr) files - see `image_load_bench/` at the repo root for the
benchmark data that motivated this. `Bitmap::createFromFile` tries DevIL first
for those two extensions and falls back to FreeImage if DevIL fails to load or
doesn't recognize the file (e.g. this particular build lacks compiled-in EXR
support - it reports `IL_INVALID_EXTENSION` for .exr files, so the FreeImage
path is what actually serves EXR loads today; only .hdr benefits from DevIL in
practice).
