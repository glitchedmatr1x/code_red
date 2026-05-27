
# Generated:  ##timemarker##

import bpy
import os
import sys
import importlib
from bpy.props import *


from bpy_extras.io_utils import (
        ImportHelper,
        )

from bpy.types import (
        Operator,
        OperatorFileListElement,
        )

import guibase
import nrblendimp
import nrfile
import nrtools



# blender <  2.8 gui0.py @@@ -> =
# blender >= 2.8 gui1.py @@@ -> :

class IMPORT_MESH_OT_nr(bpy.types.Operator, ImportHelper, guibase.BaseGui):

    bl_idname = "import_mesh.nr"
    bl_label  = "Import Ninja Ripper 2"
    filename_ext = ".nr"

    filter_glob @@@ StringProperty(name="*.nr", default="*.nr",options={'HIDDEN'},)
    files       @@@ CollectionProperty(name="File Path", type=bpy.types.OperatorFileListElement,)
    directory   @@@ StringProperty(maxlen=1024, subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'},)
    projTab     @@@ EnumProperty(name="Geometry parameters",
                                 default = 'MANUAL',
                                 description="Reverse projection parameters",
                                 items=[('MANUAL',  "Manual", "Manual parameters of projection transform"),
                                        ('PROJMAT', "Matrix", "Exact projection matrix (from ripper log)"),
                                       ],
                                )
    scrWidth         @@@ FloatProperty(name="Screen width", description="Screen width in pixels", default=1024.0, min=1.0,)
    scrHeight        @@@ FloatProperty(name="Screen height", description="Screen height in pixels", default=768.0, min=1.0,)
    fov              @@@ FloatProperty(name="FOV_Y (degrees)", description="Field of view (horizontal) in degrees", default=45.0, min=0.0, max=180.0,)
    nearDist         @@@ FloatProperty(name="Near", description="Near clip distance", default=0.01, min=0.0,)
    farDist          @@@ FloatProperty(name="Far", description="Far clip distance", default=1000.0, min=1.0,)
    exactProjMat     @@@ StringProperty(name="", maxlen=1024, default="[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0],[0, 0, 0, 1]]", description="Projection matrix (4x4) in Python format",)
    transposeProjMat @@@ BoolProperty(name="Transpose", description="Transpose matrix before using", default = False,)
    texturingTab     @@@ EnumProperty(name="Texturing parameters",
                                      description="Texturing params",
                                      default = 'AUTO',
                                      items=[('AUTO', "Auto", "Auto texture coordinates"),
                                             ('TEXCOORDBYNAME', "TexCoord by name", "Manual TEXCOORD name"),
                                             ('SCATTERTEXCOORD', "TexCoord in multi attributes", "TexCoord in multi attributes"),
                                             ('EXTRA_TEXCOORDBYNAME', "TexCoord by name from PreVS (T-Pose)", "Manual TEXCOORD name from PreVS (T-Pose)"),
                                             ('EXTRA_SCATTERTEXCOORD', "TexCoord in multi attributes from PreVS (T-Pose)", "TexCoord in multi attributes PreVS (T-Pose)"),
                                            ],
                                      )
    # Tex coords in single attribute with name + component idx
    texCoordAttribName @@@ StringProperty(name="TexCoord Attribute Name", maxlen=128, default="TEXCOORD", description="Texture coordinates attribute name",)
    texUvComponentIdx  @@@ IntVectorProperty(name="Texture U/V comp idx", description="Texture U/V component index (0...3)", default=(0,1), size=2,min=0,max=3,)
    # Tex coords in multiple attribs/component idx
    texScatterU        @@@ IntVectorProperty(name="TexU attrib idx/comp idx", description="U attrib idx/comp idx", default=(1,0), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    texScatterV        @@@ IntVectorProperty(name="TexV attrib idx/comp idx", description="V attrib idx/comp idx", default=(1,1), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    # Scene import options
    ignoreDepthEnableFalse         @@@ BoolProperty(name="Ignore HUD, 2D elements", description="Ignore DepthEnable==False (usually HUD, 2D elements)", default=False,)
    ignoreDepthWriteEnableFalse    @@@ BoolProperty(name="Ignore Skybox", description="Ignore DepthWriteEnable==False (usually skybox)", default=False,)
    ignoreRGBWriteDisabled         @@@ BoolProperty(name="Ignore if color write is disabled", description="Ignore if color write is disabled (usually z-prepass)", default=False,)
    ignoreIfRenderedToRenderTarget @@@ BoolProperty(name="Ignore if rendered to rendertarget", description="Ignore if rendered to rendertarget", default=False,)
    ignoreIfRenderedToBackBuffer   @@@ BoolProperty(name="Ignore if rendered to backbuffer", description="Ignore if rendered to backbuffer", default=False,)
    ignoreIfRenderTargetWidthDoesNotMatchToBackBuffer @@@ BoolProperty(name="Ignore if rendertarget width does not match to backbuffer", description="Ignore if rendertarget width does not match to backbuffer", default=False,)
    # Manual normals
    normalsTab         @@@ EnumProperty(name="Normal vectors",
                                        description="Normal vectors",
                                        default = 'AUTO',
                                        items=[('AUTO',     "Auto", "Auto"),
                                              ('DISABLED', "Don't assign normal vectors", "Don't assign normal vectors"),
                                              ('MANUAL',   "Manual parameters", "Manual parameters"),
                                             ],
                                        )
    normalAttrCompX    @@@ IntVectorProperty(name="Normal.X attrib idx/comp idx", description="Normal.X attrib idx/comp idx", default=(1,0), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    normalAttrCompY    @@@ IntVectorProperty(name="Normal.Y attrib idx/comp idx", description="Normal.Y attrib idx/comp idx", default=(1,1), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    normalAttrCompZ    @@@ IntVectorProperty(name="Normal.Z attrib idx/comp idx", description="Normal.Z attrib idx/comp idx", default=(1,2), size=2,min=0,max=128, update=guibase.update_funcPostVs,)

    def invoke(self, context, event):
        nrOutDir = nrtools.getNrOutputDir()
        if nrOutDir:
            self.directory = nrOutDir + "/"
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}





class IMPORT_MESH_OT_nr_prevs(bpy.types.Operator, ImportHelper, guibase.BaseGuiPreVs):

    bl_idname = "import_mesh_prevs.nr"
    bl_label  = "Import Ninja Ripper 2"
    filename_ext = ".nr"

    filter_glob     @@@ StringProperty(name="*.nr", default="*.nr",options={'HIDDEN'},)
    files           @@@ CollectionProperty(name="File Path", type=bpy.types.OperatorFileListElement,)
    directory       @@@ StringProperty(maxlen=1024, subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'},)
    vertexLayoutTab @@@ EnumProperty(name="Vertex Layout",
                                     description="Vertex layout parameters",
                                     default = 'AUTO',
                                     items=[('AUTO', "Auto", "Position idx=(0,1,2). TexCoord by name=TEXCOORD. idx=(0,1)"),
                                            ('MANUAL', "Manual", "Manual vertex layout settings"),
                                           ],
                                    )

    texturingTab    @@@ EnumProperty(name="Texturing parameters",
                                     description="Texturing params",
                                     default = 'AUTO',
                                     items=[('AUTO',           "Auto", "Auto texture coordinates"),
                                            ('TEXCOORDBYNAME', "TexCoord by name", "Manual TEXCOORD name"),
                                            ('SCATTERTEXCOORD', "TexCoord in multi attributes", "TexCoord in multi attributes"),
                                            ('EXTRA_TEXCOORDBYNAME', "TexCoord by name from post vs (World)", "Manual TEXCOORD name from post vs (World)"),
                                            ('EXTRA_SCATTERTEXCOORD', "TexCoord in multi attributes from post vs (World)", "TexCoord in multi attributes post vs (World)"),
                                           ],
                                     )
    posX               @@@ IntVectorProperty(name="PosX attrib idx/comp idx", description="Position X", default=(0,0), size=2,min=0,max=128, update=guibase.update_funcPreVs,)
    posY               @@@ IntVectorProperty(name="PosY attrib idx/comp idx", description="Position Y", default=(0,1), size=2,min=0,max=128, update=guibase.update_funcPreVs,)
    posZ               @@@ IntVectorProperty(name="PosZ attrib idx/comp idx", description="Position Z", default=(0,2), size=2,min=0,max=128, update=guibase.update_funcPreVs,)
    texScatterU        @@@ IntVectorProperty(name="TexU attrib idx/comp idx", description="U attrib idx/comp idx", default=(1,0), size=2,min=0,max=128, update=guibase.update_funcPreVs,)
    texScatterV        @@@ IntVectorProperty(name="TexV attrib idx/comp idx", description="V attrib idx/comp idx", default=(1,1), size=2,min=0,max=128, update=guibase.update_funcPreVs,)
    texCoordAttribName @@@ StringProperty(name="TexCoord Attribute Name", maxlen=128, default="TEXCOORD", description="Texture coordinates attribute name",)
    texUvComponentIdx  @@@ IntVectorProperty(name="Texture U/V comp idx", description="Texture U/V component index (0...3)", default=(0,1), size=2,min=0,max=3,)
    # Manual normals
    normalsTab         @@@ EnumProperty(name="Normal vectors",
                                        description="Normal vectors",
                                        default = 'AUTO',
                                        items=[('AUTO',     "Auto", "Auto"),
                                              ('DISABLED', "Don't assign normal vectors", "Don't assign normal vectors"),
                                              ('MANUAL',   "Manual parameters", "Manual parameters"),
                                             ],
                                        )
    normalAttrCompX    @@@ IntVectorProperty(name="Normal.X attrib idx/comp idx", description="Normal.X attrib idx/comp idx", default=(1,0), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    normalAttrCompY    @@@ IntVectorProperty(name="Normal.Y attrib idx/comp idx", description="Normal.Y attrib idx/comp idx", default=(1,1), size=2,min=0,max=128, update=guibase.update_funcPostVs,)
    normalAttrCompZ    @@@ IntVectorProperty(name="Normal.Z attrib idx/comp idx", description="Normal.Z attrib idx/comp idx", default=(1,2), size=2,min=0,max=128, update=guibase.update_funcPostVs,)


    def invoke(self, context, event):
        nrOutDir = nrtools.getNrOutputDir()
        if nrOutDir:
            self.directory = nrOutDir + "/"
        wm = context.window_manager
        wm.fileselect_add(self)
        return {'RUNNING_MODAL'}
