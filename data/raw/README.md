# Official inputs

Extract the complete official D-problem ZIP into this directory, keeping its
subdirectories, original filenames, problem statement, Excel files, DEM and
submission template. Source files are ignored by Git and never modified by the
pipeline. Alternatively, supply the unpacked root as a positional CLI argument.

The six calculation inputs are the node, transport, demand, relay and radio
workbooks plus the 30 m GeoTIFF. The per-question SHA-256 manifest binds outputs
to their exact contents. Multiple matches for an input are rejected explicitly.
