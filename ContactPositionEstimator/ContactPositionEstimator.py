#########################################################################################
### Name convention: Gui Object should have suffix CB for Collapsible
### Button, TB toolbox button etc...
#########################################################################################
import struct
import os
import unittest
import subprocess
from __main__ import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import numpy as np
import re
import collections
import json
import math
import platform
import sys
import math as m

"""Uses ScriptedLoadableModule base class, available at:
https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
"""

#########################################################################################
####                                                                                 ####
####  Contact Position Estimator ########################################################
####                                                                                 ####
#########################################################################################
class ContactPositionEstimator(ScriptedLoadableModule):
    #########################################################################################
    #### __init__
    #########################################################################################
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "1. Contact Position Estimator"
        self.parent.categories = ["SEEGA"]
        self.parent.dependencies = []
        self.parent.contributors = ["G. Arnulfo (Univ. Genoa) & M. Narizzano (Univ. Genoa)"]
        self.parent.helpText = """seeg electroDE rEconstruction TOol (ContactPositionEstimator):
                    This tool reconstructs the position of SEEG electrode contacts
                    from a post-implant Cone-beam CT scan."""
        self.parent.acknowledgementText = """This file was originally developed by Gabriele Arnulfo & Massimo Narizzano"""

        ## READ the configuration files under the Config/ directory
        self.parentPath = os.path.dirname(parent.path)
        self.configPath = self.parentPath + "/Config/deeto.config"
        self.electrodeTypesPath = self.parentPath + "/Config/electrodes.config"

        # Locate the deeto executable path and choose the right version respect the platform system
        with open(self.configPath) as data_file:
            tmpConfigData = json.load(data_file)
            if platform.system() == "Darwin":
                self.deetoExecutablePath = self.parentPath + "/" + tmpConfigData["deetoMac"]
            elif platform.system() == "Windows":
                self.deetoExecutablePath = self.parentPath + "/" + tmpConfigData["deetoWindows"]
            elif platform.system() == "Linux":
                self.deetoExecutablePath = self.parentPath + "/" + tmpConfigData["deetoLinux"]
            else:
                exit("Platform error")

