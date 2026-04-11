# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 NXSTYNATE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# operators.py — Layer manipulation operators

from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy.types import Operator

from .node import _write_layer_props, _set_layer_count, _clear_layer_props, _suppress_updates
from .utils import find_node_by_group


class STACK_OT_add_layer(Operator):
    """Add a new layer to the stack node"""
    bl_idname = "stack_node.add_layer"
    bl_label = "Add Layer"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty()

    def execute(self, context):
        node = find_node_by_group(self.group_name)
        if node is None:
            self.report({'ERROR'}, "Node not found")
            return {'CANCELLED'}

        # Ensure runtime cache is populated.
        node.ensure_layers()

        import bpy
        from . import node as node_mod
        node_mod._suppress_updates = True
        try:
            layer = node.layers.add()
            idx = len(node.layers) - 1
            layer.layer_index = idx
            layer.layer_name = f"Layer {idx}"
            layer.blend_mode = "MIX"
            layer.opacity = 1.0
            layer.enabled = True
        finally:
            node_mod._suppress_updates = False

        # Persist to ID properties.
        _write_layer_props(node.node_tree, idx,
                           name=f"Layer {idx}", blend="MIX", opacity=1.0,
                           enabled=True, collapsed=False)
        _set_layer_count(node.node_tree, len(node.layers))

        node.add_layer_to_group(idx)
        node.rebuild_internals()
        return {'FINISHED'}


class STACK_OT_remove_layer(Operator):
    """Remove a layer from the stack node"""
    bl_idname = "stack_node.remove_layer"
    bl_label = "Remove Layer"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty()
    layer_index: IntProperty()

    def execute(self, context):
        node = find_node_by_group(self.group_name)
        if node is None:
            self.report({'ERROR'}, "Node not found")
            return {'CANCELLED'}

        node.ensure_layers()

        if len(node.layers) <= 1:
            self.report({'WARNING'}, "Cannot remove the last layer")
            return {'CANCELLED'}

        removed = self.layer_index
        num = len(node.layers)
        nt = node.node_tree

        old_to_new = {}
        for old_i in range(num):
            if old_i < removed:
                old_to_new[old_i] = old_i
            elif old_i == removed:
                old_to_new[old_i] = None
            else:
                old_to_new[old_i] = old_i - 1

        import bpy
        from . import node as node_mod
        node_mod._suppress_updates = True
        try:
            node.layers.remove(removed)
            for i, layer in enumerate(node.layers):
                layer.layer_index = i
        finally:
            node_mod._suppress_updates = False

        # Rewrite all ID properties with new indices.
        new_count = len(node.layers)
        for i, layer in enumerate(node.layers):
            _write_layer_props(nt, i,
                               name=layer.layer_name,
                               blend=layer.blend_mode,
                               opacity=layer.opacity,
                               enabled=layer.enabled,
                               collapsed=layer.collapsed)

        # Clean up leftover props from the old last index.
        _clear_layer_props(nt, num - 1)
        _set_layer_count(nt, new_count)

        node.rebuild_group(old_to_new=old_to_new)
        return {'FINISHED'}


class STACK_OT_move_layer(Operator):
    """Move a layer up or down in the stack"""
    bl_idname = "stack_node.move_layer"
    bl_label = "Move Layer"
    bl_options = {'REGISTER', 'UNDO'}

    group_name: StringProperty()
    layer_index: IntProperty()
    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        node = find_node_by_group(self.group_name)
        if node is None:
            self.report({'ERROR'}, "Node not found")
            return {'CANCELLED'}

        node.ensure_layers()

        idx = self.layer_index
        num = len(node.layers)

        if self.direction == 'UP' and idx > 0:
            new_idx = idx - 1
        elif self.direction == 'DOWN' and idx < num - 1:
            new_idx = idx + 1
        else:
            return {'CANCELLED'}

        old_to_new = list(range(num))
        old_to_new[idx] = new_idx
        old_to_new[new_idx] = idx

        import bpy
        from . import node as node_mod
        node_mod._suppress_updates = True
        try:
            node.layers.move(idx, new_idx)
            for i, layer in enumerate(node.layers):
                layer.layer_index = i
        finally:
            node_mod._suppress_updates = False

        # Rewrite all ID properties with new order.
        nt = node.node_tree
        for i, layer in enumerate(node.layers):
            _write_layer_props(nt, i,
                               name=layer.layer_name,
                               blend=layer.blend_mode,
                               opacity=layer.opacity,
                               enabled=layer.enabled,
                               collapsed=layer.collapsed)

        node.rebuild_group(old_to_new=old_to_new)
        return {'FINISHED'}
