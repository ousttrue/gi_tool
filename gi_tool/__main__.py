#
# https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html
# https://palepoli.skr.jp/tips/pygobject/treeview.php
#
import gi
import pathlib
import os

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

PREFIX = pathlib.Path(os.environ['PKG_CONFIG_PATH']).parent.parent


class Window(Gtk.ApplicationWindow):

    def __init__(self, app):
        super().__init__(application=app, title='gi_tool')

        self.hpaned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)

        self.frame1 = Gtk.Frame.new()
        self.hpaned.set_start_child(self.frame1)
        self.create_treeview()
        self.frame1.set_child(self.tree)

        self.frame2 = Gtk.Frame.new()
        self.hpaned.set_end_child(self.frame2)

        self.set_child(self.hpaned)
        self.present()

    def create_treeview(self):
        # model
        self.model = Gtk.ListStore(str)

        self.tree = Gtk.TreeView(model=self.model)
        # column
        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(cell_renderer=cell, title='gir', text=0)
        self.tree.append_column(column)

    def load(self, path: pathlib.Path):
        if not path.exists():
            return

        girs = [e for e in path.iterdir() if e.suffix == '.gir']

        for e in sorted(girs, key=lambda x: x.stem):
            self.model.append([e.stem])


class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self, application_id='gi_tool')

    def do_activate(self):
        win = Window(self)
        win.load(PREFIX / 'share/gir-1.0')


app = Application()
app.run()