#########################################################################################
####                                                                                 ####
####  ContactPositionEstimatorWidget                                                 ####
####                                                                                 ####
#########################################################################################
class ContactPositionEstimatorWidget(ScriptedLoadableModuleWidget):
    #######################################################################################
    ### setup
    #######################################################################################
    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)
        #### Some variables
        self.configurationSetup()
        self.lastSegmentation = []
        self.segmentationSetup()
        self.fids = None

    #######################################################################################
    ### configurationSetup
    ### Collapsible button, where are stored the information for the segmentation module
    ### for example the deeto executable location, etc...
    #######################################################################################
    def configurationSetup(self):
        #### Create a Collapsible Button
        self.setupCB = ctk.ctkCollapsibleButton()
        self.setupCB.text = "ContactPositionEstimator - Configuration"
        self.setupCB.collapsed = True
        self.layout.addWidget(self.setupCB)

        #### Collapsible button layout
        self.setupFL = qt.QFormLayout(self.setupCB)

        #### Tool Box for changing deeto Executable
        self.deetoTB = qt.QToolButton()
        self.deetoTB.setText("...")
        self.deetoTB.toolTip = "Change deeto executable"
        self.deetoTB.enabled = True
        self.deetoTB.connect('clicked(bool)', self.ondeetoTB)

        #### Line Edit button, where the executable path is shown
        self.deetoLE = qt.QLineEdit(slicer.modules.ContactPositionEstimatorInstance.deetoExecutablePath)
        self.deetoLE.setDisabled(True)
        self.deetoLE.setMaximumWidth(100)
        self.deetoLE.setFixedWidth(400)

        #### Buttons Layout
        self.deetoButtonsHBL = qt.QHBoxLayout()
        self.deetoButtonsHBL.addWidget(self.deetoLE)
        self.deetoButtonsHBL.addWidget(self.deetoTB)

        #### Aggiungo il bottone al layout
        self.setupFL.addRow("ContactPositionEstimator executable: ", self.deetoButtonsHBL)

        #### Button to change the deeto executable location
        #### It is called in ondeetoTB, when deetoTB is selected
        self.deetoFD = qt.QFileDialog()
        self.deetoFD.setFileMode(qt.QFileDialog.AnyFile)
        self.deetoFD.setToolTip("Pick the input to the algorithm.")

    #######################################################################################
    ### segmentationSetup #
    #######################################################################################
    def segmentationSetup(self):

        #### Collapsible Button --- General Frame
        self.segmentationCB = ctk.ctkCollapsibleButton()
        self.segmentationCB.text = "ContactPositionEstimator - Segmentation"
        self.segmentationCB.contentsLineWidth = 1
        self.layout.addWidget(self.segmentationCB)
        #### Collapsible Button layout
        self.segmentationFL = qt.QFormLayout(self.segmentationCB)

        #### Choose Fiducial - Section
        #### Select box ComboBox -
        self.fiducialCBox = slicer.qMRMLNodeComboBox()
        self.fiducialCBox.nodeTypes = (("vtkMRMLMarkupsFiducialNode"), "")
        self.fiducialCBox.selectNodeUponCreation = False
        self.fiducialCBox.addEnabled = False
        self.fiducialCBox.removeEnabled = False
        self.fiducialCBox.noneEnabled = True
        self.fiducialCBox.setMRMLScene(slicer.mrmlScene)
        self.fiducialCBox.setToolTip("Select a fiducial list")
        #### Add fiducial to the Collapsible Button
        self.segmentationFL.addRow("Fiducial List", self.fiducialCBox)
        #### Connect the fiducial list to the
        self.fiducialCBox.connect('currentNodeChanged(bool)', self.onfiducialCBox)
        #### Update fiducial Push Button
        self.updateFiducialPB = qt.QPushButton("Update Fiducial")
        self.updateFiducialPB.toolTip = "Run the algorithm."
        self.updateFiducialPB.enabled = True

        self.segmentationFL.addRow(self.updateFiducialPB)
        self.updateFiducialPB.connect('clicked(bool)', self.onfiducialCBox)

        #### Configure Segmentation - Section
        ### Read from files the list of the modules
        with open(slicer.modules.ContactPositionEstimatorInstance.electrodeTypesPath) as data_file:
            # models is a dictionary with the name of electrode type is the key
            self.models = json.load(data_file)

        #### Create the caption table for the configuration
        self.tableCaption = ["Name", "Type/Model", "TP", "cEP"]
        self.tableHsize = [80, 180, 50, 50]
        self.captionGB = qt.QGroupBox(self.segmentationCB)
        self.captionBL = qt.QHBoxLayout(self.captionGB)
        self.captionBL.setMargin(1)
        for i in (range(len(self.tableCaption))):
            a = qt.QLabel(self.tableCaption[i], self.captionGB)
            a.setMaximumWidth(self.tableHsize[i])
            a.setMaximumHeight(20)
            a.setStyleSheet("qproperty-alignment: AlignCenter;")
            self.captionBL.addWidget(a)

        self.segmentationFL.addRow("", self.captionGB)
        self.electrodeList = []

    #######################################################################################
    # onfiducialCBox   #
    # def onfiducialCBox(self):
    #  Create dynamically the electrode table, by reading the fiducial list selected, by
    #  (1) Clear old Fiducial Table
    #  self.clearTableclearTable()  # Eliminate the electrode list
    #
    #  (2) If the selected fiducial list is not None Do
    #      (a) Read the fiducial list and
    #      (b) for each point pair create an Electrode object containing:
    #          name, target and entry coordinates and the flag
    #      (c) check simple error cases: (i) missing entry/target,
    #        (ii) more points than expected
    # NB: unselected points will not be parsed
    #######################################################################################

    

    def onfiducialCBox(self):

        self.electrodeList = []
        self.clearTable()  # Eliminate the electrode list
        operationLog = ""  # error/warning Log string
        if self.fids is None:
            if self.fiducialCBox.currentNode() is None:
                return
            # (2.a) Read the fiducial list
            self.fids = self.fiducialCBox.currentNode()
        else:
            self.fids = slicer.mrmlScene.GetFirstNodeByClass('vtkMRMLMarkupsFiducialNode')

        # here we fill electrode list using fiducials
        for i in range(self.fids.GetNumberOfFiducials()):
            if self.fids.GetNthFiducialSelected(i) == True:
                P2 = [0.0, 0.0, 0.0]
                self.fids.GetNthFiducialPosition(i, P2)
                # [WARNING] The fiducial name convention is hard coded, change please[/WARNING]#
                # replace name with _1 or 1 with empty char
                self.name = re.sub(r"_?1", "", self.fids.GetNthFiducialLabel(i))
                # find the electrode in list with the same name
                el = [x for x in self.electrodeList if str(x.name.text) == self.name]
                if len(el) > 0:
                    if (len(el[0].target) > 0):
                        # (2.c.II)  more points than expected
                        operationLog += "WAR: \"" + self.name + "\" has defined more than 2 times"
                    P1 = el[0].entry
                    el[0].target = P2
                    distance_P2_P1 = (pow(P2[0], 2.0) + pow(P2[1], 2.0) + pow(P2[2], 2.0)) - \
                                     (pow(P1[0], 2.0) + pow(P1[1], 2.0) + pow(P1[2], 2.0))
                    if distance_P2_P1 > 0:
                        el[0].entry = P2
                        el[0].target = P1
                else:
                    # (2.b) for each point pair create an Electrode object containing:
                    #       name, target and entry coordinates and the flag
                    # Add the electrode Line to the collapsible button (update the GUI)
                    self.electrodeList.append(Electrode(self.name, self.segmentationCB, \
                                                        self.models, self.tableHsize))
                    self.electrodeList[len(self.electrodeList) - 1].entry = P2

                    # (2.c.i) Look for missing entry/target,
        el = [x for x in self.electrodeList if (len(x.target) == 0)]
        for i in range(len(el)):
            operationLog += "ERR: \"" + el[i].name.text + "\" Missing entry or target"
            el[i].delete()
            self.electrodeList.remove(el[i])

        # here electrodeList should have all the electrode objects in the list
        # we sort the electrode in list alphabetically
        self.electrodeList = sorted(self.electrodeList,key=lambda x: x.name.text)

        while not len(self.lastSegmentation) == 0:
            self.segmentationFL.removeRow(self.lastSegmentation[0])
            del self.lastSegmentation[0]

        # Link the electrode to the Form
        for elec in self.electrodeList:
            elec.computeLength()
            elec.setElectrodeModel(self.models)
            self.segmentationFL.addRow("", elec.row)
            self.lastSegmentation.append(elec.row)

        # notify error
        slicer.util.showStatusMessage(operationLog)
        if len(self.electrodeList) == 0:
            return
        # GUI CT Segmentation - Section
        # CT selector  input volume selector
        self.ctVolumeCB = slicer.qMRMLNodeComboBox()
        self.ctVolumeCB.nodeTypes = (("vtkMRMLScalarVolumeNode"), "")
        self.ctVolumeCB.addAttribute("vtkMRMLScalarVolumeNode", "LabelMap", 0)
        self.ctVolumeCB.selectNodeUponCreation = True
        self.ctVolumeCB.addEnabled = False
        self.ctVolumeCB.removeEnabled = False
        self.ctVolumeCB.noneEnabled = True
        self.ctVolumeCB.showHidden = False
        self.ctVolumeCB.showChildNodeTypes = False
        self.ctVolumeCB.setMRMLScene(slicer.mrmlScene)
        self.ctVolumeCB.setToolTip("Pick the input to the algorithm.")

        self.volumeCtLabel = qt.QLabel("CT Volume")
        self.segmentationFL.addRow(self.volumeCtLabel, self.ctVolumeCB)
        self.lastSegmentation.append(self.volumeCtLabel)
        self.lastSegmentation.append(self.ctVolumeCB)

        # START Segmentation Button
        self.startSegmentationPB = qt.QPushButton("Start Segmentation")
        self.startSegmentationPB.toolTip = "Run the algorithm."
        self.startSegmentationPB.enabled = True

        # CREATE vtk models
        self.createVTKModels = qt.QCheckBox("Create Shaft Model?")

        # SPLIT Fiducial Combobox
