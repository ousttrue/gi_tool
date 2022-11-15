import pathlib
import argparse
import io
import re
import types
import gi
import importlib
import inspect
import xml.etree.ElementTree as ET
from typing import List, Optional, NamedTuple

NS = {"": "http://www.gtk.org/introspection/core/1.0"}
C_NS = {"c": "http://www.gtk.org/introspection/c/1.0"}
PATTERN = re.compile(r"\{([^}]+)\}(.+)")


def get_tag(child: ET.Element) -> str:
    m = PATTERN.match(child.tag)
    assert m
    return m.group(2)


def py_type(gir_type: Optional[str]) -> str:
    if not gir_type:
        return "None"
    match gir_type:
        case "gboolean":
            return "bool"
        case "gint" | "guint" | "gsize" | "gssize":
            return "int"
        case "gfloat" | "gdouble":
            return "float"
        case "utf8":
            return "str"
        case "List[utf8]":
            return "List[str]"
        case "gpointer":
            return "object"
        case _:
            return f"'{gir_type}'"


class GIParam:
    def __init__(self, element: ET.Element, is_this=False) -> None:
        self.is_this = is_this
        self.name = element.attrib["name"]
        self.type = str(element)
        for child in element:
            tag = get_tag(child)
            match tag:
                case "doc":
                    self.doc = child.text
                case "type":
                    self.type = child.attrib["name"]
                case "array":
                    self.type = f"List[{child.find('type', NS).attrib['name']}]"
                case "varargs":
                    self.type = f"varargs"
                case _:
                    assert False

    def __str__(self) -> str:
        if self.is_this:
            return "self"
        elif self.name == "...":
            return "*args"
        else:
            return f"{self.name}: {py_type(self.type)}"


class GIMethod:
    def __init__(
        self, element: ET.Element, is_static=False, return_type: Optional[str] = None
    ) -> None:
        self.name = element.attrib["name"]
        self.doc = None
        self.return_type = None
        self.is_static = is_static
        self.parameters: List[GIParam] = []
        for child in element:
            tag = get_tag(child)
            match tag:
                case "return-value":
                    self.parse_return(child)
                case "parameters":
                    self.parse_parameters(child)
                case "attribute":
                    pass
                case "doc":
                    self.doc = child.text
                case "doc-deprecated":
                    pass
                case "source-position":
                    pass
                case _:
                    print(tag)
                    assert False

        if return_type:
            self.return_type = return_type

    def parse_return(self, element: ET.Element):
        for child in element:
            tag = get_tag(child)
            match tag:
                case "doc":
                    pass
                case "type":
                    self.return_type = child.attrib["name"]

    def parse_parameters(self, element: ET.Element):
        for child in element:
            tag = get_tag(child)
            if tag == "parameter":
                self.parameters.append(GIParam(child))
            elif tag == "instance-parameter":
                self.parameters.append(GIParam(child, True))
            else:
                assert False

    def to_str(self, indent="    "):
        sio = io.StringIO()
        if self.is_static:
            sio.write(f"{indent}@staticmethod\n")
        parameters = ", ".join(str(p) for p in self.parameters)
        sio.write(
            f"""{indent}def {self.name}({parameters}) -> {py_type(self.return_type)}:\n"""
        )
        if self.doc:
            sio.write(f'''{indent}    """{self.doc}"""\n''')
        sio.write(f"{indent}    ...\n\n")
        return sio.getvalue()

    def __str__(self) -> str:
        return self.to_str()


class GIClass:
    def __init__(self, element: ET.Element) -> None:
        self.name = element.attrib["name"]
        self.doc = None
        self.parent = element.attrib.get("parent")
        assert self.name
        self.methods: List[GIMethod] = []

        for child in element:
            tag = get_tag(child)
            match tag:
                case "method":
                    self.methods.append(GIMethod(child))
                case "constructor":
                    self.methods.append(
                        GIMethod(child, is_static=True, return_type=self.name)
                    )
                case "function":
                    self.methods.append(GIMethod(child, is_static=True))
                case "doc":
                    self.doc = child.text
                case "doc-deprecated":
                    pass
                case "source-position":
                    pass
                case "constructor":
                    pass
                case "property":
                    pass
                case "signal":
                    pass
                case "implements":
                    pass
                case "virtual-method":
                    pass
                case "field":
                    pass
                case "union":
                    pass
                case _:
                    assert False

    def __str__(self):
        sio = io.StringIO()
        if self.parent:
            sio.write(f"class {self.name}({self.parent}):\n")
        else:
            sio.write(f"class {self.name}:\n")
        if self.doc:
            sio.write(f'    """{self.doc}"""\n')

        if self.methods:
            for method in self.methods:
                sio.write(method.to_str(indent="    "))
        else:
            sio.write("    pass\n")
        return sio.getvalue()


