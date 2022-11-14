#
# https://python-gtk-3-tutorial.readthedocs.io/en/latest/treeview.html
# https://palepoli.skr.jp/tips/pygobject/treeview.php
#
import gi
import pathlib

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

PREFIX = pathlib.Path('C:/gnome')


class Window(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app, title='gi_tools')
        ''' widget '''
        # model
        self.model = Gtk.ListStore(str)

        self.tree = Gtk.TreeView(model=self.model)
        # column
        cell = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn(cell_renderer=cell, title='gir', text=0)
        self.tree.append_column(column)

        self.set_child(self.tree)
        self.present()

    def load(self, path: pathlib.Path):
        if not path.exists():
            return

        girs = [e for e in path.iterdir() if e.suffix == '.gir']

        for e in sorted(girs, key=lambda x: x.stem):
            self.model.append([e.stem])


class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self, application_id='gi_tools')

    def do_activate(self):
        win = Window(self)
        win.load(PREFIX / 'share/gir-1.0')


app = Application()
app.run()