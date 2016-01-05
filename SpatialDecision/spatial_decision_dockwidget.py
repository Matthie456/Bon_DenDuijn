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

from qgis.gui import QgsMapTool, QgsMapToolEmitPoint, QgsMapToolPan

from . import utility_functions as uf


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

        # set up GUI operation signals
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
        self.neighborhoodCombo.activated.connect(self.setNeighborhoodlayer)
        self.buildingCentroidsCombo.activated.connect(self.setBuildinglayer)
        self.SelectUserGroupCombo.activated.connect(self.setSelectedUserGroup)
        self.transitLayerCombo.activated.connect(self.setSelectedLayer)

        # toggle layer visibility
        self.toggleBufferCheckBox.stateChanged.connect(self.toggleBufferLayer)
        self.toggleAccessibiltyCheckBox.stateChanged.connect(self.toggleAccessibilityLayer)
        self.toggleLoAccessibilityCheckBox.stateChanged.connect(self.toggleLoAccessibilityLayer)

        # reporting
        self.featureCounterUpdateButton.clicked.connect(self.updateNumberFeatures)
        self.saveMapButton.clicked.connect(self.saveMap)
        self.saveMapPathButton.clicked.connect(self.selectFile)
        self.updateAttribute.connect(self.extractAttributeSummary)

        # set current UI restrictions

        # initialisation
        self.updateLayers()
        proj = QgsProject.instance()
        proj.writeEntry("SpatialDecisionDockWidget", 'CRS' ,28992)
        print "Plugin loaded!"



        #run simple tests

    def closeEvent(self, event):
        # disconnect interface signals
        self.iface.projectRead.disconnect(self.updateLayers)
        self.iface.newProjectCreated.disconnect(self.updateLayers)

        self.closingPlugin.emit()
        event.accept()

#######
#   Data functions
#######

    def openScenario(self,filename=""):
        scenario_open = False
        #scenario_file = os.path.join('/Users/jorge/github/GEO1005','sample_data','time_test.qgs')

        scenario_file = os.path.join('{}'.format(QgsProject.instance().homePath()),'sample_data', 'projectfile.qgs')
        # check if file exists
        if os.path.isfile(scenario_file):
            self.iface.addProject(scenario_file)
            scenario_open = True
        else:
            last_dir = uf.getLastDir("SDSS")
            new_file = QtGui.QFileDialog.getOpenFileName(self, "", last_dir, "(*.qgs)")
            if new_file:
                self.iface.addProject(new_file)
                scenario_open = True
        if scenario_open:
            self.updateLayers()

    def saveScenario(self):
        self.iface.actionSaveProject().trigger

    def updateLayers(self):
        layers = uf.getLegendLayers(self.iface, 'all', 'all')
        self.transitLayerCombo.clear()
        self.neighborhoodCombo.clear()
        self.buildingCentroidsCombo.clear()
        if layers:
            layer_names = uf.getLayersListNames(layers)
            self.transitLayerCombo.addItems(layer_names)
            self.neighborhoodCombo.addItems(layer_names)
            self.buildingCentroidsCombo.addItems(layer_names)
            self.setSelectedLayer()
            self.setNeighborhoodlayer()
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
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 1200)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro', 'tram')")
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Students.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)
        elif self.SelectUserGroupCombo.currentText() == 'Elderly':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 400)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','tram','ferry')")
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Elderly.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)
        elif self.SelectUserGroupCombo.currentText() == 'Adults':
            proj.writeEntry("SpatialDecisionDockWidget", "radius", 600)
            proj.writeEntry("SpatialDecisionDockWidget", "transittypes", "('rail','metro','ferry')")
            transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            transit_layer.loadNamedStyle('{}/Transit_Adults.qml'.format(path))
            transit_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(transit_layer)

