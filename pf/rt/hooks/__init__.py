"""Hooks that let a production module emit real-time outputs without changing its logic.

A hook is a function `install(prod_main_module, emit)` called once after the module is imported; it may wrap module methods
and call `emit(kind, name, frame_id, payload)` from the module thread. Outputs are written after the frame being processed.
"""
