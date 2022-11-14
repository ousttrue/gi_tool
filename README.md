# gi_tool

## gi_tool.generator

Python stub generator for pygobject from `gir` file.
A [pygobject-stubs](https://github.com/pygobject/pygobject-stubs/tree/master/tools) alternative.

```py
class Container(Widget):
    widget = ...

    def add(self, widget: Widget) -> None: ...
```

👇

```py

```

## usage

```
py gi_tool.generator Gtk 4.0 > C:\Python311\Lib\site-packages\gi-stubs\repository\Gtk.pyi
```