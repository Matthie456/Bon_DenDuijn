# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpatialDecisionDockWidget
                                 A QGIS plugin
 This is a SDSS template for the GEO1005 course
                             -------------------
        begin                : 2015-11-02
        git sha              : $Format:%H$
        copyright            : (C) 2015 by Jorge Gil, TU Delft
        email                : j.a.lopesgil@tudelft.nl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt4 import QtGui, QtCore, uic
from qgis.core import *
from qgis.networkanalysis import *
# Initialize Qt resources from file resources.py
import resources

import os
import os.path
import random
import processing
import csv

from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsMapToolPan

from . import utility_functions as uf

import webbrowser

from PyQt4.QtGui import QMessageBox, QCursor
from PyQt4.QtGui import *
from PyQt4.QtCore import *



FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'spatial_decision_dockwidget_base.ui'))

class SpatialDecisionDockWidget(QtGui.QDockWidget, FORM_CLASS):

    closingPlugin = QtCore.pyqtSignal()
    #custom signals
    updateAttribute = QtCore.pyqtSignal(str)

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(SpatialDecisionDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        # define globals
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.scn_list = []

        # set up GUI operation signals

        #general
        self.wikipushButton.clicked.connect(self.openwiki)
        self.wikipushButton.setIcon(QtGui.QIcon(':icons/question.png'))
        self.mainlabel.setPixmap(QtGui.QPixmap(':icons/icon_large.png'))

        # data
        self.iface.projectRead.connect(self.updateLayers)
        self.iface.newProjectCreated.connect(self.updateLayers)
        self.openScenarioButton.clicked.connect(self.openScenario)
        self.saveScenarioButton.clicked.connect(self.saveScenario)
        self.selectAttributeCombo.hide()
        self.selectAttributeLabel.hide()

        # analysis
        self.checkAccessibilityButton.clicked.connect(self.checkaccessibility)
        self.addNodeButton.clicked.connect(self.startnodeprocess)
        self.recalculateButton.clicked.connect(self.recalculateaccessibility)

        # dropdown menus
        self.buildingCentroidsCombo.activated.connect(self.setBuildinglayer)
        self.SelectUserGroupCombo.activated.connect(self.setSelectedUserGroup)
        self.transitLayerCombo.activated.connect(self.setSelectedLayer)

        # toggle layer visibility
        self.toggleBufferCheckBox.stateChanged.connect(self.toggleBufferLayer)
        self.toggleAccessibiltyCheckBox.stateChanged.connect(self.toggleAccessibilityLayer)
        self.toggleLoAccessibilityCheckBox.stateChanged.connect(self.toggleDensityLayer)

        # reporting
        self.saveMapButton.clicked.connect(self.saveMap)
        self.generateReportButton.clicked.connect(self.reporting)
        self.saveTableButton.clicked.connect(self.saveTable)

        # set current UI restrictions
        self.reportList.hide()
        #self.statisticsTable.hide()
        self.updateAttribute.connect(self.extractAttributeSummary)
        
        # initialisation
        self.updateLayers()
        proj = QgsProject.instance()
        proj.writeEntry("SpatialDecisionDockWidget", 'CRS' ,28992)

    def closeEvent(self, event):
        # disconnect interface signals
        self.iface.projectRead.disconnect(self.updateLayers)
        self.iface.newProjectCreated.disconnect(self.updateLayers)

        self.closingPlugin.emit()
        event.accept()
#######
#   Input functions
#######

    def openwiki(self):
        url = 'https://github.com/Matthie456/Bon_DenDuijn/wiki'
        webbrowser.open(url)


    def openScenario(self,filename=""):
        scenario_open = False

        msgBox = QtGui.QMessageBox()
        msgBox.setText('Are you sure?\nThis will delete all scenarios')
        msgBox.addButton(QtGui.QPushButton('No'), QtGui.QMessageBox.RejectRole)
        msgBox.addButton(QtGui.QPushButton('Yes'), QtGui.QMessageBox.AcceptRole)
        ret = msgBox.exec_()

        if ret == 0:
            return
        elif ret == 1:
            scenario_file = os.path.join('{}'.format(QgsProject.instance().homePath()), 'Small_project.qgs')
            # check if file exists
            if os.path.isfile(scenario_file):
                self.iface.addProject(scenario_file)
                scenario_open = True
            else:
                last_dir = uf.getLastDir("SDSS")
                #last_dir = QgsProject.instance().homePath()
                new_file = QtGui.QFileDialog.getOpenFileName(self, "", last_dir, "(*.qgs)")
                if new_file:
                    self.iface.addProject(new_file)
                    scenario_open = True
            if scenario_open:
                self.updateLayers()

    def saveScenario(self):
        self.iface.actionSaveProjectAs().trigger()

    def updateLayers(self):
        layers = uf.getLegendLayers(self.iface, 'all', 'all')
        self.transitLayerCombo.clear()
        self.buildingCentroidsCombo.clear()
        if layers:
            layer_names = uf.getLayersListNames(layers)
            self.transitLayerCombo.addItems(layer_names)
            self.buildingCentroidsCombo.addItems(layer_names)
            self.setSelectedLayer()
            self.setBuildinglayer()

    def setSelectedLayer(self):
        layer_name = self.transitLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getSelectedLayer(self):
        layer_name = self.transitLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        return layer

    def updateAttributes(self, layer):
        self.selectAttributeCombo.clear()
        if layer:
            fields = uf.getFieldNames(layer)
            self.selectAttributeCombo.addItems(fields)
            # send list to the report list window
            self.clearReport()
            self.updateReport(fields)

    def setSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        self.updateAttribute.emit(field_name)

    def getSelectedAttribute(self):
        field_name = self.selectAttributeCombo.currentText()
        return field_name

    def setSelectedUserGroup(self):
        proj = QgsProject.instance()
        if self.SelectUserGroupCombo.currentText() == 'Students':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 800)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro', 'tram')")
            proj.writeEntry("SpatialDecisionDockWidget", "rail_radius", 1000)
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Students.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)
        elif self.SelectUserGroupCombo.currentText() == 'Elderly':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 400)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','tram','ferry')")
            proj.writeEntry("SpatialDecisionDockWidget", "rail_radius", 750)
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Elderly.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)
        elif self.SelectUserGroupCombo.currentText() == 'Adults':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 600)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro','ferry')")
            proj.writeEntry("SpatialDecisionDockWidget", "rail_radius", 800)
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Adults.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)