#        self.fiducialSplitBox = slicer.qMRMLNodeComboBox()
#        self.fiducialSplitBox.nodeTypes = (("vtkMRMLMarkupsFiducialNode"), "")
#        self.fiducialSplitBox.selectNodeUponCreation = False
#        self.fiducialSplitBox.addEnabled = False
#        self.fiducialSplitBox.removeEnabled = False
#        self.fiducialSplitBox.noneEnabled = True
#        self.fiducialSplitBox.setMRMLScene(slicer.mrmlScene)
#        self.fiducialSplitBox.setToolTip("Select a fiducial list")

        # SPLIT Fiducials Button
#        self.splitFiducialPB = qt.QPushButton("Split Fiducial List")
#        self.splitFiducialPB.toolTip = "Split Fiducial file, one for each electrode"
#        self.splitFiducialPB.enabled = True

        horzGroupLayout = qt.QHBoxLayout()
        horzGroupLayout.addWidget(self.startSegmentationPB)
        horzGroupLayout.addWidget(self.createVTKModels)

        self.segmentationFL.addRow("", horzGroupLayout)
        self.lastSegmentation.append(horzGroupLayout)

#        self.segmentationFL.addRow("", self.fiducialSplitBox)
#        self.segmentationFL.addRow("", self.splitFiducialPB)

        # connections
