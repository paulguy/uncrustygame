from sys import stdout
import copy

#TODO:
# arithmetic expressions parsing, with some way to take note values as a parameter

FIELD_TYPE_INT = object()
FIELD_TYPE_HEX = object()
FIELD_TYPE_FLOAT = object()
FIELD_TYPE_STR = object()
FIELD_TYPE_ROW = object()

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
        """
        Get number of columns in this sequence.
        """
        return len(self._column)

    def add_row_description(self):
        """
        Add a column type description and return its ID.
        """
        self._rowdesc.append(list())
        return len(self._rowdesc) - 1

    def add_field(self, desc, fieldType, rowDesc=None, func=None, priv=None):
        """
        Add a field to a column type description.
        """
        if fieldType == FIELD_TYPE_ROW:
            if rowDesc < 0 or rowDesc > len(self._rowdesc) - 1:
                raise IndexError("invalid row description index")
            self._rowdesc[desc].append(rowDesc)
        elif func != None:
            self._rowdesc[desc].append((fieldType, func, priv))
        else:
            self._rowdesc[desc].append(fieldType)

    def add_column(self, rowDesc):
        """
        Add an actual column from a type description to hold data to the sequence.
        """
        if rowDesc < 0 or rowDesc > len(self._rowdesc) - 1:
            raise IndexError("invalid row description index")
        self._column.append(rowDesc)
        return len(self._column) - 1


