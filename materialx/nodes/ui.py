# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright 2022, AMD

from pathlib import Path
import traceback

import MaterialX as mx

import bpy
from bpy_extras.io_utils import ImportHelper, ExportHelper

from .. import utils
from ..preferences import addon_preferences

from ..utils import logging
log = logging.Log('nodes.ui')


class NODES_OP_import_file(bpy.types.Operator, ImportHelper):
    bl_idname = utils.with_prefix('nodes_import_file')
    bl_label = "Import from File"
    bl_description = "Import MaterialX node tree from .mtlx file"

    filename_ext = ".mtlx"
    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for importing MaterialX node tree from .mtlx file",
        maxlen=1024, subtype="FILE_PATH"
    )
    filter_glob: bpy.props.StringProperty(default="*.mtlx", options={'HIDDEN'}, )

    def execute(self, context):
        mx_node_tree = context.space_data.edit_tree
        mtlx_file = Path(self.filepath)

        doc = mx.createDocument()
        search_path = mx.FileSearchPath(str(mtlx_file.parent))
        search_path.append(str(utils.MX_LIBS_DIR))
        try:
            mx.readFromXmlFile(doc, str(mtlx_file))
            mx_node_tree.import_(doc, mtlx_file)

        except Exception as e:
            log.error(traceback.format_exc(), mtlx_file)
            return {'CANCELLED'}

        return {'FINISHED'}


class NODES_OP_export_file(bpy.types.Operator, ExportHelper):
    bl_idname = utils.with_prefix('nodes_export_file')
    bl_label = "Export to File"
    bl_description = "Export MaterialX node tree to .mtlx file"

    # region properties
    filename_ext = ".mtlx"

    filepath: bpy.props.StringProperty(
        name="File Path",
        description="File path used for exporting MaterialX node tree to .mtlx file",
        maxlen=1024,
        subtype="FILE_PATH"
    )
    filter_glob: bpy.props.StringProperty(
        default="*.mtlx",
        options={'HIDDEN'},
    )
    is_export_deps: bpy.props.BoolProperty(
        name="Include dependencies",
        description="Export used MaterialX dependencies",
        default=False
    )
    is_export_textures: bpy.props.BoolProperty(
        name="Export bound textures",
        description="Export bound textures to corresponded folder",
        default=True
    )
    texture_dir_name: bpy.props.StringProperty(
        name="Texture folder name",
        description="Texture folder name used for exporting files",
        default='textures',
        maxlen=1024
    )
    # endregion

    def execute(self, context):
        mx_node_tree = context.space_data.edit_tree
        doc = mx_node_tree.export()
        if not doc:
            log.warn("Incorrect node tree to export", mx_node_tree)
            return {'CANCELLED'}

        utils.export_mx_to_file(doc, self.filepath,
                                mx_node_tree=mx_node_tree,
                                # is_export_deps=self.is_export_deps,
                                is_export_textures=self.is_export_textures,
                                texture_dir_name=self.texture_dir_name)

        return {'FINISHED'}

    def draw(self, context):
        # self.layout.prop(self, 'is_export_deps')

        col = self.layout.column(align=False)
        col.prop(self, 'is_export_textures')

        row = col.row()
        row.enabled = self.is_export_textures
        row.prop(self, 'texture_dir_name', text='')

    @staticmethod
    def enabled(context):
        return bool(context.space_data.edit_tree.output_node)
