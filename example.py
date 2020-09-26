#!/usr/bin/env python3


import ctypes
from pathlib import Path

import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk

gi.require_version('GL', '1.0')
from OpenGL import GL, GLX

from mpv import MPV, MpvRenderContext, OpenGlCbGetProcAddrFn


def get_process_address(_, name):
    address = GLX.glXGetProcAddress(name.decode("utf-8"))
    return ctypes.cast(address, ctypes.c_void_p).value


class MainClass(Gtk.Window):

    def __init__(self, media):
        super(MainClass, self).__init__()
        self.media = media
        self.set_default_size(600, 400)
        self.connect("destroy", self.on_destroy)

        frame = Gtk.Frame()
        self.area = OpenGlArea()
        self.area.connect("realize", self.play)
        frame.add(self.area)
        self.add(frame)
        self.show_all()

    def on_destroy(self, widget, data=None):
        Gtk.main_quit()

    def play(self, arg1):
        self.resize(1920, 1080)

        path = Path(self.media)
        if not path.exists():
            self.set_title(f"Video '{self.media}' does not exist")
        else:
            self.set_title(str(path.absolute()))
            self.area.play(self.media)


class OpenGlArea(Gtk.GLArea):

    def __init__(self, **properties):
        super().__init__(**properties)

        self._proc_addr_wrapper = OpenGlCbGetProcAddrFn(get_process_address)

        self.ctx = None
        self.mpv = MPV(
            input_default_bindings=True,
            input_vo_keyboard=True,
            osc=True
            # log_handler=print,
            # loglevel='debug'
        )

        self.connect("realize", self.on_realize)
        self.connect("render", self.on_render)
        self.connect("unrealize", self.on_unrealize)

        self.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        # self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        # self.add_events(Gdk.EventMask.STRUCTURE_MASK)
        # self.add_events(Gdk.EventMask.SCROLL_MASK)

        self.connect("motion-notify-event", self.on_mouse_move_event)
        self.connect("button-press-event", self.on_button_press_event)
        self.connect("button-release-event", self.on_button_release_event)

    def on_realize(self, area):
        self.make_current()
        self.ctx = MpvRenderContext(self.mpv, 'opengl',
                                    opengl_init_params={'get_proc_address': self._proc_addr_wrapper})
        self.ctx.update_cb = self.wrapped_c_render_func

    def on_unrealize(self, arg):
        self.ctx.free()
        self.mpv.terminate()

    def wrapped_c_render_func(self):
        GLib.idle_add(self.call_frame_ready, None, GLib.PRIORITY_HIGH)

    def call_frame_ready(self, *args):
        if self.ctx.update():
            self.queue_render()

    def on_render(self, arg1, arg2):
        if self.ctx:
            factor = self.get_scale_factor()
            rect = self.get_allocated_size()[0]

            width = rect.width * factor
            height = rect.height * factor

            fbo = GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING)
            self.ctx.render(flip_y=True, opengl_fbo={'w': width, 'h': height, 'fbo': fbo})
            return True
        return False

    def play(self, media):
        self.mpv.play(media)

    def on_mouse_move_event(self, _, event) -> bool:
        scale_factor = self.get_scale_factor()
        self.mpv.command_async("mouse", int(event.x * scale_factor), int(event.y * scale_factor))
        return True

    def on_button_press_event(self, _, event) -> bool:
        btn = event.button

        # PRESS = "keypress"
        # DOWN = "keydown"
        # UP = "keyup"

        if btn == 1:  # MouseButton LEFT:
            self.mpv.command_async("keydown", "MOUSE_BTN" + str(0))
            return True

        return False

    def on_button_release_event(self, _: Gtk.Widget, event) -> bool:
        btn = event.button

        if btn == 1:
            self.mpv.command_async("keyup", "MOUSE_BTN" + str(0))
            return True

        return False


if __name__ == '__main__':
    import locale

    locale.setlocale(locale.LC_NUMERIC, 'C')

    # 1. Steps to reproduce: run this script with a longer video
    # 2. Move the mouse and seek until you get 'MemoryError: ('mpv event queue full' ...)'

    application = MainClass(media='my-long-video.mkv')
    Gtk.main()
