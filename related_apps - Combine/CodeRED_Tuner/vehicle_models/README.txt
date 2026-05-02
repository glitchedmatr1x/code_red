Optional vehicle mesh preview folder.

The Drive 3D tab can load simple OBJ meshes. Put exported meshes here as:
  car01.obj
  truck01.obj

Current Code RED Mesh and Texture Viewer resources appear to support Blender import of CodeX-exported .wfd/.wvd XML, not direct raw .wft rendering inside this standalone Tk app. If CodeX/Code RED exports a vehicle mesh to OBJ, this app can use it immediately.

If no OBJ is present, the simulator builds a fallback car/truck body from the vehsim Size values and wheel metadata.
