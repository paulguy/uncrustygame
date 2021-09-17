from sys import stdout
import copy

FIELD_TYPE_INT = "int"
FIELD_TYPE_HEX = "hex"
FIELD_TYPE_FLOAT = "float"
FIELD_TYPE_STR = "str"
FIELD_TYPE_ROW = "row"

EMPTY_ROW = "empty-row"

class SequenceEnded(Exception):
    pass

class SequenceDescription():
    def __init__(self):
        self._column = list()
        self._rowdesc = list()
        # add necessary "speed" column
        globalRow = self.add_row_description()
        self.add_field(globalRow, FIELD_TYPE_INT)
        self.add_column(globalRow)

    @property
    def columns(self):
        return len(self._column)

    def add_row_description(self):
        self._rowdesc.append(list())
        return len(self._rowdesc) - 1

    def add_field(self, desc, fieldType, rowDesc=None, func=None, priv=None):
        if fieldType == FIELD_TYPE_ROW:
            if rowDesc < 0 or rowDesc > len(self._rowdesc) - 1:
                raise IndexError("invalid row description index")
            self._rowdesc[desc].append(rowDesc)
        elif func != None:
            self._rowdesc[desc].append((fieldType, func, priv))
        else:
            self._rowdesc[desc].append(fieldType)

    def add_column(self, rowDesc):
        if rowDesc < 0 or rowDesc > len(self._rowdesc) - 1:
            raise IndexError("invalid row description index")
        self._column.append(rowDesc)
        return len(self._column) - 1


