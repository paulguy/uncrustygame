from sys import stdout
import copy

SEQ_FIELD_TYPE_INT = "int"
SEQ_FIELD_TYPE_HEX = "hex"
SEQ_FIELD_TYPE_FLOAT = "float"
SEQ_FIELD_TYPE_STR = "str"
SEQ_FIELD_TYPE_ROW = "row"

class SequenceDescription():
    def __init__(self):
        self._columns = list()
        self._rowdesc = list()
        # add necessary "speed" column
        globalRow = self.add_row_description()
        self.add_field(globalRow, SEQ_FIELD_TYPE_INT)
        self.add_column(globalRow)

    @property
    def columns(self):
        return len(self._columns)

    def add_row_description(self):
        self._rowdesc.append(list())
        return len(self._rowdesc) - 1

    def add_field(self, desc, fieldType, rowDesc=None):
        if fieldType == SEQ_FIELD_TYPE_ROW:
            if rowDesc < 0 or rowDesc > len(self._rowdesc) - 1:
                raise IndexError("invalid row description index")
            self._rowdesc[desc].append(rowDesc)
        else:
            self._rowdesc[desc].append(fieldType)

    def get_row_description(self, rowDesc):
        return self._rowdesc(rowDesc)

    def add_column(self, rowDesc):
        if rowDesc < 0 or rowDesc > len(self._rowDesc) - 1:
            raise IndexError("invalid row description index")
        self._columns.append(rowDesc)
        return len(self._columns) - 1

    def get_column(self, column)
        return self._columns[column]


class Sequencer():
    def __init__(self, desc, file):
        self._desc = desc
        self._read_file(self, file)
        self.reset()

    def reset(self):
        self._state = copy.copy(self._initial)
        self._divTime = self._state[0][0]

    def _read_row(self, struct, desc, initial=False):
        changeMask = None
        rowData = struct.split()
        if iniital == False:
            changeMask = int(rowData[0], base=16)
            desc = desc[1:]
            rowData = rowData[1:]

        row = list()
        pos = 0
        for i in range(len(desc) - 1):
            if initial == False:
                changed = changeMask & 1
                changeMask >>= 1
                if not changed:
                    row.append(None)
                    continue

            if desc[i] == SEQ_FIELD_TYPE_INT:
                row.append(int(rowData[pos]))
            elif desc[i] == SEQ_FIELD_TYPE_HEX:
                row.append(int(rowData[pos], base=16))
            elif desc[i] == SEQ_FIELD_TYPE_FLOAT:
                row.append(float(rowData[pos]))
            elif desc[i] == SEQ_FIELD_TYPE_STR:
                row.append(rowData[pos])
            elif instanceof(desc[i], int):
                # SEQ_FIELD_TYPE_ROW
                rowDesc = self._desc.get_row_description(desc[i])
                newrow = read_row(self, rowData[pos:], rowDesc, initial=initial)
                row.append(newrow)
            pos++

        self._row.append(row)
        return len(self._rows) - 1

    def _read_line(self, file, initial=False):
        structs = file.readline().split('|')
        if len(structs) < self._desc.columns:
            raise Exception("not enough columns in file")

        fullRow = list()
        for i in range(self._desc.columns):
            columnDesc = self._desc.get_column(i)
            rowDesc = self._desc.get_row_description(columnDesc)
            newrow = self.read_row(structs[i], rowDesc, initial=initial)
            fullRow.append(newrow)

        return fullRow

    def _read_file(self, file):
        self._initial = read_line(file, initial=True)
        self._row = list()
        self._pattern = list()
        self._order = list()

        patterns = int(file.readline())
        for i in range(patterns):
            patlen = int(file.readline())
            pattern = list()
            for j in range(patlen):
                pattern.append(read_line(file))
            self._pattern.append(pattern)

        ordersData = file.readline().split()
        for item in ordersData:
            order = int(item)
            if order < 0 or order > len(self._pattern) - 1:
                raise IndexError("order refers to pattern out of range")
            self._order.append(int(item))

    def _write_row(self, file, row, desc):
        for item in range(len(desc)):
            if row[item] != None:
                if desc[item] == SEQ_FIELD_TYPE_INT:
                    print("{:d} ".format(row[item]), end='', file=file)
                elif desc[item] == SEQ_FIELD_TYPE_HEX:
                    print("{:x} ".format(row[item]), end='', file=file)
                elif desc[item] == SEQ_FIELD_TYPE_FLOAT:
                    print("{:f} ".format(row[item]), end='', file=file)
                elif desc[item] == SEQ_FIELD_TYPE_STR:
                    print(row[item], end='', file=file)
                elif instanceof(desc[item], int):
                    # SEQ_FIELD_TYPE_ROW
                    rowDesc = self._desc.get_row_description(desc[item])
                    self._write_row(file, row[item:], rowDesc)

    def _write_line(self, file, line):
        for row in range(len(line)):
            changeMask = 0
            if line != self._initial:
                for item in line[row]:
                    changeMask <<= 1
                    if item != None:
                        changeMask |= 1
                print("{} ".format(hex(changeMask)), end='', file=file)

            columnDesc = self._desc.get_column(row)
            desc = self._desc.get_row_description(columnDesc)
            self._print_row(file, line[row], desc)

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

        for order in self._orders:
            print("{} ".format(order, file=file)