class GIEnumValue(NamedTuple):
    name: str
    value: str
    doc: Optional[str]

    @staticmethod
    def from_element(element: ET.Element) -> "GIEnumValue":
        name = element.attrib["name"].upper()
        value = element.attrib["value"]
        doc = element.find("doc", NS)
        doc_text = None
        if doc != None:
            doc_text = doc.text
        return GIEnumValue(name, value, doc_text)


class GIEnum:
    def __init__(self, element: ET.Element, is_intflag=False) -> None:
        self.doc = None
        self.name = element.attrib["name"]
        self.values: List[GIEnumValue] = []
        self.is_intflag = is_intflag

        for child in element:
            tag = get_tag(child)
            match tag:
                case "doc":
                    self.doc = child.text
                case "member":
                    self.values.append(GIEnumValue.from_element(child))
                case "function":
                    # ?
                    pass
                case "source-position":
                    pass
                case _:
                    assert False

    def __str__(self) -> str:
        sio = io.StringIO()
        if self.is_intflag:
            sio.write(f"class {self.name}(IntFlag):\n")
        else:
            sio.write(f"class {self.name}(Enum):\n")
        if self.doc:
            sio.write(f'    """{self.doc}"""\n')

        for value in self.values:
            sio.write(f"    {value.name} = {value.value}\n")
            if value.doc:
                sio.write(f'    """{value.doc}"""\n')
        sio.write("\n")
        return sio.getvalue()


class GIModule:
    def __init__(self, gir_dir: pathlib.Path, module: types.ModuleType) -> None:
        assert gir_dir.exists()
        self.constants: List[GIEnumValue] = []
        self.classes: dict[str, object] = {}
        self.functions: List[GIMethod] = []

        gir = gir_dir / f"{module._namespace}-{module._version}.gir"
        tree = ET.parse(gir)
        root = tree.getroot()
        namespace = root.find("namespace", NS)
        assert namespace

        # for key in dir(module):
        #     attr = getattr(module, key)
        #     self.process_obj(attr, namespace)

        # def process_obj(self, parent, gir: ET.Element):
        # print(parent)
        # for key in dir(parent):
        #     if key.startswith('__'):
        #         continue
        #     obj = getattr(parent, key)
        #     if callable(obj) or inspect.isroutine(obj):
        #         try:
        #             sig = inspect.signature(obj)
        #             print(f'[override]{key}{sig}')
        #         except:
        #             # get gir
        #             print(f'[gir]{key}()')
        #     elif inspect.isdatadescriptor(obj):
        #         # props
        #         print(f'[get/set]{key}')
        #     elif str(type(obj)) == "<class 'gi._gi.GProps'>":
        #         print(f'[GProps]{key}')
        #     else:
        #         assert False

        for child in namespace:
            tag = get_tag(child)
            match tag:
                case "class":
                    klass = GIClass(child)
                    self.classes[klass.name] = klass
                case "enumeration":
                    klass = GIEnum(child)
                    self.classes[klass.name] = klass
                case "bitfield":
                    klass = GIEnum(child, is_intflag=True)
                    self.classes[klass.name] = klass
                case "constant":
                    self.constants.append(GIEnumValue.from_element(child))
                case "function":
                    self.functions.append(GIMethod(child))
                case "alias":
                    pass
                case "function-macro":
                    pass
                case "record":
                    pass
                case "interface":
                    pass
                case "callback":
                    pass
                case "boxed":
                    pass
                case "docsection":
                    pass
                case _:
                    assert False


def generate(gir_dir: pathlib.Path, name: str, version: str):
    gi.require_version(name, version)
    module = importlib.import_module(f".{name}", "gi.repository")

    gi_module = GIModule(gir_dir, module)

    print(
        """from typing import List
import gi
from gi.repository import Pango, Gdk, Gio, GObject
from enum import Enum, IntFlag
"""
    )

    # const
    for value in gi_module.constants:
        print(f"{value.name} = {value.value}")
        if value.doc:
            print(f'"""{value.doc}"""')

    # class / enum
    for key in sorted(gi_module.classes.keys()):
        klass = gi_module.classes[key]
        print(klass)

    # functions
    for f in gi_module.functions:
        print(f.to_str(indent=""))


def main():
    parser = argparse.ArgumentParser(
        prog="gi_tool.generator",
        description="generate pygobject stub from {gir_dir}/{module}-{version}.gir",
    )
    parser.add_argument("gir_dir", help="PREFIX/share/gir-1.0")
    parser.add_argument("module", help="Gtk, Gst ... etc")
    parser.add_argument("version", help="1.0, 2.0, 3.0, 4.0 ... etc")
    parsed = parser.parse_args()

    generate(pathlib.Path(parsed.gir_dir), parsed.module, parsed.version)


if __name__ == "__main__":
    main()