#        self.splitFiducialPB.connect('clicked(bool)', self.onsplitFiducialClick)
        self.startSegmentationPB.connect('clicked(bool)', self.onstartSegmentationPB)

    #######################################################################################
    # on ContactPositionEstimator BUTTON
    #######################################################################################
    def ondeetoTB(self):
        """ on ContactPositionEstimator Tool Box Button Logic """
        fileName = qt.QFileDialog.getOpenFileName(self.deetoFD, \
                                                  "Choose surf directory", "~", "")
        self.deetoLE.setText(fileName)
        slicer.modules.ContactPositionEstimatorInstance.deetoExecutablePath = fileName

    #######################################################################################
    # on Start Segmentation, by reading
    #######################################################################################
    def onstartSegmentationPB(self):
        slicer.util.showStatusMessage("START SEGMENTATION")
        print ("RUN SEGMENTATION ALGORITHM ")
        try:
            ContactPositionEstimatorLogic().runSegmentation(self.electrodeList, self.ctVolumeCB.currentNode(), \
                                                            slicer.modules.ContactPositionEstimatorInstance.parentPath, \
                                                            slicer.modules.ContactPositionEstimatorInstance.deetoExecutablePath, \
                                                            self.models, self.createVTKModels)
            print ("END RUN SEGMENTATION ALGORITHM \n")
            slicer.util.showStatusMessage("END SEGMENTATION")
        except IndexError:
            print("ERROR: electrode misplaced\nSTOP SEGMENTATION\n")
            slicer.util.showStatusMessage("ERROR: electrode misplaced")

    #######################################################################################
    # onSplitFiducialClick
    #######################################################################################
