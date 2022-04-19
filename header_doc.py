#!/usr/bin/env python

from dataclasses import dataclass
from sys import argv

@dataclass
class DocPair():
    comment : str
    code : str

@dataclass
class DocArg():
    name : str
    desc : str

def _is_empty_strlist(strlist):
    for text in strlist:
        if len(text.lstrip().rstrip()) > 0:
            return False

    return True

def _strlist_to_str(strlist):
    text = ""
    for item in strlist[:-1]:
        text += "{}\n".format(item)
    text += strlist[-1]

    return text

def _strlist_to_html(strlist):
    text = "<p>"
    for item in strlist:
        if len(item.lstrip().rstrip()) == 0:
            text += "</p><p>"
        else:
            text += "{} ".format(item)
    text += "</p>"

    return text

def _make_sees_list(sees):
    text = "<p>See:"
    for see in sees:
        text += " <a href=\"#{}\">{}</a>".format(see, see)
    text += "</p>"

    return text

def _make_args_table(args):
    text = "<table class=\"funcdef\"><thead><th>Name</th><th>Description</th></thead><tbody>"
    for arg in args:
        text += "<tr><td>{}</td><td>{}</td></tr>".format(arg.name, arg.desc)
    text += "</tbody></table>"

    return text

def _get_funcname(proto):
    ridx = proto.index('(')
    lidx = 0
    try:
        lidx = proto[:ridx].rindex('*')
    except ValueError:
        try:
            lidx = proto[:ridx].rindex(' ')
        except ValueError:
            pass

    return proto[lidx+1:ridx]

def _name_to_id(name):
    return name.translate({' ': '_',
                           '.': '_'})

def _clear_trailing_blank_lines(strlist):
    for num in range(len(strlist) - 1, 0, -1):
        if len(strlist[num].lstrip().rstrip()) == 0:
            del strlist[num]
        else:
            break

    return strlist

class DocTOC():
    def __init__(self, docs):
        self._toclist = list()
        for doc in docs:
            self._toclist.append((doc.depth, doc.name))

    def __str__(self):
        depth = 1
        text = "<ul>"
        for doc in self._toclist:
            if doc[0] < depth:
                for num in range(depth - doc[0]):
                    text += "</ul>"
                depth = doc[0]
            elif doc[0] > depth:
                for num in range(doc[0] - depth):
                    text += "<ul>"
                depth = doc[0]
            text += "<li><a href=\"#{}\">{}</a></li>".format(_name_to_id(doc[1]), doc[1])
        for num in range(depth):
            text += "</ul>"

        return text

class DocHeading():
    def __init__(self, title, depth):
        self._title = title
        self._depth = depth

    @property
    def name(self):
        return self._title

    @property
    def depth(self):
        return self._depth

    def __str__(self):
        return "<h{} id=\"{}\">{}</h{}>".format(self._depth,
                                                _name_to_id(self._title),
                                                self._title,
                                                self._depth)

class DocText():
    def __init__(self, title, text, depth):
        self._title = title
        self._text = text
        self._depth = depth

    @property
    def name(self):
        return self._title

    @property
    def depth(self):
        return self._depth

    def __str__(self):
        return "<h{} id=\"{}\">{}</h{}><p>{}</p>".format(self._depth,
                                                         _name_to_id(self._title),
                                                         self._title,
                                                         self._depth,
                                                         self._text)

class DocCode():
    def __init__(self, title, code, depth):
        self._title = title
        self._code = code
        self._depth = depth

    @property
    def name(self):
        return self._title

    @property
    def depth(self):
        return self._depth

    def __str__(self):
        return "<h{} id=\"{}\">{}</h{}><code>{}</code>".format(self._depth,
                                                               _name_to_id(self._title),
                                                               self._title,
                                                               self._depth,
                                                               self._code)

class DocTypeDef():
    def __init__(self, name, proto, desc, depth):
        self._name = name
        self._proto = proto
        self._desc = desc
        self._depth = depth

    @property
    def name(self):
        return self._name

    @property
    def depth(self):
        return self._depth

    def __str__(self):
        text = "<code id=\"{}\">{}</code><p>{}</p><hr>".format(_name_to_id(self._name),
                                                               self._proto,
                                                               self._desc)

        return text

class DocFuncDef():
    def __init__(self, name, proto, desc, sees, args, depth):
        self._name = name
        self._proto = proto
        self._desc = desc
        self._sees = sees
        self._args = args
        self._depth = depth

    @property
    def name(self):
        return self._name

    @property
    def depth(self):
        return self._depth

    def __str__(self):
        text = "<code id=\"{}\">{}</code><p>{}</p>".format(_name_to_id(self._name),
                                                           self._proto,
                                                           self._desc)
        if self._sees is not None:
            text += _make_sees_list(self._sees)
        if self._args is not None:
            text += _make_args_table(self._args)
        text += "<hr>"

        return text

