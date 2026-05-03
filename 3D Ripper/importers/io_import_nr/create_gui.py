import os
import sys
import datetime

scriptdir = os.path.dirname(__file__) + "/"

inputTempFile = scriptdir + 'gui_templ.py'

curTime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

with open(inputTempFile, mode='r') as file:
    templContent = file.read()

    # gui0.py (blender < 2.8)
    guiCont = templContent.replace("@@@", "=")
    guiCont = guiCont.replace("##timemarker##", curTime)
    guiFile = open(scriptdir + 'gui0.py', 'w')
    guiFile.write(guiCont)
    guiFile.close()

    # gui1.py (blender >= 2.8)
    guiCont = templContent.replace("@@@", ":")
    guiCont = guiCont.replace("##timemarker##", curTime)
    guiFile = open(scriptdir + 'gui1.py', 'w')
    guiFile.write(guiCont)
    guiFile.close()

    print("gui0.py gui1.py created")