#    def onsplitFiducialClick(self):
#        """ onSplitFiducialClick  """
#
#        def uniquify(seq):
#            # order preserving
#            checked = []
#            for e in seq:
#                if e not in checked:
#                    checked.append(e)
#            return checked
#
#        # read get the fiducial file reconstructed
#        fiducialData = self.fiducialSplitBox.currentNode()
#
#        # Get channel names
#        chLabels = [fiducialData.GetNthFiducialLabel(i) for i in xrange(fiducialData.GetNumberOfFiducials())]
#
#        # Extract electrode name from channel names
#        elLabels = [re.match('[A-Z]*\'?', x).group(0) for x in chLabels]
#        uniqueElLabels = uniquify(elLabels)
#
#        # count for each electrode name the number of segmented contacts
#        elChCounts = [elLabels.count(x) for x in uniqueElLabels]
#
#        print "SPLITTING FIDUCIAL FILES"
#
#        offset = 0
#        for elIdx in xrange(len(uniqueElLabels)):
#
#            elLabel = uniqueElLabels[elIdx]
#            newFids = slicer.util.getNode(slicer.modules.markups.logic().AddNewFiducialNode(elLabel))
#
#            for chIdx in xrange(elChCounts[elIdx]):
#                # we have to create a separate fiducial file for
#                # each electrode and populate with corresponding
#                # channel positions and labels
#                P = [0.0, 0.0, 0.0]
#                fiducialData.GetNthFiducialPosition(chIdx + offset, P)
#                newFids.AddFiducial(P[0], P[1], P[2])
#                newFids.SetNthFiducialLabel(chIdx, fiducialData.GetNthFiducialLabel(chIdx + offset))
#                newFids.SetNthMarkupDescription(chIdx, fiducialData.GetNthMarkupDescription(chIdx + offset))
#
#            slicer.modules.markups.logic().SetAllMarkupsLocked(newFids, True)
#            offset += elChCounts[elIdx]
#        print "DONE"

    #######################################################################################
    # clearTable
    #######################################################################################
    def clearTable(self):
        if ((len(self.electrodeList) - 1) < 0):
            return

        # delete last row
        self.startSegmentationPB.setParent(None)
        self.startSegmentationPB.deleteLater()
        self.segmentationFL.takeAt(self.segmentationFL.count())

        # delete last two rows (one is the label)
        self.ctVolumeCB.setParent(None)
        self.ctVolumeCB.deleteLater()
        self.volumeCtLabel.setParent(None)
        self.volumeCtLabel.deleteLater()
        self.segmentationFL.takeAt(self.segmentationFL.count())
        self.segmentationFL.takeAt(self.segmentationFL.count())

        #self.splitFiducialPB.setParent(None)
        #self.splitFiducialPB.deleteLater()
        self.segmentationFL.takeAt(self.segmentationFL.count())
        #self.fiducialSplitBox.setParent(None)
        #self.fiducialSplitBox.deleteLater()
        self.segmentationFL.takeAt(self.segmentationFL.count())

        last = len(self.electrodeList) - 1
        self.createVTKModels.setParent(None)
        self.createVTKModels.deleteLater()

        while last >= 0:
            self.electrodeList[last].delete()
            self.electrodeList.remove(self.electrodeList[last])
            self.segmentationFL.takeAt(self.segmentationFL.count())
            last = len(self.electrodeList) - 1

        self.segmentationFL.update()
        # notify error
        slicer.util.showStatusMessage("")


