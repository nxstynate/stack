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

from .properties import StackLayerProperties
from .operators import STACK_OT_add_layer, STACK_OT_remove_layer, STACK_OT_move_layer
from .node import StackNode
from .menu import NODE_MT_stack_custom, stack_menu_draw

classes = (
    StackLayerProperties,
    STACK_OT_add_layer,
    STACK_OT_remove_layer,
    STACK_OT_move_layer,
    StackNode,
    NODE_MT_stack_custom,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_add.append(stack_menu_draw)


def unregister():
    bpy.types.NODE_MT_add.remove(stack_menu_draw)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
