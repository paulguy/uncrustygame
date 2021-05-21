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

    def _read_row(self, structs, desc, initial=False):
        changeMask = None
        rowData = structs.split()
        if iniital == False:
            changeMask = int(rowData[0], base=16)
            rowDesc = rowDesc[1:]
            rowData = rowData[1:]

        row = list()
        pos = 0
        for i in range(len(rowDesc) - 1):
            if initial == False:
                changed = changeMask & 1
                changeMask >>= 1
                if not changed:
                    row.append(None)
                    continue

            if rowDesc[i] == SEQ_FIELD_TYPE_INT:
                row.append(int(rowData[pos]))
            elif rowDesc[i] == SEQ_FIELD_TYPE_HEX:
                row.append(int(rowData[pos], base=16))
            elif rowDesc[i] == SEQ_FIELD_TYPE_FLOAT:
                row.append(float(rowData[pos]))
            elif rowDesc[i] == SEQ_FIELD_TYPE_STR:
                row.append(rowData[pos])
            elif rowDesc[i] == SEQ_FIELD_TYPE_ROW:
                newrow = read_row(self, rowData[pos:], desc, initial=initial)
                row.append(newrow)
            pos++

        self._row.append(row)
        return len(self._rows) - 1

    def _read_line(self, file, initial=False):
        structs = file.readline().split('|')
        if len(structs) < self._desc.columns:
            raise Exception("not enough columns in file")

        fullRow = list()
        for i in range(self._desc.columns - 1):
            columnDesc = self._desc.get_column(i)
            colummn = list()
            for j in range(len(columnDesc) - 1):
                rowDesc = self._desc.get_row_description(j)
                newrow = self.read_row(structs[j], rowDesc, initial=initial)
                column.append(newrow)

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

        ordersData = file.readline().split()
        for item in ordersData:
            order = int(item)
            if order < 0 or order > len(self._pattern) - 1:
                raise IndexError("order refers to pattern out of range")
            self._order.append(int(item))
