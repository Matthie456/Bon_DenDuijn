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
        self.selectLayerCombo.activated.connect(self.setSelectedLayer)
        self.selectAttributeCombo.activated.connect(self.setSelectedAttribute)
        # self.SelectUserGroupCombo.clicked.connect(self.functiehier)

        # analysis
        self.bufferButton.clicked.connect(self.calculateBuffer)

        # visualisation

        # reporting
        self.featureCounterUpdateButton.clicked.connect(self.updateNumberFeatures)
        self.saveMapButton.clicked.connect(self.saveMap)
        self.saveMapPathButton.clicked.connect(self.selectFile)
        self.updateAttribute.connect(self.extractAttributeSummary)

        # set current UI restrictions

        # initialisation
        self.updateLayers()
        #self.SelectUserGroupCombo.currentIndexChanged(const QString&)
        if self.SelectUserGroupCombo.currentText() == 'Students':
            radius = 800
            transittypes = ['train', 'bus', 'ferry','metro','tram']
            print radius, transittypes

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
        scenario_file = os.path.join('/Users/jorge/github/GEO1005','sample_data','time_test.qgs')
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
        self.iface.actionSaveProject()

    def updateLayers(self):
        layers = uf.getLegendLayers(self.iface, 'all', 'all')
        self.selectLayerCombo.clear()
        if layers:
            layer_names = uf.getLayersListNames(layers)
            self.selectLayerCombo.addItems(layer_names)
            self.setSelectedLayer()

    def setSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
        layer = uf.getLegendLayerByName(self.iface,layer_name)
        self.updateAttributes(layer)

    def getSelectedLayer(self):
        layer_name = self.selectLayerCombo.currentText()
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

#######
#    Analysis functions
#######
    # buffer functions

    def calculateBuffer(self):
        origins = self.getSelectedLayer().selectedFeatures()
        layer = self.getSelectedLayer()
        if origins > 0:
            cutoff_distance = 200
            buffers = {}
            for point in origins:
                geom = point.geometry()
                buffers[point.id()] = geom.buffer(cutoff_distance,12)
            # store the buffer results in temporary layer called "Buffers"
            buffer_layer = uf.getLegendLayerByName(self.iface, "Buffers")
            # create one if it doesn't exist
            if not buffer_layer:
                attribs = ['id', 'distance']
                types = [QtCore.QVariant.String, QtCore.QVariant.Double]
                buffer_layer = uf.createTempLayer('Buffers','POLYGON',layer.crs().postgisSrid(), attribs, types)
                uf.loadTempLayer(buffer_layer)
            # insert buffer polygons
            geoms = []
            values = []
            for buffer in buffers.iteritems():
                # each buffer has an id and a geometry
                geoms.append(buffer[1])
                # in the case of values, it expects a list of multiple values in each item - list of lists
                values.append([buffer[0],cutoff_distance])
            uf.insertTempFeatures(buffer_layer, geoms, values)
            self.refreshCanvas(buffer_layer)

    def calculateIntersection(self):
        # use the buffer to cut from another layer
        cutter = uf.getLegendLayerByName(self.iface, "Buffers")
        # use the selected layer for cutting
        layer = self.getSelectedLayer()
        if cutter.featureCount() > 0:
            # get the intersections between the two layers
            intersections = uf.getFeaturesIntersections(layer,cutter)
            if intersections:
                # store the intersection geometries results in temporary layer called "Intersections"
                intersection_layer = uf.getLegendLayerByName(self.iface, "Intersections")
                # create one if it doesn't exist
                if not intersection_layer:
                    geom_type = intersections[0].type()
                    if geom_type == 1:
                        intersection_layer = uf.createTempLayer('Intersections','POINT',layer.crs().postgisSrid(), [], [])
                    elif geom_type == 2:
                        intersection_layer = uf.createTempLayer('Intersections','LINESTRING',layer.crs().postgisSrid(), [], [])
                    elif geom_type == 3:
                        intersection_layer = uf.createTempLayer('Intersections','POLYGON',layer.crs().postgisSrid(), [], [])
                    uf.loadTempLayer(intersection_layer)
                # insert buffer polygons
                geoms = []
                values = []
                for intersect in intersections:
                    # each buffer has an id and a geometry
                    geoms.append(intersect)
                uf.insertTempFeatures(intersection_layer, geoms, values)
                self.refreshCanvas(intersection_layer)

    # after adding features to layers needs a refresh (sometimes)
    def refreshCanvas(self, layer):
        if self.canvas.isCachingEnabled():
            layer.setCacheImage(None)
        else:
            self.canvas.refresh()



#######
#    Visualisation functions
#######

hallo
iwdied
weifjwij

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


#TEST