#######
#    Analysis functions
#######

    def setNeighborhoodlayer(self):
        layer_name = self.neighborhoodCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getNeighborhoodlayer(self):
        layer_name = self.neighborhoodCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        return layer

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
        state = self.toggleBufferCheckBox.checkState()

        if state == 0:
            self.iface.legendInterface().setLayerVisible(layer, False)
            self.refreshCanvas(layer)
        elif state == 2:
            self.iface.legendInterface().setLayerVisible(layer, True)
            self.refreshCanvas(layer)

    def toggleAccessibilityLayer(self):
        layer = uf.getLegendLayerByName(self.iface, 'Accessibility')
        state = self.toggleAccessibiltyCheckBox.checkState()

        if state == 0:
            self.iface.legendInterface().setLayerVisible(layer, False)
            self.refreshCanvas(layer)
        elif state == 2:
            self.iface.legendInterface().setLayerVisible(layer, True)
            self.refreshCanvas(layer)

    def toggleLoAccessibilityLayer(self):
        layer = uf.getLegendLayerByName(self.iface, 'Lack of accessibility')
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
        self.accessibilitynonservice(False)

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

    def recalculateaccessibility(self):
        '''Runs all other functions, with added nodes'''
        name = self.newLayerNameEdit.text()
        self.iface.legendInterface().addGroup(name)
        root = QgsProject.instance().layerTreeRoot()
        length = len(root.children())
        new_group = root.children()[length-1]
        new_group_clone = new_group.clone()
        root.insertChildNode(0,new_group_clone)
        root.removeChildNode(new_group)
        scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))

        self.iface.legendInterface().moveLayer(scenario_layer, 0)
        self.calculateBuffer(True)
        self.accessibility(True)
        self.accessibilitynonservice(True)


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

    def accessibilitynonservice(self, is_scn):
        # Globals
        proj = QgsProject.instance()
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        all_houses_layer = self.getBuildinglayer()
        all_houses = uf.getAllFeatures(all_houses_layer) #list with residential houses as points
        all_houses_list = list(all_houses.values())

        if all_houses_list > 0:
            building_layer = self.getBuildinglayer()
            # Check if the layer exists
            access_nonservice_layer = uf.getLegendLayerByName(self.iface, "Lack of accessibility")
            # Create one if it doesn't exist and add suffix for the scenario
            if not access_nonservice_layer:
                attribs = ['ratio']
                types = [QtCore.QVariant.Double]
                access_nonservice_layer = uf.createTempLayer('Lack of accessibility','POLYGON',CRS, attribs, types)
                uf.loadTempLayer(access_nonservice_layer)
            if is_scn:
                name = self.newLayerNameEdit.text()
                attribs = ['ratio']
                types = [QtCore.QVariant.Double]
                access_nonservice_layer = uf.createTempLayer('Lack of accessibility_{}'.format(name),'POLYGON',CRS, attribs, types)
                uf.loadTempLayer(access_nonservice_layer)
            geoms = []
            values = []
            nbhood_layer = self.getNeighborhoodlayer()
            nbhood_features = uf.getAllFeatures(nbhood_layer)
            nbhood_features_list = list(nbhood_features.values())
            fld_values = uf.getFieldValues(building_layer, 'VBO_CNT')[0]

            for nbhood_feature in nbhood_features_list:
                geom = QgsGeometry(nbhood_feature.geometry())
                geoms.append(geom)
                house_id = 0
                sumtotal = 0
                for house in all_houses_list:
                    adress_cnt = fld_values[house_id]
                    house_id += 1
                    base_geom = QgsGeometry(nbhood_feature.geometry())
                    intersect_geom = QgsGeometry(house.geometry())
                    if base_geom.intersects(intersect_geom):
                        if adress_cnt == NULL:
                            sumtotal = sumtotal + 0
                        else:
                            sumtotal = sumtotal + adress_cnt
                    else:
                        continue
                ratio = sumtotal/geom.area()
                values.append([ratio])
            uf.insertTempFeatures(access_nonservice_layer, geoms, values)

            # Style the layer
            path = '{}/styles/'.format(QgsProject.instance().homePath())
            access_nonservice_layer.loadNamedStyle('{}/Lack_of_Accessibility.qml'.format(path))
            access_nonservice_layer.triggerRepaint()
            self.iface.legendInterface().refreshLayerSymbology(access_nonservice_layer)

            # Move the layer if a scenario is made
            if is_scn:
                self.iface.legendInterface().moveLayer(access_nonservice_layer, 0)
            else:
                self.iface.legendInterface().moveLayer(access_nonservice_layer, 2)
            self.iface.legendInterface().setLayerVisible(access_nonservice_layer, False)
            self.refreshCanvas(access_nonservice_layer)

    def startnodeprocess(self):
        proj = QgsProject.instance()
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        # load layer and duplicate it for possible changes
        transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")

        # Create a copy of the Transit layer for editing purposes
        self.iface.setActiveLayer(transit_layer)
        uf.duplicateLayerMem(transit_layer, "POINT", CRS, 'Transit_stops copy')
        new_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops copy')
        self.iface.setActiveLayer(new_layer)

        # Make sure layer is editable
        if not new_layer.isEditable():
            new_layer.startEditing()
        self.addnode()

    def addnode(self):
        # load layers
        new_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops copy')
        transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")
        transit_layer.setReadOnly(True)
        new_layer.featureAdded.connect(self.addnode)

        # setup clicktool
        self.clickTool = QgsMapToolEmitPoint(self.canvas)
        self.clickTool.canvasClicked.connect(self.addfeatures)
        self.canvas.setMapTool(self.clickTool)

    def addfeatures(self):
        proj = QgsProject.instance()
        CRS = proj.readEntry("SpatialDecisionDockWidget", 'CRS')[0]
        cur_user = self.SelectUserGroupCombo.currentText()
        new_layer = uf.getLegendLayerByName(self.iface, 'Transit_stops copy')
        transit_layer = uf.getLegendLayerByName(self.iface, "Transit_stops")

        # set counter
        originalfeatures = transit_layer.featureCount()
        newfeatures = new_layer.featureCount()
        diff = newfeatures - originalfeatures
        maxnodes = self.maxNewNodesSpinbox.value()

        # Add features
        if newfeatures == originalfeatures:
            self.iface.setActiveLayer(new_layer)
            self.iface.actionAddFeature().trigger()
            return
        elif diff < maxnodes:
            self.iface.setActiveLayer(new_layer)
            self.iface.actionAddFeature().trigger()
            return
        elif diff == maxnodes:
            # Commit changes and set clicktool to pantool
            new_layer.commitChanges()
            self.panTool = QgsMapToolPan(self.canvas)
            self.canvas.setMapTool(self.panTool)

            # Save the scenario to shapefile in /sample_data/Scenarios/{name}/
            path = "{}/Scenarios/".format(QgsProject.instance().homePath())
            name = self.newLayerNameEdit.text()
            directory = "{}/{}/".format(path, name)
            if os.path.exists(directory):
                pass
            else:
                os.makedirs(directory)
            uf.saveAsNewShapefile(new_layer, directory, "Transit_{}".format(name), CRS,)

            # Remove unnecessary copy of transit_layer
            QgsMapLayerRegistry.instance().removeMapLayer(new_layer.id())

            # Load the saved layer
            self.iface.addVectorLayer(directory, "Transit_{}".format(name), "ogr")
            scenario_layer = uf.getLegendLayerByName(self.iface, "Transit_{}".format(name))
            # style the layer accordingly
            stylepath = '{}/styles/'.format(QgsProject.instance().homePath())
            scenario_layer.loadNamedStyle('{}/Transit_{}.qml'.format(stylepath, cur_user))
            scenario_layer.triggerRepaint()

            # Set layer visibility and move to correct group
            self.iface.legendInterface().setLayerVisible(transit_layer, False)
            self.iface.legendInterface().moveLayer(scenario_layer, 0)
            self.iface.legendInterface().setLayerExpanded(scenario_layer, False)

            # Order layers
            root = QgsProject.instance().layerTreeRoot()
            scn_group = root.children()[0]
            access = scn_group.children()[0]
            access_clone = access.clone()
            scn_group.insertChildNode(4, access_clone)
            scn_group.removeChildNode(access)

            self.refreshCanvas(scenario_layer)



    # after adding features to layers needs a refresh (sometimes)
    def refreshCanvas(self, layer):
        if self.canvas.isCachingEnabled():
            layer.setCacheImage(None)
        else:
            self.canvas.refresh()