#######
#    Analysis functions
#######

    def setBuildinglayer(self):
        layer_name = self.buildingCentroidsCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getBuildinglayer(self):
        layer_name = self.buildingCentroidsCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        return layer

    def toggleBufferLayer(self):
        cur_user = self.SelectUserGroupCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface, 'Buffers_{}'.format(cur_user))
        if not layer:
            print 'layer does not exist'
            self.toggleBufferCheckBox.setChecked(False)
            return
        else:
            state = self.toggleBufferCheckBox.checkState()

            if state == 0:
                self.iface.legendInterface().setLayerVisible(layer, False)
                self.refreshCanvas(layer)
            elif state == 2:
                self.iface.legendInterface().setLayerVisible(layer, True)
                self.refreshCanvas(layer)

    def toggleAccessibilityLayer(self):

        layer = uf.getLegendLayerByName(self.iface, 'Accessibility')
        if not layer:
            print 'layer does not exist'
            self.toggleAccessibiltyCheckBox.setChecked(False)
            return
        else:
            state = self.toggleAccessibiltyCheckBox.checkState()

            if state == 0:
                #check if layer exists

                self.iface.legendInterface().setLayerVisible(layer, False)
                self.refreshCanvas(layer)
            elif state == 2:
                #check if layer exists
                self.iface.legendInterface().setLayerVisible(layer, True)
                self.refreshCanvas(layer)

    def toggleDensityLayer(self):
        layer = uf.getLegendLayerByName(self.iface, 'Population_density')
        if not layer:
            print 'layer does not exist'
            self.toggleLoAccessibilityCheckBox.setChecked(False)
            return
        else:
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            cur_user = self.SelectUserGroupCombo.currentText()
            layer.loadNamedStyle('{}population_density_{}.qml'.format(path,cur_user))
            state = self.toggleLoAccessibilityCheckBox.checkState()

            if state == 0:
                self.iface.legendInterface().setLayerVisible(layer, False)
                self.refreshCanvas(layer)
            elif state == 2:
                self.iface.legendInterface().setLayerVisible(layer, True)
                self.refreshCanvas(layer)

    ## MAIN Function
    def checkaccessibility(self):
        '''Runs all other functions'''

        self.iface.legendInterface().addGroup("Baselayers")
        self.calculateBuffer(False)
        self.accessibility(False)

        # ordering accessibility layer
        root = QgsProject.instance().layerTreeRoot()
        base_group = root.children()[1]
        access = base_group.children()[1]
        access_clone = access.clone()
        base_group.insertChildNode(0,access_clone)
        base_group.removeChildNode(access)

        # ordering scenarios group
        base_group_clone = base_group.clone()
        root.insertChildNode(0, base_group_clone)
        root.removeChildNode(base_group)
        transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
        transit_layer.removeSelection()

    def recalculateaccessibility(self):
        '''Runs all other functions, with added nodes'''
        ischecked = self.addNodeButton.isChecked()

        if ischecked:
            self.addNodeButton.setChecked(False)
            self.startnodeprocess()
            
        name = self.newLayerNameEdit.text()
        self.iface.legendInterface().addGroup(name)
        root = QgsProject.instance().layerTreeRoot()
        length = len(root.children())
        new_group = root.children()[length-1]
        new_group_clone = new_group.clone()
        new_group_clonadde = new_group.clone()
        root.insertChildNode(0,new_group_clone)
        root.removeChildNode(new_group)
        scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))

        self.iface.legendInterface().moveLayer(scenario_layer, 0)
        self.calculateBuffer(True)
        self.accessibility(True)

    # Calculate Buffers
    def calculateBuffer(self, is_scn):

        # Globals
        proj = QgsProject.instance()
        cur_user = self.SelectUserGroupCombo.currentText()
        radius = proj.readNumEntry("SpatialDecisionDockWidget", "radius")[0]
        transittypes = proj.readEntry("SpatialDecisionDockWidget", "transittypes")[0]
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        name = self.newLayerNameEdit.text()

        # Check which layer should be used as transit layer
        if is_scn:
            scn_layer = uf.getLegendLayerByName(self.iface, 'Transit_{}'.format(name))
            transit_layer = scn_layer
        else:
            transit_layer = self.getSelectedLayer()

        # Select the right features
        uf.selectFeaturesByExpression(transit_layer,"network in {}".format(transittypes))
        origins = transit_layer.selectedFeatures()
        layer = transit_layer

        # Actual buffer creation
        if origins > 0:
            cutoff_distance = radius
            buffers = {}
            for point in origins:
                attr = point.attribute('network')
                if attr == 'rail':
                    rail_radius = proj.readNumEntry("SpatialDecisionDockWidget", "rail_radius")[0]
                    geom = point.geometry()
                    buffers[point.id()] = geom.buffer(rail_radius,12)
                else:
                    geom = point.geometry()
                    buffers[point.id()] = geom.buffer(cutoff_distance,12)

            # store the buffer results in temporary layer called "Buffers_[cur_user]"
            buffer_layer = uf.getLegendLayerByName(self.iface, 'Buffers_{}'.format(cur_user))
            # create one if it doesn't exist and add suffix for the scenario
            if not buffer_layer:
                attribs = ['id', 'distance', 'network']
                types = [QtCore.QVariant.String, QtCore.QVariant.Double, QtCore.QVariant.String]
                buffer_layer = uf.createTempLayer('Buffers_{}'.format(cur_user),'POLYGON',CRS, attribs, types)
                buffer_layer.setLayerName('Buffers_{}'.format(cur_user))
                print "created layer", buffer_layer.name()
                uf.loadTempLayer(buffer_layer)
            if is_scn:
                name = self.newLayerNameEdit.text()
                attribs = ['id', 'distance', 'network']
                types = [QtCore.QVariant.String, QtCore.QVariant.Double, QtCore.QVariant.String]
                buffer_layer = uf.createTempLayer('Buffers_{}_{}'.format(cur_user, name),'POLYGON',CRS, attribs, types)
                buffer_layer.setLayerName('Buffers_{}_{}'.format(cur_user, name))
                print "created layer", buffer_layer.name()
                uf.loadTempLayer(buffer_layer)

            # insert buffer polygons
            geoms = []
            values = []

            fld_values = uf.getFieldValues(layer, 'network', True,"network in {}".format(transittypes))[0]
            cnt = 0
            for buffer in buffers.iteritems():
                geoms.append(buffer[1])
                if fld_values[cnt] == 'rail':
                   values.append([buffer[0],rail_radius, fld_values[cnt]])
                else:
                    values.append([buffer[0],cutoff_distance, fld_values[cnt]])
                cnt += 1

            uf.insertTempFeatures(buffer_layer, geoms, values)

            # Style the layer
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            buffer_layer.loadNamedStyle('{}/Buffers.qml'.format(path))
            buffer_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(buffer_layer)

            # move the layer if a scenario is made
            if is_scn:
                self.iface.legendInterface().moveLayer(buffer_layer, 0)
            else:
                self.iface.legendInterface().moveLayer(buffer_layer, 2)

            self.iface.legendInterface().setLayerVisible(buffer_layer, False)
            self.refreshCanvas(buffer_layer)
            layer.removeSelection()


    def accessibility(self, is_scn):
        '''Check accessibility for all building centroids'''

        # Globals
        proj = QgsProject.instance()
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        cur_user = self.SelectUserGroupCombo.currentText()
        all_houses_layer = self.getBuildinglayer()
        all_houses = uf.getAllFeatures(all_houses_layer) #list with residential housing as points
        all_houses_list = list(all_houses.values())

        if all_houses_list > 0:
            layer = self.getSelectedLayer()
            # Check if the layer exists
            access_layer = uf.getLegendLayerByName(self.iface, "Accessibility")
            # Create one if it doesn't exist and add suffix for the scenario
            if not access_layer:
                attribs = ['number of overlapping buffers']
                types = [QtCore.QVariant.Double]
                access_layer = uf.createTempLayer('Accessibility','POINT',CRS, attribs, types)
                uf.loadTempLayer(access_layer)
            if is_scn:
                name = self.newLayerNameEdit.text()
                attribs = ['number of overlapping buffers']
                types = [QtCore.QVariant.Double]
                access_layer = uf.createTempLayer('Accessibility_{}'.format(name),'POINT',CRS, attribs, types)
                uf.loadTempLayer(access_layer)
            geoms = []
            values = []
            if is_scn:
                buffer_layer = uf.getLegendLayerByName(self.iface, 'Buffers_{}_{}'.format(cur_user, name))
            else:
                buffer_layer = uf.getLegendLayerByName(self.iface, 'Buffers_{}'.format(cur_user))
            buffers = uf.getAllFeatures(buffer_layer)
            buffer_list = list(buffers.values())

            for point in all_houses_list:

                cnt = 0
                geom = QgsGeometry(point.geometry())
                geoms.append(geom.asPoint())
                for buffer in buffer_list:
                    base_geom = QgsGeometry(point.geometry())
                    intersect_geom = QgsGeometry(buffer.geometry())
                    if base_geom.intersects(intersect_geom):
                        cnt +=1
                    else:
		                continue
                values.append([cnt])
            uf.insertTempFeatures(access_layer, geoms, values)
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            access_layer.loadNamedStyle('{}/Accessibility.qml'.format(path))
            access_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(access_layer)

            # Move the layer if a scenario is made
            if is_scn:
                self.iface.legendInterface().moveLayer(access_layer, 0)
            else:
                self.iface.legendInterface().moveLayer(access_layer, 2)
            self.iface.legendInterface().setLayerVisible(access_layer, False)
            self.refreshCanvas(access_layer)

    def startnodeprocess(self):
        isdown = self.addNodeButton.isChecked()
        cur_user = self.SelectUserGroupCombo.currentText()
        stylepath = '{}/Styles/'.format(QgsProject.instance().homePath())

        if not isdown:
            if self.addfeatures():
                print "something"

            else:

                name = self.newLayerNameEdit.text()

                self.scn_list.append(name)
                scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))
                scenario_layer.removeSelection()
        elif isdown:
            proj = QgsProject.instance()
            CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
            # load layer and duplicate it for possible changes
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")

            # Create a copy of the Transit layer for editing purposes
            self.iface.setActiveLayer(transit_layer)
            uf.duplicateLayerMem(transit_layer, "POINT", CRS, 'Transit_stops copy')
            self.new_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops copy')
            self.iface.setActiveLayer(self.new_layer)
            self.iface.legendInterface().setLayerVisible(self.new_layer, True)
            self.new_layer.loadNamedStyle('{}Transit_{}.qml'.format(stylepath, cur_user))


            self.canvas.scaleChanged.connect(self.checkMapTool)
            self.canvas.extentsChanged.connect(self.checkMapTool)


            # Make sure layer is editable
            if not self.new_layer.isEditable():
                self.new_layer.startEditing()
            self.remainingNodesLCD.display(0)
            self.setClickTool()


    def checkMapTool(self):
        maptool = self.canvas.mapTool()

        if type(maptool) == QgsMapToolEmitPoint:
            self.setClickTool()
        if type(maptool) != QgsMapToolEmitPoint:
            self.setClickTool()

    def setClickTool(self):
        # setup clicktool
        self.clickTool = QgsMapToolEmitPoint(self.canvas)
        self.clickTool.canvasClicked.connect(self.addfeatures)
        self.canvas.setMapTool(self.clickTool)

    def addfeatures(self):
        proj = QgsProject.instance()
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        cur_user = self.SelectUserGroupCombo.currentText()
        new_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops copy')
        stylepath = '{}/Styles/'.format(QgsProject.instance().homePath())
        new_layer.loadNamedStyle('{}Transit_{}.qml'.format(stylepath, cur_user))
        transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")

        # set counter
        originalfeatures = transit_layer.featureCount()
        newfeatures = new_layer.featureCount()
        diff = newfeatures - originalfeatures
        ischecked = self.addNodeButton.isChecked()

        # Add features
        if ischecked:
            self.iface.setActiveLayer(new_layer)
            self.iface.actionAddFeature().trigger()
            self.new_layer.featureAdded.connect(self.lcdCounter)
            return
        elif not ischecked:
            print 'diff', diff
            if diff == 0:
                QgsMapLayerRegistry.instance().removeMapLayer(new_layer.id())
                return True
            else:
                # Commit changes and set clicktool to pantool
                self.new_layer.featureAdded.disconnect(self.lcdCounter)
                new_layer.commitChanges()
                self.panTool = QgsMapToolPan(self.canvas)
                self.canvas.setMapTool(self.panTool)

                # Save the scenario to shapefile in /sample_data/Scenarios/{name}/
                path = "{}/Scenarios/".format(QgsProject.instance().homePath())
                name = self.newLayerNameEdit.text()
                directory = "{}/{}".format(path, name)
                if os.path.exists(directory):
                    pass
                else:
                    os.makedirs(directory)

                scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))
                if not scenario_layer:
                    uf.saveAsNewShapefile(new_layer, directory, "Transit_{}".format(name), CRS,)
                    scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))

                # Remove unnecessary copy of transit_layer
                QgsMapLayerRegistry.instance().removeMapLayer(new_layer.id())

                # Load the saved layer
                self.iface.addVectorLayer(directory, "Transit_{}".format(name), "ogr")
                scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))
                # style the layer accordingly
                scenario_layer.loadNamedStyle('{}Transit_{}.qml'.format(stylepath, cur_user))
                scenario_layer.triggerRepaint()

                # Set layer visibility and move to correct group
                self.iface.legendInterface().setLayerVisible(transit_layer, False)
                self.iface.legendInterface().moveLayer(scenario_layer, 0)
                self.iface.legendInterface().setLayerExpanded(scenario_layer, False)

                self.canvas.scaleChanged.disconnect(self.checkMapTool)
                self.canvas.extentsChanged.disconnect(self.checkMapTool)
                self.clickTool.canvasClicked.disconnect(self.addfeatures)


                # Order layers
                root = QgsProject.instance().layerTreeRoot()
                scn_group = root.children()[0]
                access = scn_group.children()[0]
                access_clone = access.clone()
                scn_group.insertChildNode(4, access_clone)
                scn_group.removeChildNode(access)
                self.refreshCanvas(scenario_layer)


    def lcdCounter(self):
        value = self.remainingNodesLCD.value()
        self.remainingNodesLCD.display(value+1)
        return

    # after adding features to layers needs a refresh (sometimes)
    def refreshCanvas(self, layer):
        if self.canvas.isCachingEnabled():
            layer.setCacheImage(None)
        else:
            self.canvas.refresh()


