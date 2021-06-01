from sys import stdout
import copy

FIELD_TYPE_INT = "int"
FIELD_TYPE_HEX = "hex"
FIELD_TYPE_FLOAT = "float"
FIELD_TYPE_STR = "str"
FIELD_TYPE_ROW = "row"

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

    def _read_row(self, struct, desc, initial=False):
        changeMask = None
        if not initial:
            changeMask = int(struct[0], base=16)
            struct = struct[1:]

        row = list()
        pos = 0
        for i in range(len(desc)):
            if not initial:
                # changeMask bits are left to right so logically reversed from
                # their actual bit number
                changed = changeMask & (1 << ((len(desc) - 1) - i))
                if not changed:
                    row.append(None)
                    continue

            if desc[i] == FIELD_TYPE_INT:
                row.append(int(struct[pos]))
            elif desc[i] == FIELD_TYPE_HEX:
                row.append(int(struct[pos], base=16))
            elif desc[i] == FIELD_TYPE_FLOAT:
                row.append(float(struct[pos]))
            elif desc[i] == FIELD_TYPE_STR:
                row.append(struct[pos])
            elif isinstance(desc[i], tuple):
                # callable
                row.append(desc[i][1](desc[i][2], struct[pos]))
            elif isinstance(desc[i], int):
                rowDesc = self._desc._rowdesc[desc[i]]
                newrow = self._read_row(struct[pos:], rowDesc, initial=initial)
                row.append(newrow)
            pos += 1

        self._row.append(row)
        return len(self._row) - 1

    def _read_line(self, file, initial=False):
        structs = file.readline().split('|')
        if len(structs) < self._desc.columns:
            raise Exception("not enough columns in file")

        fullRow = list()
        for i in range(self._desc.columns):
            columnDesc = self._desc._column[i]
            rowDesc = self._desc._rowdesc[columnDesc]
            newrow = self._read_row(structs[i].split(), rowDesc, initial=initial)
            fullRow.append(newrow)

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
                elif isinstance(desc[item], tuple):
                    # callable, but conversion is already done
                    if desc[item][0] == FIELD_TYPE_INT:
                        print("{:d} ".format(row[item]), end='', file=file)
                    elif desc[item][0] == FIELD_TYPE_FLOAT:
                        print("{:f} ".format(row[item]), end='', file=file)
                    elif desc[item][0] == FIELD_TYPE_STR:
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
            if isinstance(desc[i], (int, tuple)):
                if row[i] == None:
                    newRow.append(None)
                else:
                    newRow.append(self._get_row(self._desc._rowdesc[desc[i]], self._row[row[i]]))
            else:
                newRow.append(row[i])
        return newRow

    def _get_line(self, line):
        newLine = list()
        for i in range(len(line)):
            newLine.append(self._get_row(self._desc._rowdesc[i], self._row[line[i]]))
        return newLine

    def advance(self, time):
        line = None

        if self._curOrder == -1 and self._curLine == 0 and self._lineTime == 0:
            self._curOrder = 0
            line = self._get_line(self._initial)[1:]
            time = 0
        elif time >= self._divTime - self._lineTime:
            time = self._divTime - self._lineTime
            self._lineTime = 0
            pattern = self._pattern[self._order[self._curOrder]]
            self._curLine += 1
            if self._curLine == len(pattern):
                self._curOrder += 1
                if self._curOrder < len(self._order):
                    self._curLine = 0
                    pattern = self._pattern[self._order[self._curOrder]]
                else:
                    raise SequenceEnded()
            line = self._get_line(pattern[self._curLine])
            if line[0][0] != None:
                self._divTime = line[0][0]
            line = line[1:]
        else:
            self._lineTime += time

        return time, line
