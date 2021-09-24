# meshpy

This is a 3D mesh processing library, courtesty of
the Berkeley AutoLab and Jeff Mahler.

To run unit tests, from the top level directory simply run
```bash
python -m unittest discover
```

## Updates for Python 3
_(CBT, 09/24/2021)_
1. Fixed all relative imports to add "." prefix
2. Fixed map functions to return lists rather than map objects (python 3 returns map objects by default rather than lists)
3. Updated print statements to python 3 syntax
4. Updated calls to python's _Queue_ package, which is lowercase in python 3
5. Fixed an issue with calls to python's _sys.maxint_ value, which no longer exists in python 3  
6. Disabled _mesh_renderer_, _random_variables_, and _image_converter_  modules due to broken dependencies with BerkeleyAutomation's [autolab_core](https://github.com/BerkeleyAutomation/autolab_core) and [perception](https://github.com/BerkeleyAutomation/perception) packages. These packages were recently updated to python 3, dropping all support for versions less than python 3.6. They also appear to have changed syntax or workflow enough to break the _BinaryImage_ and _CameraIntrinsics_ classes. (_Note: will work on fixing this sometime soon_)