class HeaderReader:
    def _find_comment_start(self, start):
        code = list()
        try:
            idx = start.index('/*')
            code.append(start[:idx])
            return DocPair(code, start[idx+2:])
        except ValueError:
            if len(start) > 0:
                code.append(start)

        for line in self._in:
            if line[-1] == '\n':
                line = line[:-1]
            try:
                idx = line.index('/*')
                code.append(line[:idx])
                rest = line[idx+2:]
                code = _clear_trailing_blank_lines(code)
                return DocPair(code, rest)
            except ValueError:
                if len(code) > 0 or len(line.lstrip().rstrip()) > 0:
                    code.append(line)

        return DocPair(code, None)

    def _find_comment_end(self, start):
        comment = list()
        try:
            idx = start.index('*/')
            comment.append(start[:idx])
            return DocPair(comment, start[idx+2:])
        except ValueError:
            if len(start) > 0:
                comment.append(start)

        for line in self._in:
            if line[-1] == '\n':
                line = line[:-1]
            try:
                idx = line.index('*/')
                comment.append(line[:idx])
                rest = line[idx+2:]
                comment = _clear_trailing_blank_lines(comment)
                return DocPair(comment, rest)
            except ValueError:
                if line.startswith(' *'):
                    line = line.lstrip()[2:]
                if len(comment) > 0 or len(line.lstrip().rstrip()) > 0:
                    comment.append(line)

        return DocPair(comment, None)

    def _get_comment_code_pair(self):
        if self._rest is None:
            return DocPair(None, None)
        commentpair = self._find_comment_end(self._rest)
        self._rest = commentpair.code
        if self._rest is None:
            return commentpair
        codepair = self._find_comment_start(self._rest)
        self._rest = codepair.code

        return DocPair(commentpair.comment, codepair.comment)

    def _get_intro(self):
        intro = self._get_comment_code_pair()
        if intro.comment[0].lstrip().startswith('Copyright'):
            intro = self._get_comment_code_pair()

        return intro

    def __init__(self, filename):
        depth = 1
        self._items = list()
        with open(filename, 'r') as self._in:
            pair = self._find_comment_start('')
            self._rest = pair.code

            intro = self._get_intro()
            self._items.append(DocText("{} Documentation".format(filename),
                                       _strlist_to_html(intro.comment),
                                       depth))
            depth += 1
            while True:
                pair = self._get_comment_code_pair()
                if pair.code is None and pair.comment is None:
                    # no more to read from the file
                    break
                if pair.code is None or _is_empty_strlist(pair.code):
                    if _is_empty_strlist(pair.comment):
                        if depth <= 2:
                            raise ValueError("depth went too low, maybe unmatched section ending?")
                        depth -= 1
                    elif len(pair.comment) == 1:
                        self._items.append(DocHeading(_strlist_to_str(pair.comment),
                                                      depth))
                        depth += 1
                    else:
                        self._items.append(DocText(pair.comment[0],
                                                   _strlist_to_html(pair.comment[1:]),
                                                   depth))
                elif pair.code[0].lower().startswith('typedef'):
                    if pair.code[0].lower().split()[1] == 'struct' or \
                       pair.code[0].lower().split()[1] == 'enum':
                        name = pair.code[-1].split()[-1][:-1]
                        self._items.append(DocTypeDef(name,
                                                      _strlist_to_str(pair.code),
                                                      _strlist_to_html(pair.comment),
                                                      depth))
                    else:
                        lidx = pair.code[0].index('(*')
                        ridx = pair.code[0][lidx+2:].index(')')
                        name = pair.code[0][lidx+2:lidx+2+ridx]
                        self._items.append(DocTypeDef(name,
                                                      _strlist_to_str(pair.code),
                                                      _strlist_to_html(pair.comment),
                                                      depth))
                elif pair.code[0].lower().startswith('#define'):
                    name = pair.code[0].split()[1]
                    try:
                        idx = name.index('(')
                        name = name[:idx]
                    except ValueError:
                        pass
                    self._items.append(DocTypeDef(name,
                                                  _strlist_to_str(pair.code),
                                                  _strlist_to_html(pair.comment),
                                                  depth))
                else:
                    if pair.code[-1].startswith('#endif'):
                        pair.code = pair.code[:-1]
                        pair.code = _clear_trailing_blank_lines(pair.code)
                    found = len(pair.comment) - 1
                    for num in range(len(pair.comment) - 1, 0, -1):
                        if len(pair.comment[num].lstrip().rstrip()) == 0:
                            found = num
                            break
                    args = list()
                    if found < len(pair.comment) - 1:
                        name = None
                        desc = ''
                        for arg in pair.comment[num+1:]:
                            if arg[0] == ' ':
                                desc += ' '
                                desc += arg.lstrip()
                            else:
                                if name is not None:
                                    args.append(DocArg(name, desc))
                                name, desc = arg.split(maxsplit=1)
                        if name is not None:
                            args.append(DocArg(name, desc))
                    else:
                        args = None
                    sees = None
                    if pair.comment[found-1].lstrip().startswith("See: "):
                        sees = pair.comment[found-1].split()[1:]
                        found -= 1
                    name = _get_funcname(pair.code[0])
                    self._items.append(DocFuncDef(name,
                                                  _strlist_to_str(pair.code),
                                                  _strlist_to_html(pair.comment[:found]),
                                                  sees,
                                                  args,
                                                  depth))

        toc = DocTOC(self._items)
        self._items.insert(0, toc)

    def __getitem__(self, num):
        return self._items[num]

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return DocIterator(self)

class DocIterator():
    def __init__(self, doc, num=0):
        self._doc = doc
        self._num = num

    def __iter__(self):
        return DocIterator(self._doc, self._num)

    def __next__(self):
        if self._num >= len(self._doc):
            raise StopIteration
        self._num += 1
        return self._doc[self._num - 1]

def main(filename):
    header = """<!DOCTYPE html>
<html>
    <head>
        <title>{} Documentation</title>
        <link href="uncrustygame.css" rel="stylesheet">
    </head>
    <body>
        <img src="cdemo/title.bmp">""".format(filename)

    footer = """    </body>
</html>"""

    doc = HeaderReader(filename)

    print(header)
    for block in doc:
        print(block)
    print(footer)

if __name__ == '__main__':
    main(argv[1])