#######
#    Reporting functions
#######

    def reporting(self):
        proj = QgsProject.instance()
        transittypes = proj.readEntry("SpatialDecisionDockWidget", "transittypes")[0]

        # Current situation
        #self.reportTextEdit.clear()
        transit_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops')
        if not transit_layer:
            print "kutzooi"
        else:
            uf.selectFeaturesByExpression(transit_layer,"network in {}".format(transittypes))
            totalfeatures = transit_layer.selectedFeatureCount()
            transit_layer.removeSelection()

            network_types = ["'rail'", "'tram'", "'ferry'", "'metro'", "'bus'"]
            current_list = []
            for typ in network_types:
                string = '"network" = '+"{}".format(typ)
                uf.selectFeaturesByExpression(transit_layer, string)
                num = transit_layer.selectedFeatureCount()
                current_list.append(num)
                transit_layer.removeSelection()
            current_total = sum(current_list)
            current_list.append(current_total)

            # New situation(s)
            scn_dict = {}
            self.scn_list
            for tekst in self.scn_list:
                new_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(tekst))
                if new_layer == None:
                    msgBox = QtGui.QMessageBox()
                    msgBox.setText('No layers available!\nPlease create a scenario.')
                    msgBox.addButton(QtGui.QPushButton('Ok'), QtGui.QMessageBox.RejectRole)
                    ret = msgBox.exec_()

                    if ret == 0:
                        for i in range(len(self.scn_list)):
                            self.statisticsTable.removeColumn(i+2)
                        return
                else:
                    uf.selectFeaturesByExpression(new_layer,"network in {}".format(transittypes))
                    if False:
                        print "test"
                    else:
                        totalfeatures = new_layer.selectedFeatureCount()
                        new_layer.removeSelection()

                        network_types = ["'rail'", "'tram'", "'ferry'", "'metro'", "'bus'"]
                        new_list = []
                        for typ in network_types:
                            string = '"network" = '+"{}".format(typ)
                            uf.selectFeaturesByExpression(new_layer, string)
                            num = new_layer.selectedFeatureCount()
                            new_list.append(num)
                            new_layer.removeSelection()
                        new_total = sum(new_list)
                        new_list.append(new_total)
                        scn_dict[tekst] = new_list

            rows = 6
            headers = ["network type","current situation"]
            for scn_name in self.scn_list:
                headers.append(scn_name)
            cols = len(headers)
            self.statisticsTable.horizontalHeader().setVisible(True)
            self.statisticsTable.verticalHeader().setVisible(True)
            self.statisticsTable.setRowCount(rows)
            self.statisticsTable.setColumnCount(cols)

            first_col = ["rail", "tram", "ferry", "metro", "bus", "total"]
            for i, typ in enumerate(first_col):
                self.statisticsTable.setItem(i, 0, QTableWidgetItem(str(typ)))

            for i, item in enumerate(current_list):
                self.statisticsTable.setItem(i, 1, QTableWidgetItem(str(item)))

            for n, scn in enumerate(self.scn_list):
                value = scn_dict[scn]
                for i, item in enumerate(value):
                    self.statisticsTable.setItem(i, n+2, QTableWidgetItem(str(item)))

            self.statisticsTable.setHorizontalHeaderLabels(headers)


    def saveTable(self):
        path = QtGui.QFileDialog.getSaveFileName(self, 'Save File', '', 'CSV(*.csv)')
        if path:
            with open(unicode(path), 'wb') as stream:
                # open csv file for writing
                writer = csv.writer(stream)
                # write header
                header = []
                for column in range(self.statisticsTable.columnCount()):
                    item = self.statisticsTable.horizontalHeaderItem(column)
                    header.append(unicode(item.text()).encode('utf8'))
                writer.writerow(header)
                # write data
                for row in range(self.statisticsTable.rowCount()):
                    rowdata = []
                    for column in range(self.statisticsTable.columnCount()):
                        item = self.statisticsTable.item(row, column)
                        if item is not None:
                            rowdata.append(
                                unicode(item.text()).encode('utf8'))
                        else:
                            rowdata.append('')
                    writer.writerow(rowdata)

    # saving the current screen
    def saveMap(self):
        dir = "{}/Images/".format(QgsProject.instance().homePath())
        path = QtGui.QFileDialog.getSaveFileName(self, "Save map file", dir, "PNG (*.png)")
        if path.strip()!="":
            path = unicode(path)
            uf.setLastDir(path,"SDSS")
            self.canvas.saveAsImage(path,None,"PNG")

    def extractAttributeSummary(self, attribute):
        # get summary of the attribute
        summary = []
        network_types = ['een', 'twee', 'drie' ]
        layer = self.getSelectedLayer()

        # send this to the table
        self.clearTable()
        self.updateTable(network_types)


    # report window functions
    def updateReport(self,report):
        self.reportList.clear()
        self.reportList.addItems(report)

    def insertReport(self,item):
        self.reportList.insertItem(0, item)

    def clearReport(self):
        self.reportList.clear()

    # table window functions
    def updateTable(self, values):
        # takes a list of label / value pairs, can be tuples or lists. not dictionaries to control order
        #self.statisticsTable = QtGui.QTableWidget(3, 2)
        self.statisticsTable.horizontalHeader().setVisible(True)
        self.statisticsTable.verticalHeader().setVisible(True)
        self.statisticsTable.setHorizontalHeaderLabels(["network type","number"])
        self.statisticsTable.setRowCount(len(values))

        tableData = [
            ("Alice", 'blue'),
            ("Neptun", 'red'),
            ("Ferdinand", 'grey')
        ]
        for i, (name, color) in enumerate(tableData):
            nameItem = QtGui.QTableWidgetItem(name)
            coloritem = QtGui.QTableWidgetItem(color)
            self.statisticsTable.setItem(i, 0, nameItem)
            self.statisticsTable.setItem(i, 1, coloritem)
        '''if len(values) > 0:
            for i, item in enumerate(values):
                self.statisticsTable.setItem(i, 0, str(i))
                self.statisticsTable.setItem(i, 0, item)
                print i
                print item
                #self.statisticsTable.setItem(i,0,QtGui.QTableWidgetItem(i))
                #self.statisticsTable.setItem(i,1,QtGui.QTableWidgetItem(item))'''
        self.statisticsTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.statisticsTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.statisticsTable.resizeRowsToContents()

        table = self.statisticsTable
        layout = QtGui.QGridLayout()
        layout.addWidget(table, 0, 0)
        self.setLayout(layout)


    def clearTable(self):
        self.statisticsTable.clear()


