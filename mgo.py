# mGo - by Stuart Tozer and Antonio Neto

from PySide import QtCore, QtGui, QtUiTools
import mari
import mari.examples.mgo_main as mgo_main
import os
import hashlib
import socket

import mari.examples.mgo_materialiser_wip
reload(mari.examples.mgo_materialiser_wip)

ROOT_PATH = mari.resources.path(mari.resources.EXAMPLES)
ICONS_PATH = mari.resources.path(mari.resources.ICONS)
MGO_PATH = ROOT_PATH + "/mGo"
MAIN_UI_PATH = MGO_PATH + "/mgo_ui.ui"
MATERIALISER_UI_PATH = MGO_PATH + "/materialiser_ui.ui"
MGO_USERPATH = mari.resources.path(mari.resources.USER) + "/mGo"
PRESETS_PATH = MGO_USERPATH + "/Presets"

SUPPORTED_SHADERS = ['AiStandard', 'VRayMtl', 'RedshiftArchitectural']

materialiser_ui = None


class MgoUI(QtGui.QWidget):
    def __init__(self, ui_file):
        QtGui.QWidget.__init__(self)
        self.ui = ui_file
        self.main = mgo_main.MgoMain()
        self.materialiser = mari.examples.mgo_materialiser_wip
        label = QtGui.QLabel()
        self.mGo_palette = mari.palettes.create("mGo", label)
        self.mGo_palette.setBodyWidget(self.ui)

        self.output_path = None
        self.output_description_path = None
        self.export_app = None
        self.geo = None
        self.geo_name = None
        self.shader = None

        self.ui.mgo_icon.setPixmap(ICONS_PATH + '/mGo_green.png')
        self.ui.materialiser_btn.setIcon(QtGui.QPixmap(ICONS_PATH + '/shaderPresets.png'))
        self.ui.exportAttrs_chk.setIcon(QtGui.QIcon(ICONS_PATH + '/Attributes.png'))
        self.ui.exportChannels_chk.setIcon(QtGui.QIcon(ICONS_PATH + '/Channel.png'))
        self.ui.exportGeo_chk.setIcon(QtGui.QIcon(ICONS_PATH + '/Geo.png'))
        self.ui.browseDir_btn.setIcon(QtGui.QPixmap(ICONS_PATH + '/Folder.png'))
        self.ui.sendToApp_btn.setIcon(QtGui.QPixmap(ICONS_PATH + '/Forward.png'))
        self.ui.exportDescription_btn.setIcon(QtGui.QPixmap(ICONS_PATH + '/script.png'))

        self.ui.materialiser_btn.clicked.connect(self.open_materialiser)
        self.ui.browseDir_btn.clicked.connect(self.browse_output_dir)
        self.ui.sendToApp_btn.clicked.connect(self.send_to_app)
        self.ui.outputPath_edit.editingFinished.connect(self.set_output_dir)

    def print_message(self, message_str):
        print(message_str)
        mari.app.log(message_str)

    def open_materialiser(self):
        global materialiser_ui
        materialiser_ui = self.materialiser.MaterialiserUI(self)
        materialiser_ui.ui.show()

    def browse_output_dir(self):
        directory = str(QtGui.QFileDialog.getExistingDirectory(dir=self.ui.outputPath_edit.text(),
                                                               caption="Choose Assets Export Directory"))
        if directory:
            self.ui.outputPath_edit.setText(directory)
            self.set_output_dir()

    def set_output_dir(self):
        directory = self.ui.outputPath_edit.text()
        if directory:
            directory = directory.replace("\\", "/")
            self.output_path = directory
            self.output_description_path = self.output_path + "/mGo " + mari.projects.current().name() + "_description.mgo"
            self.ui.outputPath_edit.setText(directory)

    def send_to_app(self):
        mgo_data = []
        if not mari.projects.current():
            self.print_message("Please open a project first")
            return

        # make sure atleast one checkbox is enabled in order to continue with export
        if not self.ui.exportAttrs_chk.isChecked() and not self.ui.exportChannels_chk.isChecked()\
                and not self.ui.exportGeo_chk.isChecked():

            self.print_message("- EXPORT CANNOT PROCEED - \nplease enable at least one export option")
            return

        send_mode = self.ui.sendMode_cbox.currentText()
        geo_list = self.get_geo_list(send_mode)

        for geo in geo_list:
            self.geo = geo

            # the main export function... for each shader the shader data is returned and appended to 'mgo_data'
            mgo_data.append(self.mgo_export())

        self.main.json_write(mgo_data, self.output_description_path)
        self.send_message_to_app()

    def mgo_export(self):
        self.set_output_dir()
        self.shader = self.geo.currentShader()

        try:
            shader_type = self.shader.getParameter("shadingNode")
            shader_name = self.cleanup_name(self.shader.name())

        except:
            self.print_message("Current shader not supported by mGo")
            return

        self.print_message("--------------------------------------------------")
        self.print_message("EXPORTING SHADER(S) FOR: " + self.geo.name())
        self.print_message("--------------------------------------------------\n")
        self.print_message("SHADER NAME: " + shader_name)
        self.print_message("SHADER TYPE: " + shader_type + "\n")

        # export data
        data = dict()
        data['shader name'] = shader_name
        data['shader type'] = shader_type
        data['attributes'] = {}
        data['channels'] = {}
        data['geo name'] = self.geo.name()
        data['geo path'] = None
        data['geo import'] = False
        data['channels import'] = False
        data['attributes import'] = False
        data['filter type'] = self.ui.filterType_cbox.currentText()
        data['udim'] = 'multi'  # assumed

        # if geo only has one udim patch, store it in 'udim' key
        if len(self.geo.patchList()) == 1:
            data['udim'] = self.geo.patchList()[0].name()

        # collect and export data for each checked data type
        self.print_message("export attributes: " + str(self.ui.exportAttrs_chk.isChecked()))
        if self.ui.exportAttrs_chk.isChecked():
            data = self.do_attributes_export(data)

        self.print_message("export channels: " + str(self.ui.exportChannels_chk.isChecked()))
        if self.ui.exportChannels_chk.isChecked():
            data = self.do_channels_export(data)

        self.print_message("export channels: " + str(self.ui.exportGeo_chk.isChecked()))
        if self.ui.exportGeo_chk.isChecked():
            data = self.do_geo_export(data)

        # write .mgo file
        mgo_file_path = (self.output_path + "/" + mari.projects.current().name() + " mGo/" +
                         self.geo.name() + "_" + shader_name + ".mgo").replace('\\', '/')

        self.main.json_write(data, mgo_file_path)

        self.print_message("--- Data Successfully Exported ---")
        self.print_message(".mgo file saved in folder:")
        self.print_message(mgo_file_path)

        return mgo_file_path  # filepath returned to main export function


    def do_channels_export(self, data):
        data['channels import'] = True
        inputs_list = self.shader.inputList()

        for channel in inputs_list:
            if channel[1]:    # if input has a channel
                input_name = channel[0]
                channel_name = self.cleanup_name(channel[1].name())
                channel_depth = int(channel[1].depth())

                if channel_depth == 8:
                    file_extension = self.ui.eightBitFormat_cbox.currentText()
                else:
                    file_extension = self.ui.thirtyTwoBitFormat_cbox.currentText()

                channel_output_path = (self.output_path + "/" + self.geo.name() + "_" + channel_name + ".$UDIM." +
                                       file_extension).replace('\\', '/')

                self.print_message("Exporting: " + channel_name + ", " + str(channel_depth) + " bit" + "\n")
                data['channels'][input_name] = [channel_name, channel_output_path, channel_depth]

                # export only new or updated patches
                altered_patches = self.compare_hashes(channel[1], channel_name, file_extension)
                if altered_patches[0]:
                    if file_extension == "exr":
                        channel[1].exportImagesFlattened(channel_output_path, 0, altered_patches[0], {"compression": "zip"})
                    else:
                        channel[1].exportImagesFlattened(channel_output_path, 0, altered_patches[0])

                self.print_message("-- finished --\n")

        return data

    def do_attributes_export(self, data):
        data['attributes import'] = True
        parameters = self.shader.parameterNameList()
        for parameter in parameters:
            value = self.shader.getParameter("%s" % parameter)
            value_type = self.convert_type(type(value))
            if value_type == 'float3':  # convert mari color object to rgb values
                value = value.rgb()

            data['attributes'][parameter] = [value, value_type]

        return data

    def do_geo_export(self, data):
        data['geo import'] = True
        data['geo path'] = self.geo.currentVersion().path()
        self.print_message("geo path: " + self.geo.currentVersion().path())

        return data

    def compare_hashes(self, channel, channel_name, file_extension):
        metadata_index = 0
        uv_indexes = []
        udims = []
        hashes = []

        # check if channel has metadata stored from a previous mGo export
        if channel.hasMetadata("Hash"):
            channel_metadata = channel.metadataItemList("Hash")

            # generate the first hash based on the channel/system colorspaces
            generated_hash = self.generate_hash(channel, metadata_index, 0, 0)
            hashes.append(generated_hash)

            # compare the new hash with the first element in the metadata list
            if generated_hash == channel_metadata[metadata_index]:
                for patch in self.geo.patchList():
                    metadata_index += 1
                    generated_hash = self.generate_hash(channel, metadata_index, patch.uvIndex(), patch.name())
                    hashes.append(generated_hash)

                    # test whether file exists, then test
                    file_path = (self.output_path + "/" + self.geo.name() + "_" + channel_name + "." + patch.name() +
                                 "." + file_extension).replace('\\', '/')

                    if not os.path.exists(file_path) and not generated_hash == channel_metadata[metadata_index]:
                        uv_indexes.append(patch.uvIndex())
                        udims.append(patch.name())
                    else:
                        self.print_message("Patch " + patch.name() + " has not been altered... skipping export")
            else:
                for patch in self.geo.patchList():
                    metadata_index += 1
                    uv_indexes.append(patch.uvIndex())
                    udims.append(patch.name())
                    generated_hash = self.generate_hash(channel, metadata_index, patch.uvIndex(), patch.name())
                    hashes.append(generated_hash)
        else:
            # create initial metadata for the channel
            channel.setMetadata("Hash", "")
            channel.setMetadataEnabled("Hash", False)

            # generate the first hash based on the channel/system colorspaces
            generated_hash = self.generate_hash(channel, metadata_index, 0, 0)
            hashes.append(generated_hash)

            for patch in self.geo.patchList():
                metadata_index += 1
                uv_indexes.append(patch.uvIndex())
                udims.append(patch.name())
                generated_hash = self.generate_hash(channel, metadata_index, patch.uvIndex(), patch.name())
                hashes.append(generated_hash)

        # update channel metadata with the new hashes
        channel.setMetadataItemList("Hash", hashes)

        return [uv_indexes, udims]

    def generate_hash(self, channel, metadata_index, uv_index, udim):
        sha256 = hashlib.sha256()
        hash_data = []
        # the first time you got in here store the strings related to colorspace settings
        if metadata_index == 0:
            hash_data.append(channel.colorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_NATIVE))
            hash_data.append(channel.colorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_OUTPUT))
            hash_data.append(channel.colorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_WORKING))
            hash_data.append(channel.scalarColorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_NATIVE))
            hash_data.append(channel.scalarColorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_OUTPUT))
            hash_data.append(channel.scalarColorspaceConfig().resolveColorspace(
                mari.ColorspaceConfig.ColorspaceStage.COLORSPACE_STAGE_WORKING))
            sha256.update(str(hash_data))

        else:
            uv_index = int(uv_index)
            udim = int(udim)
            hash_data.append(channel.hash(udim))
            hash_data.append(channel.imageHash(udim))

            # look in each visible layer of the patch and get its hash
            layers = channel.layerList()

            for layer in layers:
                if layer.isVisible():
                    if layer.isGroupLayer():
                        # the function must call itself to generate the HASH for any layers inside the group layer
                        hash_data.append(self.generate_hash(layer.layerStack(), metadata_index, uv_index, udim) +
                                         str(layer.isMaskEnabled()))

                    elif layer.isPaintableLayer():
                        hash_data.append(layer.imageSet().image(uv_index).hash())
                    else:
                        hash_data.append(layer.hash(udim))
                        hash_data.append(layer.imageHash(udim))

                    # both masks and MaskStack are recognized by '.hasMask()'. They also may be disabled
                    if layer.hasMask() and not layer.hasMaskStack():
                        # Exception Handle for nested masks in the nodegraph. a mask has to be single paint node!
                        # If not it has to be properly merged with nodes to become a maskStack instead
                        try:
                            hash_data.append(layer.maskImageSet().image(uv_index).hash() + str(layer.isMaskEnabled()))
                        except:
                            pass

                    elif layer.hasMaskStack():
                        # MaskStacks can have their own layers, which could be paintable layers, procedurals, etc...
                        # The function must call itself to generate the HASH for any layers inside the MaskStack
                        hash_data.append(self.generate_hash(layer.maskStack(), metadata_index, uv_index, udim) +
                                         str(layer.isMaskEnabled()))

            sha256.update(str(hash_data))

        return sha256.hexdigest()

    def send_message_to_app(self):
        self.export_app = self.ui.exportApp_cbox.currentText()

        if self.ui.appHost_cbox.currentText() == "Local Host Only":
            app_host = 'localhost'
        elif self.ui.appHost_cbox.currentText() == "Network Host":
            app_host = 'IPS[0]'  # fix
        else:
            app_host = self.ui.appHost_cbox.currentText()

        try:
            maya = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            maya.connect((app_host, 6010))
            print "sending..."
            maya.send('import mgo_maya; reload(mgo_maya); mgo_maya.MgoMaya.Import("%s")'
                      % self.output_description_path)
            maya.close()
            self.print_message("--- Exported to Maya ---")

        except socket.error:
            self.print_message("--- ALERT --- You must have to open Maya's port 6010 first!")
            # '\n' command does not work here! Have to manully space out phrases to get a proper line break.
            message = mari.actions.create('open port',
                                          'mari.utils.message("Scene Description & Shader Data saved in the mGo Folder.                                                 If you want to automate the Maya import process make sure port 6010 is open in Maya - See Instructions for Help.")')
            message.trigger()

    def cleanup_name(self, name):
        invalid_characters = ".,(){}[]&$%&?^/|!-:@#*+ "
        for character in invalid_characters:
            name = name.replace(character, "_")
        return name

    def get_geo_list(self, send_mode):
        geo_list = []
        if send_mode == 'Current Object':
            geo_list = [mari.geo.current()]

        elif send_mode == 'Visible Objects':
            for geo in mari.geo.list():
                if geo.isVisible():
                    geo_list.append(geo)

        elif send_mode == 'All Objects':
            for geo in mari.geo.list():
                geo_list.append(geo)

        return geo_list

    def convert_type(self, data_type):
        if data_type == mari.Color:
            data_type = 'float3'
        elif data_type == float:
            data_type = 'float'
        elif data_type == unicode:
            data_type = 'enum'
        elif data_type == bool:
            data_type = 'bool'
        elif data_type == int:
            data_type = 'int'

        return data_type


def run():
    global UI
    load_ui = QtUiTools.QUiLoader().load(MAIN_UI_PATH)
    UI = MgoUI(load_ui)
    UI.mGo_palette.show()


try:
    mari.palettes.remove('mGo')
except:
    pass

run()
