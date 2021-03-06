# -*- coding: utf-8 -*-
# Copyright (c) 2016, French National Center for Scientific Research (CNRS)
# Distributed under the (new) BSD License. See LICENSE for more info.

__version__ = "0.2.0"

try:
    import PyQt5
    HAVE_PyQt5 = True
except ImportError:
    HAVE_PyQt5 = False

try:
    import RPi.GPIO as GPIO
    HAVE_GPIO = True
except ImportError:
    HAVE_GPIO = False


if HAVE_PyQt5:
    from .core_gui import PyAudio_protocol
    print("Gui Mode")
    from .test_tools import list_audio_device, show_device_sr, test_simple_syncro_parallel
    from .test_tools import get_sin

if HAVE_GPIO:
    from .core_rpi_nogui import PyAudio_protocol_rpi
