
import os
import sys
import struct
import math

import nrfile

# blender on mac doesn't have winreg
def _getOutDir(reg_path):
    try:
        import winreg
        try:
            registry_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_READ)
            value, regtype = winreg.QueryValueEx(registry_key, r'outDir')
            winreg.CloseKey(registry_key)
            return value
        except WindowsError:
            print("winreg.WindowsError")
            return None
    except Exception as e:
        return None


def getNrOutputDir():

    outDir = _getOutDir(r'SOFTWARE\black_ninja\NinjaRipper 2.0.5')
    if outDir:
        return outDir
    outDir = _getOutDir(r'SOFTWARE\black_ninja\NinjaRipper2')
    return outDir


def identMat44():
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]


def stringToMat44(s):
    s = s.replace(' ', '')
    s = s.replace('[', '')
    s = s.replace(']', '')
    s = s.replace(';', '')
    s = s.replace('{', '')
    s = s.replace('}', '')
    arr = s.split(',')
    
    mat = identMat44()
    if len(arr) < 16:
        return mat

    b = 0
    for i in range(0, 4):
        r = [None] * 4
        r[0] = float(arr[b + 0])
        r[1] = float(arr[b + 1])
        r[2] = float(arr[b + 2])
        r[3] = float(arr[b + 3])
        mat[i] = r
        b = b + 4
    return mat


def perspMatFovLH(fovYdeg, width, height, nearZ, farZ):
    aspectHByW = float(width) / float(height)
    fovAngleY = fovYdeg * math.pi / 180.0
    sinFov = math.sin(0.5 * fovAngleY)
    cosFov = math.cos(0.5 * fovAngleY)
    Height = cosFov / sinFov;
    Width = Height / aspectHByW;
    mat = identMat44()
    
    q = float(farZ / (farZ - nearZ))
    mat[0] = [Width, 0.0, 0.0, 0.0]
    mat[1] = [0.0, Height, 0.0, 0.0]
    mat[2] = [0.0, 0.0, q, 1.0]
    mat[3] = [0.0, 0.0, -q * nearZ, 0.0]
    return mat


def matrixmult(A, B):
    rows_A = len(A)
    cols_A = len(A[0])
    rows_B = len(B)
    cols_B = len(B[0])

    if cols_A != rows_B:
        return None

    # Create the result matrix
    # Dimensions would be rows_A x cols_B
    C = [[0 for row in range(cols_B)] for col in range(rows_A)]
    for i in range(rows_A):
        for j in range(cols_B):
            for k in range(cols_A):
                C[i][j] += A[i][k] * B[k][j]
    return C


def matrixinvert(A):
    ''' Returns the inverse of A, where  A is a square matrix in the form of a nested list of lists. '''
    try:
        A = [A[i]+[int(i==j) for j in range(len(A))] for i in range(len(A))]
        for i in range(len(A)):
            A[i:] = sorted(A[i:], key=lambda r: -abs(r[i]))
            A[i] = [A[i][j]/A[i][i] for j in range(len(A)*2)]
            A = [[A[j][k] if i==j else A[j][k]-A[i][k]*A[j][i] for k in range(len(A)*2)] for j in range(len(A))]
        return [A[i][-len(A):] for i in range(len(A))]
    except:
        return None


def createMat(rows, cols):
    listoflists = []
    for i in range(0, rows):
        sublist = []
        for j in range(0, cols):
            sublist.append(0.0)
        listoflists.append(sublist)
    return listoflists


def transposeMat(A):
    mat = createMat(len(A), len(A[0]))
    for i in range(len(A)):
        for j in range(len(A[0])):
            mat[j][i] = A[i][j]
    return mat




# For Blender
# Return: [[x,y,z], [x,y,z]]
def unpackVertexComponentAsList(vert, vertexData, va):
    vertBaseOffs = 0
    fmt = va.getFormat()
    res = []
    for idx in range(0, vert.getVertexCount()):
        vertDataOffs = vertBaseOffs + va.offs
        p = struct.unpack_from(fmt, vertexData, vertDataOffs)
        res.append(p)
        vertBaseOffs = vertBaseOffs + vert.getVertexSize()
    return res


# For Blender
def restorePositionAsList(vert, vertexData, posVatr, projMat):
    invProjMat = matrixinvert(projMat)
    if None == invProjMat:
        #raise RuntimeError("Can't inverse projection matrix")
        return None

    if 4 != posVatr.compCount:
        #raise RuntimeError("Post vs position not 4 component")
        return None

    fmt = posVatr.getFormat()
    res = []
    for vertIdx in range(0, vert.getVertexCount()):
        vertDataOffs = vertIdx * vert.getVertexSize()
        vertDataOffs = vertDataOffs + posVatr.offs
        p = struct.unpack_from(fmt, vertexData, vertDataOffs)
        viewp = matrixmult([p], invProjMat)
        vp = viewp[0]
        pp = (vp[0], vp[1], vp[2])
        res.append(pp)
    return res



# layerTextureCoordinates [[u,v,w,t],[u,v,w,t],[u,v,w,t]...]
# Extract component data to list of list
#   uIdx=1 vIdx=3  ->   [[v,t],[v,t],[v,t]...]
#   uIdx=0 vIdx=2  ->   [[u,w],[u,w],[u,w]...]
def extractComponentsAsList(uvData, compIdxList):
    compsCnt = len(uvData[0])

    for compIdx in compIdxList:
        if compIdx >= compsCnt:
            return uvData

    res = []
    for v in uvData:
        tmpV = []
        for compIdx in compIdxList:
            tmpV.append(v[compIdx])
        res.append(tmpV)
    return res




# For Blender
# vaCompList - [[vaIdx, compIdx], ]
# Return: [[x,y,z], [x,y,z]]
def unpackVertexComponentVaAsList(vert, vertexData, vatrs, vaCompList):

    # Range checks
    for vaComp in vaCompList:
        vaIdx   = vaComp[0]
        compIdx = vaComp[1]

        va = vatrs.getAttr(vaIdx)
        if not va:
            # Attrib with idx not exist
            return None

        # Component index range error?
        if compIdx >= va.compCount:
            return None


    vertBaseOffs = 0

    res = []
    for idx in range(0, vert.getVertexCount()):
        resp = []
        for vaComp in vaCompList:
            vaIdx   = vaComp[0]
            compIdx = vaComp[1]

            va = vatrs.getAttr(vaIdx)
            fmt = va.getFormat()
            vertDataOffs = vertBaseOffs + va.offs
            p = struct.unpack_from(fmt, vertexData, vertDataOffs)
            resp.append(p[compIdx])

        res.append(resp)
        vertBaseOffs = vertBaseOffs + vert.getVertexSize()
    return res
