import pathlib
import io
import re
import types
import gi
import importlib
import inspect
import xml.etree.ElementTree as ET
from typing import List, Optional

GIR_BASE = pathlib.Path('D:/gnome/share/gir-1.0')
NS = {'': 'http://www.gtk.org/introspection/core/1.0'}
C_NS = {'c': 'http://www.gtk.org/introspection/c/1.0'}
PATTERN = re.compile(r'\{([^}]+)\}(.+)')


def get_tag(child: ET.Element) -> str:
    m = PATTERN.match(child.tag)
    assert m
    return m.group(2)


def py_type(gir_type: Optional[str]) -> str:
    if not gir_type:
        return 'None'
    match gir_type:
        case 'gboolean':
            return 'bool'
        case 'gint' | 'guint':
            return 'int'
        case 'gfloat' | 'gdouble':
            return 'float'
        case 'utf8':
            return 'str'
        case 'List[utf8]':
            return 'List[str]'
        case 'gpointer':
            return 'object'
        case _:
            return f"'{gir_type}'"


class GIParam:
    def __init__(self, element: ET.Element, is_this=False) -> None:
        self.is_this = is_this
        self.name = element.attrib['name']
        self.type = str(element)
        for child in element:
            tag = get_tag(child)
            match tag:
                case 'doc':
                    self.doc = child.text
                case 'type':
                    self.type = child.attrib['name']
                case 'array':
                    self.type = f"List[{child.find('type', NS).attrib['name']}]"
                case 'varargs':
                    self.type = f"varargs"
                case _:
                    assert False

    def __str__(self) -> str:
        if self.is_this:
            return 'self'
        else:
            return f"{self.name}: {py_type(self.type)}"


class GIMethod:
    def __init__(self, element: ET.Element) -> None:
        self.name = element.attrib['name']
        self.doc = None
        self.return_type = None
        self.parameters: List[GIParam] = []
        for child in element:
            tag = get_tag(child)
            match tag:
                case 'return-value':
                    self.parse_return(child)
                case 'parameters':
                    self.parse_parameters(child)
                case 'attribute':
                    pass
                case 'doc':
                    self.doc = child.text
                case 'doc-deprecated':
                    pass
                case 'source-position':
                    pass
                case _:
                    print(tag)
                    assert False

    def parse_return(self, element: ET.Element):
        for child in element:
            tag = get_tag(child)
            match tag:
                case 'doc':
                    pass
                case 'type':
                    self.return_type = child.attrib.get('c:type')

    def parse_parameters(self, element: ET.Element):
        for child in element:
            tag = get_tag(child)
            if tag == 'parameter':
                self.parameters.append(GIParam(child))
            elif tag == 'instance-parameter':
                self.parameters.append(GIParam(child, True))
            else:
                assert (False)

    def __str__(self):
        sio = io.StringIO()
        if self.doc:
            sio.write(f'''    """{self.doc}"""\n''')
        parameters = ', '.join(str(p) for p in self.parameters)
        sio.write(
            f'''    def {self.name}({parameters}) -> {py_type(self.return_type)}:...\n\n''')
        return sio.getvalue()


class GIClass:
    def __init__(self, element: ET.Element) -> None:
        self.name = element.attrib['name']
        assert (self.name)
        self.methods = {}

        for child in element:
            tag = get_tag(child)
            match tag:
                case 'method':
                    name = child.attrib['name']
                    if name:
                        self.methods[name] = GIMethod(child)
                case 'doc':
                    pass
                case 'doc-deprecated':
                    pass
                case 'source-position':
                    pass
                case 'constructor':
                    pass
                case 'property':
                    pass
                case 'signal':
                    pass
                case 'implements':
                    pass
                case 'function':
                    pass
                case 'virtual-method':
                    pass
                case 'field':
                    pass
                case _:
                    assert False

    def __str__(self):
        sio = io.StringIO()
        sio.write(f'class {self.name}:\n')
        if self.methods:
            for key in self.methods.keys():
                method = self.methods[key]
                sio.write(str(method))
        else:
            sio.write("    pass\n")
        return sio.getvalue()


class GIModule:

    def __init__(self, module: types.ModuleType) -> None:
        self.classes: dict[str, GIClass] = {}

        gir = GIR_BASE / f'{module._namespace}-{module._version}.gir'
        tree = ET.parse(gir)
        root = tree.getroot()
        namespace = root.find('namespace', NS)
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
                case 'class':
                    name = child.attrib['name']
                    if name in self.classes:
                        ET.dump(child)
                        assert False
                    klass = GIClass(child)
                    assert klass.name == name
                    self.classes[name] = klass
                case 'alias':
                    pass
                case 'function':
                    pass
                case 'function-macro':
                    pass
                case 'constant':
                    pass
                case 'record':
                    pass
                case 'interface':
                    pass
                case 'enumeration':
                    pass
                case 'bitfield':
                    pass
                case 'callback':
                    pass
                case 'boxed':
                    pass
                case 'docsection':
                    pass
                case _:
                    assert False


def generate(name: str, version: str):
    gi.require_version(name, version)
    module = importlib.import_module(f'.{name}', 'gi.repository')

    gi_module = GIModule(module)
    w = gi_module.classes['Window']

    print('''from typing import List
import gi
from gi.repository import Pango, Gdk, Gio, GObject
''')

    for key in sorted(gi_module.classes.keys()):
        klass = gi_module.classes[key]
        print(klass)


if __name__ == '__main__':
    generate('Gtk', '4.0')
