# mGo - by Stuart Tozer and Antonio Neto

import mari
from PySide import QtCore, QtGui, QtUiTools
import os


ROOT_PATH = mari.resources.path(mari.resources.EXAMPLES)
ICONS_PATH = mari.resources.path(mari.resources.ICONS)
MGO_PATH = ROOT_PATH + "/mGo"
MAIN_UI_PATH = MGO_PATH + "/mgo_ui.ui"
MATERIALISER_UI_PATH = MGO_PATH + "/materialiser_ui.ui"
MGO_USERPATH = mari.resources.path(mari.resources.USER) + "/mGo"
PRESETS_PATH = MGO_USERPATH + "/Presets"

SUPPORTED_SHADERS = ['AiStandard', 'VRayMtl', 'RedshiftArchitectural']


class MaterialiserUI(QtGui.QWidget):
    def __init__(self, parent):
        # import mari.examples.mgo_materialiser_wip as materialiser
        QtGui.QWidget.__init__(self)
        self.ui = QtUiTools.QUiLoader().load(MATERIALISER_UI_PATH)
        self.materialiser = MgoMaterialiser()
        self.parent = parent
        self.shader = None
        self.shader_type = None
        self.library = None
        self.preset = '--- Select Preset ---'
        self.update_preview = False

        for shader in SUPPORTED_SHADERS:
            self.ui.shader_cbox.addItem(shader)
            if not os.path.exists(PRESETS_PATH + "/" + shader):
                os.makedirs(PRESETS_PATH + "/" + shader)

        self.ui.shader_cbox.currentIndexChanged.connect(self.update_libraries)
        self.ui.library_cbox.currentIndexChanged.connect(self.update_presets)
        self.ui.preset_cbox.currentIndexChanged.connect(self.preview_shader)
        self.ui.addChannels_btn.clicked.connect(self.create_channels)
        self.ui.savePreset_btn.clicked.connect(self.export_preset)

        self.update_libraries()

    def update_libraries(self):
        self.ui.library_cbox.clear()
        self.shader_type = self.ui.shader_cbox.currentText()
        library_path = PRESETS_PATH + "/" + self.shader_type
        libraries = os.listdir(library_path)

        self.ui.library_cbox.addItems(libraries)
        self.library = self.ui.library_cbox.currentText()

        self.update_presets()

    def update_presets(self):
        self.ui.preset_cbox.clear()
        self.ui.preset_cbox.addItem('--- Select Preset ---')
        self.library = self.ui.library_cbox.currentText()
        presets_path = PRESETS_PATH + "/" + self.shader_type + "/" + self.library
        presets = os.listdir(presets_path)

        for preset in presets:
            self.ui.preset_cbox.addItem(preset.replace('.pre', ''))

        self.ui.preset_cbox.findText('--- Select Preset ---')

    def preview_shader(self):
        self.preset = self.ui.preset_cbox.currentText()
        if self.preset == '--- Select Preset ---':
            return

        preset_path = PRESETS_PATH + "/" + self.shader_type + "/" + self.library + "/" + self.preset + ".pre"
        preset = self.parent.main.json_read(preset_path)

        self.shader = self.materialiser.preview_shader(preset, self.update_preview)
        self.update_preview = True  # while previewing subsequent shaders, shader attributes will override previous ones
        self.update_inputs_list()

    def update_inputs_list(self):
        self.ui.inputs_list.clear()

        shader_inputs = self.shader.inputNameList()
        for i in shader_inputs:
            if (i != "ThicknessMap") and (i != "Normal") and (i != "Displacement") and (i != "Vector"):
                self.ui.inputs_list.addItem(i)

    def create_channels(self):
        self.update_preview = False
        channel_res = self.ui.channelRes_cbox.currentText()
        bit_depth = self.ui.bitDepth_cbox.currentText()

        if bit_depth == "8 Bit":
            bit_depth = 8
        else:
            bit_depth = 16

        inputs_list = [str(x.text()) for x in self.ui.inputs_list.selectedItems()]
        self.materialiser.create_channels(self.shader, inputs_list, channel_res, bit_depth)

    def export_preset(self):
        geo = mari.geo.current()
        export_shader = geo.currentShader()

        # If we can't get the shaderType of the export shader, then shader not supported by mGo...
        try:
            shader_type = str(export_shader.getParameter("shadingNode"))
        except:
            print "ERROR - mGo doesn't support export of the current selected shader type"
            return

        presets_path = PRESETS_PATH + "/" + self.shader_type + "/" + self.library
        output_path = str(QtGui.QFileDialog.getSaveFileName(caption="Save Preset", dir=presets_path, option=0)[0])

        if output_path:
            self.materialiser.export_preset(export_shader, output_path, shader_type)


class MgoMaterialiser(object):
    def __init__(self):
        self.preset = None
        self.shader = None
        self.geo = None

    def preview_shader(self, preset, update_preview):
        self.preset = preset    # the json preset data
        self.geo = mari.geo.current()
        current_shader = self.geo.currentShader()
        previous_shader = None

        if update_preview:
            if current_shader.getParameter("shadingNode") == self.preset['shader type']:
                self.shader = current_shader
                self.set_shader_attributes()
            else:
                previous_shader = current_shader
                self.shader = self.create_shader()
        else:
            self.shader = self.create_shader()

        self.set_shader_attributes()

        if previous_shader:
            self.geo.removeShader(previous_shader)

        return self.shader

    def create_shader(self):
        shader = self.geo.createShader(self.preset['shader name'], "Lighting/Standalone/%s" % self.preset['shader type'])
        shader.makeCurrent()
        return shader

    def set_shader_attributes(self):
        attributes = self.preset['attributes']
        for attr, value in attributes.iteritems():
            # value index[0] = value (eg. 0.23),
            # value index[1] = datatype (eg.'float')
            if value[1] == 'enum':
                pass  # TODO
            elif value[1] == 'float3':
                # must convert to 'mari color'
                parameter = mari.Color(value[0][0], value[0][1], value[0][2])
                self.shader.setParameter("%s" % attr, parameter)
            else:
                self.shader.setParameter("%s" % attr, value[0])

        self.shader.setName(self.preset['shader name'])

    def create_channels(self, shader, inputs_list, channel_res, bit_depth):
        for input_channel in inputs_list:
            channel_name = shader.name() + "_" + input_channel
            channel_list = self.geo.channelList()
            channel_list = [chan.name() for chan in channel_list]

            if channel_name in channel_list:
                print "skipping channel as already created..."
            else:
                parameter = shader.getParameter(str(input_channel))
                if type(parameter) == float:
                    parameter = mari.Color(parameter, parameter, parameter)

                channel = self.geo.createChannel(channel_name, int(channel_res), int(channel_res), int(bit_depth))
                channel_layer = channel.createProceduralLayer("Reference_Colour", "Basic/Color")
                channel_layer.setProceduralParameter("Color", parameter)
                shader.setInput(input_channel, channel)

    def export_preset(self, export_shader, output_path, shader_type):
        data = {}
        parameters_list = []
        data['shader name'] = export_shader.name()
        data['shader type'] = shader_type
        data['attributes'] = {}

        parameters = export_shader.parameterNameList()

        for parameter in parameters:
            value = (export_shader.getParameter("%s" % parameter))
            value_type = type(value)
            if value_type == mari.Color:
                value = value.rgb()

            p_list = [parameter, value, value_type]
            parameters_list.append(p_list)

        print parameters_list



