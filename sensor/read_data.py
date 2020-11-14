from .format import NumberFormat


class ReadData:
    def __init__(self, data):
        self.data = data
        self.ptr = 0

    def single(self, fmt: NumberFormat):
        number = fmt.read(self.data[self.ptr:])
        self.ptr += len(fmt)
        return number

    def enum(self, clazz):
        value = self.data[self.ptr]
        self.ptr += 1
        return clazz(value)

    def striped(self, fmt: NumberFormat, count: int):
        numbers = [
            fmt.read([
                *self.data[self.ptr + i * fmt.int_bytes:fmt.int_bytes],
                *self.data[self.ptr + count * fmt.int_bytes + i * fmt.dec_bytes:fmt.dec_bytes]
            ])
            for i in range(count)
        ]
        self.ptr += len(fmt) * count
        return numbers
