from typing import List, Optional, NamedTuple, TextIO
import pathlib
import argparse
import io
import re
import types
import gi
import importlib
import inspect
import xml.etree.ElementTree as ET
import logging
import sys

logger = logging.getLogger(__name__)

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
        case "gint" | "guint" | "guint32" | "gsize" | "gssize":
            return "int"
        case "gfloat" | "gdouble":
            return "float"
        case "utf8":
            return "str"
        case "List[utf8]":
            return "List[str]"
        case "gpointer":
            return "object"
        case "none":
            return "None"
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
                    self.type = child.attrib.get("name")
                case "array":
                    self.type = f"List[{child.find('type', NS).attrib['name']}]" # type: ignore
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
                case "doc-deprecated" | "doc-version":
                    if not self.doc:
                        self.doc = child.text
                case "source-position":
                    pass
                case _:
                    logger.error(tag)
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
                    self.return_type = child.attrib.get("name")

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
        self.parents = []
        parent = element.attrib.get("parent")
        if parent:
            self.parents.append(parent)
        assert self.name
        self.methods: List[GIMethod] = []

        for child in element:
            tag = get_tag(child)
            match tag:
                case "method" | "virtual-method":
                    self.methods.append(GIMethod(child))
                case "constructor":
                    self.methods.append(
                        GIMethod(child, is_static=True, return_type=self.name)
                    )
                case "function":
                    self.methods.append(GIMethod(child, is_static=True))
                case "doc":
                    self.doc = child.text
                case "implements":
                    self.parents.append(child.attrib["name"])
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
                case "field":
                    pass
                case "union":
                    pass
                case "prerequisite":
                    pass
                case "attribute":
                    pass
                case _:
                    assert False

    def __str__(self):
        sio = io.StringIO()
        if self.parents:
            parent = ", ".join(self.parents)
            sio.write(f"class {self.name}({parent}):\n")
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
                case "doc-deprecated" | "doc-version":
                    if not self.doc:
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
    def __init__(self, gir: pathlib.Path) -> None:
        self.constants: List[GIEnumValue] = []
        self.classes: dict[str, object] = {}
        self.functions: List[GIMethod] = []

        tree = ET.parse(gir)
        root = tree.getroot()
        namespace = root.find("namespace", NS)
        assert namespace

        for child in namespace:
            tag = get_tag(child)
            match tag:
                case "class" | "interface":
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
                case "callback":
                    pass
                case "boxed":
                    pass
                case "docsection":
                    pass
                case "union":
                    pass
                case _:
                    assert False


def generate(gir_file: pathlib.Path, out: TextIO):
    gi_module = GIModule(gir_file)

    out.write(
        """from typing import List
import gi
from gi.repository import Pango, Gdk, Gio, GObject, Gsk
from enum import Enum, IntFlag

"""
    )

    # const
    for value in gi_module.constants:
        out.write(f"{value.name} = {value.value}\n")
        if value.doc:
            out.write(f'"""{value.doc}"""\n')

    # class / enum
    for key in sorted(gi_module.classes.keys()):
        klass = gi_module.classes[key]
        out.write(str(klass))
        out.write("\n")

    # functions
    for f in gi_module.functions:
        out.write(f.to_str(indent=""))
        out.write("\n")


def generate_all(gir_dir: pathlib.Path, site_packages: pathlib.Path):
    dst = site_packages / "gi-stubs/repository"
    if not dst.exists():
        logger.info(f"mkdir: {dst}")
        dst.mkdir(exist_ok=True, parents=True)

    for e in gir_dir.iterdir():
        if not e.is_file():
            continue
        if e.suffix != ".gir":
            continue
        m = re.search(r'(.*)-(\d+\.\d+)$', e.stem)
        if m:
            name = m.group(1)
        else:
            name = e.stem
        pyi = dst / (name + ".pyi")

        logger.info(pyi.name)
        with pyi.open(mode="w") as w:
            generate(e, w)

    init = dst / '__init__.py'
    if not init.exists():
        init.write_text('')


def main():
    parser = argparse.ArgumentParser(
        prog="girstub",
        description="generate pygobject stub from {gir_dir}/{module}-{version}.gir",
    )
    subparsers = parser.add_subparsers(dest="subparser_name")

    # gen
    parser_gen = subparsers.add_parser("gen", help="Print pyi from gen")
    parser_gen.add_argument("gir_dir", help="Path to PREFIX/share/gir-1.0")
    parser_gen.add_argument("module", help="Gtk, Gst ... etc")
    parser_gen.add_argument("version", help="1.0, 2.0, 3.0, 4.0 ... etc")

    # all
    parser_all = subparsers.add_parser("all", help="Generate pyi files from *.gen")
    parser_all.add_argument("gir_dir", help="Path to PREFIX/share/gir-1.0")
    parser_all.add_argument(
        "site_packages",
        help="Path to python/lib/site-packages. Write {site_packages}/gi-stubs/repository/*.pyi files.",
    )

    # dispatch
    args = parser.parse_args()
    match args.subparser_name:
        case "gen":
            gir_dir = pathlib.Path(args.gir_dir)
            gir = gir_dir / f"{args.module}-{args.version}.gir"
            generate(gir, sys.stdout)
        case "all":
            generate_all(pathlib.Path(args.gir_dir), pathlib.Path(args.site_packages))
        case _:
            parser.print_help()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