#######
#    Visualisation functions
#######

#######
#    Reporting functions
#######

    # update a text edit field
    def updateNumberFeatures(self):
        layer = self.getSelectedLayer()
        if layer:
            count = layer.featureCount()
            self.featureCounterEdit.setText(str(count))

    # selecting a file for saving
    def selectFile(self):
        last_dir = uf.getLastDir("SDSS")
        path = QtGui.QFileDialog.getSaveFileName(self, "Save map file", last_dir, "PNG (*.png)")
        if path.strip()!="":
            path = unicode(path)
            uf.setLastDir(path,"SDSS")
            self.saveMapPathEdit.setText(path)

    # saving the current screen
    def saveMap(self):
        filename = self.saveMapPathEdit.text()
        if filename != '':
            self.canvas.saveAsImage(filename,None,"PNG")

    def extractAttributeSummary(self, attribute):
        # get summary of the attribute
        summary = []
        layer = self.getSelectedLayer()

        # send this to the table
        self.clearTable()
        self.updateTable(summary)

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
        self.statisticsTable.setHorizontalHeaderLabels(["Item","Value"])
        self.statisticsTable.setRowCount(len(values))
        for i, item in enumerate(values):
            self.statisticsTable.setItem(i,0,QtGui.QTableWidgetItem(str(item[0])))
            self.statisticsTable.setItem(i,1,QtGui.QTableWidgetItem(str(item[1])))
        self.statisticsTable.horizontalHeader().setResizeMode(0, QtGui.QHeaderView.ResizeToContents)
        self.statisticsTable.horizontalHeader().setResizeMode(1, QtGui.QHeaderView.Stretch)
        self.statisticsTable.resizeRowsToContents()

    def clearTable(self):
        self.statisticsTable.clear()