#########################################################################################
#
# ContactPositionEstimatorLogic
#
#########################################################################################
class ContactPositionEstimatorLogic(ScriptedLoadableModuleLogic):
    def __init__(self):
        # Create a Progress Bar
        self.pb = qt.QProgressBar()

    #######################################################################################
    # runSegmentation
    #######################################################################################
    def runSegmentation(self, elList, volume, parentPath, deetoExe, models, createVTK):
        ### CHECK that both the fiducials and ct volume have been selected
        if (len(elList) == 0):
            # notify error
            slicer.util.showStatusMessage("Error, no electrode list selected")
            return
        if (volume == None):
            # notify error
            slicer.util.showStatusMessage("Error, no volume selected")
            return

        ### COMPUTE THE THRESHOLD the 45% of points not null(0.0)
        im = volume.GetImageData()
        # linearize the 3D image in a vector
        vector = vtk.util.numpy_support.vtk_to_numpy(im.GetPointData().GetScalars())
        # eliminate 0.0 value from the vector
        n_vector = vector[vector != 0]
        # sort the intensity values
        n_vector.sort()
        # compute the threshold as the 45% of points not null
        threshold = n_vector[int(n_vector.size * 0.45)]

        ### CREATE A NEW FIDUCIAL LIST CALLED ...... [TODO]
        #mlogic = slicer.modules.markups.logic()
        mlogic = slicer.modules.markups.logic().GetDefaultMarkupsDisplayNode()

        ###
        ### [TODO] Accrocchio, non so come cambiare questi parametri solo
        ### per il nodo corrente, invece che di default
        #mlogic.SetDefaultMarkupsDisplayNodeTextScale(1.3)
        #mlogic.SetDefaultMarkupsDisplayNodeGlyphScale(1.5)
        #mlogic.SetDefaultMarkupsDisplayNodeColor(0.39, 0.78, 0.78)  # AZZURRO
        #mlogic.SetDefaultMarkupsDisplayNodeSelectedColor(0.39, 1.0, 0.39)  # VERDONE

        mlogic.SetTextScale(3.0)
        mlogic.SetGlyphScale(3.0)
        mlogic.SetColor(0.39, 0.78, 0.78)  # AZZURRO
        mlogic.SetSelectedColor(0.39, 1.0, 0.39)  # VERDONE

        fidNode = slicer.util.getNode(slicer.modules.markups.logic().AddNewFiducialNode("recon"))

        # Save the volume as has been modified
        self.tmpVolumeFile = parentPath + "/Tmp/tmp.nii.gz"
        self.saveNode(volume, self.tmpVolumeFile)

        # Set the parameters of the progess bar and show it
        self.pb.setRange(0, len(elList))
        self.pb.show()
        self.pb.setValue(0)
        slicer.app.processEvents()

        # For each electrode "e":
        for i in range(len(elList)):
            tFlag = "-l" if (elList[i].tailCheckBox.isChecked() == True) else "-t"
            hFlag = "-h" if (elList[i].headCheckBox.isChecked() == True) else "-e"
            # Construct the cmdLine to run the segmentation on "e"

            cmdLine = [str(deetoExe), '-s', str(threshold), '-ct', str(self.tmpVolumeFile), \
                       hFlag, str(-1 * elList[i].entry[0]), str(-1 * elList[i].entry[1]), \
                       str(elList[i].entry[2]), tFlag, \
                       str(-1 * elList[i].target[0]), str(-1 * elList[i].target[1]), \
                       str(elList[i].target[2]), '-m'] + \
                      list(map(str, models[elList[i].model.currentText][:-1]))

            # abi ricontrolla se c'era altro prima qui

            # RUN the command line cmdLine.
            # [NOTE] : I have used Popen since subprocess.check_output wont work at the moment
            # It Looks a problem of returning code from deetoS
            points = subprocess.Popen(cmdLine, stdout=subprocess.PIPE).communicate()[0].splitlines()
            # print points

            ### For each of the point returned by deeto we add it to the new markup fiducial
            name = elList[i].name.text

            ### For each electrode we create a line from the start point to the last + 3mm
            ### Look for two points p1 and p3 starting from p1 and p2 (first and last point segmented
            last = len(points) - 1
            p1 = [float(points[0]), float(points[1]), float(points[2])]
            p2 = [float(points[last - 2]), float(points[last - 1]), float(points[last])]
            delta = math.sqrt(
                math.pow((p1[0] - p2[0]), 2) + math.pow((p1[1] - p2[1]), 2) + math.pow((p1[2] - p2[2]), 2))
            p3 = [0.0, 0.0, 0.0]
            p3[0] = p2[0] + (p2[0] - p1[0]) / delta * 3  # distance 3mm
            p3[1] = p2[1] + (p2[1] - p1[1]) / delta * 3  # distance 3mm
            p3[2] = p2[2] + (p2[2] - p1[2]) / delta * 3  # distance 3mm

            for p in range(0, (len(points) - 1), 3):
                a = fidNode.AddControlPoint(float(points[p]), float(points[p + 1]), float(points[p + 2]))
                fidNode.SetNthFiducialLabel(a, name + str((p / 3) + 1))
                fidNode.SetNthControlPointDescription(a, elList[i].model.currentText)
                """
                ### Create a vtk cylinder
                cylinderSource = vtk.vtkCylinderSource()
                cylinderSource.SetCenter(0,0,0)
                cylinderSource.SetHeight(list(models.values())[0][1])
                cylinderSource.SetRadius(list(models.values())[0][2])
                cylinderSource.SetResolution(100)
                cylinderSource.Update()
                ### Create a model of the cylinder to add to the scene
                cylindermodel = slicer.vtkMRMLModelNode()
                cylindermodel.SetName(name + "_direction")
                cylindermodel.SetAndObservePolyData(cylinderSource.GetOutput())

                #Create a Transform node for the model to copy the rotation
                cylinderTS = slicer.vtkMRMLTransformNode()

                ##compute the rotation
                #Given the vector (p1,p3) i move it to the origin
                vorigin = np.subtract(p1,p3)
                #compute rotation matrix
                R = self.rotMat(vorigin)
                #from 3x3 matrix i transformit in a 4x4 matrix
                matrix4 = self.mat3To4(R, float(points[p]), float(points[p + 1]), float(points[p + 2]))
                #from 4x4 matrix, generate vtkmatrix4x4 object
                rMatrix = self.mat4x4Gen(matrix4)
                #add the rotation to the model
                cylinderTS.SetAndObserveMatrixTransformToParent(rMatrix)

                cylindermodelDisplay = slicer.vtkMRMLModelDisplayNode()
                cylindermodelDisplay.SetSliceIntersectionVisibility(True)  # Hide in slice view
                cylindermodelDisplay.SetVisibility(True)  # Show in 3D view
                cylindermodelDisplay.SetColor(1, 0, 0)
                cylindermodelDisplay.SetLineWidth(2)
                cylindermodelDisplay.SetOpacity(0.5)

                slicer.mrmlScene.AddNode(cylindermodelDisplay)
                cylindermodel.SetAndObserveDisplayNodeID(cylindermodelDisplay.GetID())

                slicer.mrmlScene.AddNode(cylinderTS)
                cylindermodel.SetAndObserveTransformNodeID(cylinderTS.GetID())

                slicer.mrmlScene.AddNode(cylindermodel)
                """
            if createVTK.checked:
                ### Create a vtk line
                lineSource = vtk.vtkLineSource()
                lineSource.SetPoint1(p1)
                lineSource.SetPoint2(p3)
                lineSource.SetResolution(100)  ## why?
                lineSource.Update()
                ### Create a model of the line to add to the scene
                model = slicer.vtkMRMLModelNode()
                model.SetName(name + "_direction")
                model.SetAndObservePolyData(lineSource.GetOutput())
                modelDisplay = slicer.vtkMRMLModelDisplayNode()
                modelDisplay.SetSliceIntersectionVisibility(True)  # Hide in slice view
                modelDisplay.SetVisibility(True)  # Show in 3D view
                modelDisplay.SetColor(1, 0, 0)
                modelDisplay.SetLineWidth(2)
                slicer.mrmlScene.AddNode(modelDisplay)
                model.SetAndObserveDisplayNodeID(modelDisplay.GetID())
                slicer.mrmlScene.AddNode(model)

            # Lock all markup
            slicer.modules.markups.logic().SetAllMarkupsLocked(fidNode, True)

            # update progress bar
            self.pb.setValue(i + 1)
            slicer.app.processEvents()

        self.pb.hide()

    #######################################################################################
    ### saveNode
    #######################################################################################
    def saveNode(self, node, filename, properties={}):
        """Save 'node' data into 'filename'.
    It is the user responsibility to provide the appropriate file extension.
    User has also the possibility to overwrite the fileType internally retrieved using
    method 'qSlicerCoreIOManager::fileWriterFileType(vtkObject*)'. This can be done
    by specifying a 'fileType'attribute to the optional 'properties' dictionary.
    """
        from slicer import app
        properties["nodeID"] = node.GetID()
        properties["fileName"] = filename
        if hasattr(properties, "fileType"):
            filetype = properties["fileType"]
        else:
            filetype = app.coreIOManager().fileWriterFileType(node)
        return app.coreIOManager().saveNodes(filetype, properties)

        # def createModelList(self):
        #     self.electrodeModelist = list()

    def mat4x4Gen(self, m):
        rMatrix = vtk.vtkMatrix4x4()
        for x in range(4):
            for y in range(4):
                rMatrix.SetElement(x, y, m[x][y])
        return rMatrix

    def mat3To4(self, m,x,y,z):
        b = np.array([[0, 0, 0]])
        c = np.concatenate((m, b), axis=0)
        d = np.array([[x, y, z, 1]])
        return np.concatenate((c, d.T), axis=1)

    #compute euler angles from rotation matrix
    def fromRotMat(self, R):
        tol = sys.float_info.epsilon * 10

        if abs(R.item(0, 0)) < tol and abs(R.item(1, 0)) < tol:
            eul1 = 0
            eul2 = m.atan2(-R.item(2, 0), R.item(0, 0))
            eul3 = m.atan2(-R.item(1, 2), R.item(1, 1))
        else:
            eul1 = m.atan2(R.item(1, 0), R.item(0, 0))
            sp = m.sin(eul1)
            cp = m.cos(eul1)
            eul2 = m.atan2(-R.item(2, 0), cp * R.item(0, 0) + sp * R.item(1, 0))
            eul3 = m.atan2(sp * R.item(0, 2) - cp * R.item(1, 2), cp * R.item(1, 1) - sp * R.item(0, 1))

        return eul3, eul2, eul1

    def rotMat(self, vec2):
        """ Find the rotation matrix that aligns vec1 to vec2
        :param vec1: A 3d "source" vector
        :param vec2: A 3d "destination" vector
        :return mat: A transform matrix (3x3) which when applied to vec1, aligns it with vec2.
        """
        vec1 = [0,1,0]
        a, b = (vec1 / np.linalg.norm(vec1)).reshape(3), (vec2 / np.linalg.norm(vec2)).reshape(3)
        v = np.cross(a, b)
        c = np.dot(a, b)
        s = np.linalg.norm(v)
        kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
        rotation_matrix = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c) / (s ** 2))
        return rotation_matrix



