import gi
import pathlib

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk

PREFIX = pathlib.Path('C:/gnome')


class Window(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.ApplicationWindow.__init__(self, application=app, title='gi_tools')
        ''' widget '''
        self.list = Gtk.ListBox()
        self.set_child(self.list)
        self.present()

    def load(self, path: pathlib.Path):
        if not path.exists():
            return

        girs = [e for e in path.iterdir() if e.suffix == '.gir']

        for e in sorted(girs, key=lambda x: x.stem):
            self.list.insert(Gtk.Label(label=e.stem), -1)


class Application(Gtk.Application):

    def __init__(self):
        Gtk.Application.__init__(self, application_id='gi_tools')

    def do_activate(self):
        win = Window(self)
        win.load(PREFIX / 'share/gir-1.0')


app = Application()
app.run()