class Sequencer():
    def __init__(self, desc, file, trace=False):
        """
        Create a sequence.

        desc   A sequence description built up with SequenceDescription.
        file   The file to read the sequence from which must match the format described in desc.
        trace  True to output a bunch of status information.
        """
        self._trace = trace
        self._desc = desc
        self._read_file(file)
        self.reset()

    def reset(self):
        """
        Restart the state of the sequence to the beginning.
        """
        self._divTime = self._row[self._initial[0]][0]
        self._curOrder = -1
        self._curLine = 0
        self._lineTime = 0
        self._ended = False

    def _add_row(self, newrow, descnum):
        desc = self._desc._rowdesc[descnum]
        for row in range(len(self._row)):
            if self._row[row][-1] == descnum:
                if len(newrow) == len(desc):
                    found = True
                    for item in range(len(newrow)):
                        if self._row[row][item] != newrow[item]:
                            found = False
                            break
                    if found:
                        return row
        newrow.append(descnum)
        self._row.append(newrow)
        return len(self._row) - 1

    def _read_row(self, struct, descnum, initial=False):
        desc = self._desc._rowdesc[descnum]

        pos = 0
        changeMask = None
        save = None
        if not initial:
            if len(struct) == 0:
                return 0, None 
            first = struct[0]
            # check to see if this is referencing a saved row
            if first[0] == '=':
                return 1, first[1:]
            # check to see if this row is to be saved
            try:
                equals = first.index('=')
                save = first[equals+1:]
                first = first[:equals]
            except ValueError:
                save = None
            if save != None:
                if len(save) == 0:
                    raise ValueError("Empty row name.")
                if save.isnumeric():
                    raise ValueError("Numeric row name.")
            changeMask = int(first, base=16)
            if changeMask == 0:
                return 1, -1
            pos += 1

        row = list()
        for i in range(len(desc)):
            if not initial:
                # changeMask bits are left to right so logically reversed from
                # their actual bit number
                changed = changeMask & (1 << ((len(desc) - 1) - i))
                if changed == 0:
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
                    # pass False because an initial row argument may be an empty
                    # row
                    try:
                        adv, newrow = self._read_row(struct[pos:], desc[i], initial=False)
                    except IndexError as e:
                        print("... while parsing parameter change field {}..".format(i))
                        raise e
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

        rownum = self._add_row(row, descnum)
        if save != None:
            if save in self._namedRows:
                raise ValueError("Duplicate named row definition: {}".format(save))
            self._namedRows[save] = rownum
        return pos, rownum

    def _read_line(self, file, initial=False):
        structs = file.readline().split('|')

        fullRow = list()
        # allow global only or totally empty lines
        if not initial and len(structs) == 2 and len(structs[1].strip()) == 0:
            if len(structs[0].strip()) == 0:
                # totally empty line "|"
                for i in range(self._desc.columns):
                    fullRow.append(None)
            else:
                # line with only global changes "~~~ |"
                columnDesc = self._desc._column[0]
                split = structs[0].split()
                pos, newrow = self._read_row(split, columnDesc)
                if len(split) > pos:
                    raise Exception("too many values in column ({} > {})".format(len(split), pos))
                fullRow.append(newrow)
                for i in range(1, self._desc.columns):
                    fullRow.append(None)
        else:
            skip = 0
            for i in range(len(structs)):
                try:
                    columnDesc = self._desc._column[i + skip]
                except IndexError:
                    raise IndexError("Too many columns in line  == {}".format(len(self._desc._column)))
                split = structs[i].split()
                first = 0
                try:
                    first = int(split[0])
                except ValueError:
                    pass
                if not initial and first < 0:
                    if len(split) > 1:
                        raise Exception("negative column with extra values")
                    first = -first
                    if i + skip + first - 1 >= len(self._desc._column):
                        raise Exception("skipped columns would go beyond column range")
                    for j in range(first):
                        fullRow.append(None)
                    skip += first - 1
                    continue
                pos, newrow = self._read_row(split, columnDesc, initial=initial)
                if len(split) > pos:
                    raise Exception("too many values in column {} ({} > {})".format(i, len(split), pos))
                fullRow.append(newrow)

        if len(fullRow) != self._desc.columns:
            raise Exception("wrong number of columns in file ({} != {})".format(len(fullRow), self._desc.columns))

        return fullRow

    def _fix_rows(self):
        for row in self._row:
            desc = self._desc._rowdesc[row[-1]]
            for i in range(len(desc)):
                if isinstance(desc[i], int) and \
                   isinstance(row[i], str):
                    row[i] = self._namedRows[row[i]]

    def _read_file(self, file):
        self._row = list()
        self._namedRows = {}
        self._pattern = list()
        self._order = list()
        self._initial = self._read_line(file, initial=True)

        try:
            patterns = int(file.readline())
        except Exception as e:
            print("Unexpected end of file or error reading pattern count.")
            raise e
        for i in range(patterns):
            try:
                patlen = int(file.readline())
            except Exception as e:
                print("Unexpected end of file or error reading pattern length.")
                raise e
            pattern = list()
            for j in range(patlen):
                pattern.append(self._read_line(file))
            self._pattern.append(pattern)
        self._fix_rows()
        if self._trace:
            for row in enumerate(self._row):
                print("{} {}".format(row[0], row[1][:-1]))
        try:
            ordersData = file.readline().split()
        except Exception as e:
            print("Unexpected end of file or error reading pattern order.")
            raise e
        for item in enumerate(ordersData):
            order = int(item[1])
            if order < 0 or order > len(self._pattern) - 1:
                raise IndexError("order {} refers to pattern out of range: {}".format(item[0] + 1, order))
            self._order.append(order)

    def _write_row(self, file, row, initial):
        desc = self._desc._rowdesc[row[-1]]

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
            self._write_row(file, self._row[line[row]], initial)

            if row != len(line) - 1:
                print("| ", end='', file=file)

        print(file=file)

    def write_file(self, file=stdout):
        """
        Output sequence data to a file.
        """
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

    def get_row(self, rownum):
        """
        Get a row of data.
        """
        return self._row[rownum][:-1]

    def _get_line(self, line):
        newLine = list()
        for i in range(len(line)):
            if line[i] is None or line[i] == -1:
                newLine.append(None)
            else:
                newLine.append(self._row[line[i]][:-1])
        return newLine

    def set_pattern(self, pattern):
        """
        Set the current sequence pattern to start playing from.
        """
        if pattern < 0 or pattern > len(self._pattern):
            raise IndexError("pattern out of range")
        self._curPattern = pattern
        self._curLine = 0

    def set_order(self, order):
        """
        Set the current sequence pattern indicated by a specific sequence order to start playing from.
        """
        if pattern < 0 or pattern > len(self._order):
            raise IndexError("order out of range")
        self._curOrder = 0
        self._curPattern = self._order[self._curOrder]
        self._curLine = 0

    def advance(self, time):
        """
        Advance the sequence by a certain amount of time.

        Will return without advancing the full amount of time requested if it would get to the next line.
        returns the amount of time advanced, and the data of the line it fell on.
        """
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