#########################################################################################
####                                                                                 ####
#### Electrode                                                                       ####
####                                                                                 ####
#########################################################################################
class Electrode():
    #######################################################################################
    ### __init__
    #######################################################################################
    def __init__(self, name, configurationCB, models, hsize):
        ## target and entry point
        self.target = []
        self.entry = []


        #### Create a new GroupBOX i.e. a line
        self.row = qt.QGroupBox(configurationCB)
        self.hlayout = qt.QHBoxLayout(self.row)
        self.hlayout.setMargin(1)

        #### Create a new label
        self.name = qt.QLabel(name, self.row)
        self.name.setMaximumWidth(hsize[0])
        self.name.setMaximumHeight(20)
        self.hlayout.addWidget(self.name)

        # Eletrode Length
        self.length = 0

        #### Set the model list combo box
        self.model = qt.QComboBox(self.row)
        self.keys = sorted(models, reverse=True)
        #self.keys = models.keys()
        #self.keys.sort(reverse=True)
        self.model.addItems(self.keys)

        self.model.setMaximumWidth(hsize[1])
        self.model.setMaximumHeight(20)
        self.model.setStyleSheet("qproperty-alignment: AlignCenter;")
        self.hlayout.addWidget(self.model)

        #### Tail Check Box
        self.tailCheckBox = qt.QCheckBox(self.row)
        self.tailCheckBox.setMaximumWidth(hsize[2])
        self.tailCheckBox.setMaximumHeight(20)
        self.tailCheckBox.setStyleSheet("qproperty-alignment: AlignCenter;")
        self.hlayout.addWidget(self.tailCheckBox)

        ### Head CheckBox
        self.headCheckBox = qt.QCheckBox(self.row)
        self.headCheckBox.setMaximumWidth(hsize[3])
        self.headCheckBox.setMaximumHeight(20)
        self.headCheckBox.setStyleSheet("qproperty-alignment: AlignCenter;")
        self.hlayout.addWidget(self.headCheckBox)

    def computeLength(self):
        if len(self.entry) == 0 or len(self.target) == 0:
            self.length = 0
        tmpEP = np.array(self.entry)
        tmpTP = np.array(self.target)
        # compute euclidean distance
        self.length = np.sqrt(np.sum((tmpEP-tmpTP)**2))

    def setElectrodeModel(self,availableModels):
        # availableModels is a dict with elec name as key
        minLength = 100
        elecModel = list(availableModels.keys())[0]
        for k,v in availableModels.items():
            elecModelLength = float(v[-1])
            currMinLength = abs(self.length-elecModelLength)
            if minLength > currMinLength:
                minLength = currMinLength
                elecModel = k
        modelIdx = self.model.findText(elecModel)
        if modelIdx >= 0:
            self.model.setCurrentIndex(modelIdx)

    def updateInitialPoints(self,target,entry):
        if self.entry != entry:
            self.entry = entry
        if self.target != target:
            self.target = target

    #######################################################################################
    ### delete
    #######################################################################################
    def delete(self):
        self.row.setParent(None)
        self.row.deleteLater()
