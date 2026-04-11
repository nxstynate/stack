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

"""
Stack for Blender
=================

Layer blending node for the Shader Editor.
Stacks and blends texture layers with blend modes, opacity, and masking.
"""

import bpy
from bpy.app.handlers import persistent

from .properties import StackLayerProperties
from .operators import STACK_OT_add_layer, STACK_OT_remove_layer, STACK_OT_move_layer
from .node import StackNode, _dbg
from .menu import NODE_MT_stack_custom, stack_menu_draw

classes = (
    StackLayerProperties,
    STACK_OT_add_layer,
    STACK_OT_remove_layer,
    STACK_OT_move_layer,
    StackNode,
    NODE_MT_stack_custom,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _iter_stack_nodes():
    """Yield every StackNode instance across all materials and node groups."""
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.bl_idname == "StackNodeType":
                    yield node
    for tree in bpy.data.node_groups:
        for node in tree.nodes:
            if node.bl_idname == "StackNodeType":
                yield node


# ------------------------------------------------------------------
# Load handler — restore runtime cache from persisted ID properties
#
# This handler does NOT serialize or write any data.  It only reads
# the ID properties that Blender already saved to disk and populates
# the transient CollectionProperty + rebuilds internal nodes.
# ------------------------------------------------------------------

@persistent
def _stack_load_post(filepath):
    """Restore runtime layer cache after file load."""
    _dbg("load_post handler fired")
    count = 0
    for node in _iter_stack_nodes():
        if node._restore_layers():
            node.rebuild_internals()
            count += 1
    _dbg(f"load_post: restored {count} StackNode(s)")


# ------------------------------------------------------------------
# Registration
# ------------------------------------------------------------------

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(stack_menu_draw)

    bpy.app.handlers.load_post.append(_stack_load_post)

    _dbg("Stack addon registered")


def unregister():
    if _stack_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_stack_load_post)

    bpy.types.NODE_MT_add.remove(stack_menu_draw)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    _dbg("Stack addon unregistered")