class Sequencer():
    def __init__(self, desc, file):
        self._desc = desc
        self._read_file(file)
        self.reset()

    def reset(self):
        self._divTime = self._row[self._initial[0]][0]
        self._curOrder = -1
        self._curLine = 0
        self._lineTime = 0
        self._ended = False

    def _add_row(self, newrow):
        for row in range(len(self._row)):
            found = True
            if len(self._row[row]) == len(newrow):
                for item in range(len(newrow)):
                    if self._row[row][item] != newrow[item]:
                        found = False
                        break
            else:
                continue
            if found:
                return row
        self._row.append(newrow)
        return len(self._row) - 1

    def _read_row(self, struct, desc, initial=False):
        pos = 0
        changeMask = None
        if not initial:
            if len(struct) == 0:
                return 0, EMPTY_ROW
            changeMask = int(struct[0], base=16)
            if changeMask == 0:
                return 1, EMPTY_ROW
            pos += 1

        row = list()
        for i in range(len(desc)):
            if not initial:
                # changeMask bits are left to right so logically reversed from
                # their actual bit number
                changed = changeMask & (1 << ((len(desc) - 1) - i))
                if not changed:
                    row.append(None)
                    continue

            try:
                if desc[i] == FIELD_TYPE_INT:
                    row.append(int(struct[pos]))
                elif desc[i] == FIELD_TYPE_HEX:
                    row.append(int(struct[pos], base=16))
                elif desc[i] == FIELD_TYPE_FLOAT:
                    row.append(float(struct[pos]))
                elif desc[i] == FIELD_TYPE_STR:
                    row.append(struct[pos])
                elif isinstance(desc[i], int):
                    rowDesc = self._desc._rowdesc[desc[i]]
                    # pass False because an initial row argument may be an empty
                    # row
                    adv, newrow = self._read_row(struct[pos:], rowDesc, initial=False)
                    row.append(newrow)
                    pos += adv
                    continue
                pos += 1
            except IndexError as e:
                print("Not enough values: {}".format(struct))
                if not initial:
                    print(" Change mask: {:X}".format(changeMask))
                raise e
            except ValueError as e:
                print("Wrong value type for item {}".format(pos))
                print(" Values: {}".format(struct))
                print(" Descriptor Item: {}".format(i))
                raise e

        return pos, self._add_row(row)

    def _read_line(self, file, initial=False):
        structs = file.readline().split('|')

        fullRow = list()
        # allow global only or totally empty lines
        if not initial and len(structs) == 2 and len(structs[1].strip()) == 0:
            if len(structs[0].strip()) == 0:
                # totally empty line "|"
                for i in range(self._desc.columns):
                    fullRow.append(EMPTY_ROW)
            else:
                # line with only global changes "~~~ |"
                columnDesc = self._desc._column[0]
                rowDesc = self._desc._rowdesc[columnDesc]
                split = structs[0].split()
                pos, newrow = self._read_row(split, rowDesc)
                if len(split) > pos:
                    raise Exception("too many values in column ({} > {})".format(len(split), pos))
                fullRow.append(newrow)
                for i in range(1, self._desc.columns):
                    fullRow.append(EMPTY_ROW)
        elif len(structs) == self._desc.columns:
            for i in range(self._desc.columns):
                columnDesc = self._desc._column[i]
                rowDesc = self._desc._rowdesc[columnDesc]
                split = structs[i].split()
                pos, newrow = self._read_row(split, rowDesc, initial=initial)
                if len(split) > pos:
                    raise Exception("too many values in column ({} > {})".format(len(split), pos))
                fullRow.append(newrow)
        else:
            raise Exception("wrong number of columns in file ({} != {})".format(len(structs), self._desc.columns))

        return fullRow

    def _read_file(self, file):
        self._row = list()
        self._pattern = list()
        self._order = list()
        self._initial = self._read_line(file, initial=True)

        patterns = int(file.readline())
        for i in range(patterns):
            patlen = int(file.readline())
            pattern = list()
            for j in range(patlen):
                pattern.append(self._read_line(file))
            self._pattern.append(pattern)
        print(self._row)

        ordersData = file.readline().split()
        for item in ordersData:
            order = int(item)
            if order < 0 or order > len(self._pattern) - 1:
                raise IndexError("order refers to pattern out of range")
            self._order.append(int(item))

    def _write_row(self, file, row, desc, initial):
        changeMask = 0
        if not initial:
            changeBit = 1 << len(desc)
            for item in range(len(desc)):
                changeBit >>= 1
                if row[item] != None:
                    changeMask |= changeBit
            print("{:x} ".format(changeMask), end='', file=file)

        for item in range(len(desc)):
            if row[item] != None:
                if desc[item] == FIELD_TYPE_INT:
                    print("{:d} ".format(row[item]), end='', file=file)
                elif desc[item] == FIELD_TYPE_HEX:
                    print("{:x} ".format(row[item]), end='', file=file)
                elif desc[item] == FIELD_TYPE_FLOAT:
                    print("{:f} ".format(row[item]), end='', file=file)
                elif desc[item] == FIELD_TYPE_STR:
                    print(row[item], end=' ', file=file)
                elif isinstance(desc[item], int):
                    # SEQ_FIELD_TYPE_ROW
                    rowDesc = self._desc._rowdesc[desc[item]]
                    self._write_row(file, self._row[row[item]], rowDesc, initial)

    def _write_line(self, file, line):
        initial = False
        if line == self._initial:
            initial = True

        for row in range(len(line)):
            columnDesc = self._desc._column[row]
            desc = self._desc._rowdesc[columnDesc]
            self._write_row(file, self._row[line[row]], desc, initial)

            if row != len(line) - 1:
                print("| ", end='', file=file)

        print(file=file)

    def write_file(self, file=stdout):
        # print initial state
        self._write_line(file, self._initial)
        # print number of patterns
        print("{}".format(len(self._pattern)), file=file)

        for pattern in self._pattern:
            # print number of lines in pattern
            print("{}".format(len(pattern)), file=file)
            for line in pattern:
                self._write_line(file, line)

        for order in self._order:
            print("{} ".format(order), end='', file=file)
        print(file=file)

    def _get_row(self, desc, row):
        newRow = list()
        for i in range(len(desc)):
            if isinstance(desc[i], int):
                if row[i] == None:
                    newRow.append(None)
                elif row[i] == EMPTY_ROW:
                    newRow.append(EMPTY_ROW)
                else:
                    newRow.append(self._get_row(self._desc._rowdesc[desc[i]], self._row[row[i]]))
            else:
                newRow.append(row[i])
        return newRow

    def _get_line(self, line):
        newLine = list()
        for i in range(len(line)):
            desc = self._desc._rowdesc[self._desc._column[i]]
            if line[i] == EMPTY_ROW:
                newLine.append(None)
            else:
                newLine.append(self._get_row(desc, self._row[line[i]]))
        return newLine

    def set_pattern(self, pattern):
        if pattern < 0 or pattern > len(self._pattern):
            raise IndexError("pattern out of range")
        self._curPattern = pattern
        self._curLine = 0

    def set_order(self, order):
        if pattern < 0 or pattern > len(self._order):
            raise IndexError("order out of range")
        self._curOrder = 0
        self._curPattern = self._order[self._curOrder]
        self._curLine = 0

    def advance(self, time):
        line = None

        if self._curOrder == -1 and self._curLine == 0 and self._lineTime == 0:
            time = 0
            self._curOrder = 0
            self._curPattern = self._order[0]
            line = self._get_line(self._initial)[1:]

            nextline = self._get_line(self._pattern[0][0])
            if nextline[0] != None and nextline[0][0] != None:
                self._divTime = nextline[0][0]
            self._next = nextline[1:]
        elif self._ended:
            raise SequenceEnded()
        else:
            if self._next != None:
                line = self._next
                self._next = None
            else:
                line = None

            time = int(time)
            if time >= self._divTime - self._lineTime:
                time = self._divTime - self._lineTime
                self._lineTime = 0
                self._curLine += 1
                if self._curLine == len(self._pattern[self._curPattern]):
                    self._curOrder += 1
                    if self._curOrder < len(self._order):
                        self._curLine = 0
                        self._curPattern = self._order[self._curOrder]
                    else:
                        self._ended = True

                if not self._ended:
                    nextline = self._get_line(self._pattern[self._curPattern][self._curLine])
                    if nextline[0] != None and nextline[0][0] != None:
                        self._divTime = nextline[0][0]
                    self._next = nextline[1:]
            else:
                self._lineTime += time

        return time, line
