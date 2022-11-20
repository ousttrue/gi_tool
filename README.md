# gi_tool

## gi_tool.girstub

Python stub generator for pygobject from `gir` file.
A [pygobject-stubs](https://github.com/pygobject/pygobject-stubs/tree/master/tools) alternative.

```py
   def insert_column(self, column: TreeViewColumn, position: int) -> int: ...
```

👇

More rich annotation.

```py
    def insert_column(self, column: 'TreeViewColumn', position: int) -> int:
        """This inserts the @column into the @tree_view at @position.  If @position is
-1, then the column is inserted at the end. If @tree_view has
“fixed_height” mode enabled, then @column must have its “sizing” property
set to be GTK_TREE_VIEW_COLUMN_FIXED."""
        ...
```

## usage

Generate a stub from a gir, Send to standard output.

```
# usage: girstub gen gir_dir module version

> python gi_tool/girstub.py gen C:/gnome/share/gir-1.0 Gtk 4.0 > C:\Python311\Lib\site-packages\gi-stubs\repository\Gtk.pyi
```

Convert the gifs in folder and write each result to the output folder.

```
# usage: girstub all gir_dir site_packages

> python gi_tool/girstub.py all C:/gnome/share/gir-1.0 C:\Python311\Lib\site-packages
```

